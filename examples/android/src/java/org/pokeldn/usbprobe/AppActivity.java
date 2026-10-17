package org.pokeldn.usbprobe;

import android.app.Activity;
import android.app.PendingIntent;
import android.content.*;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.hardware.usb.*;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.*;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import java.io.*;
import java.util.concurrent.atomic.AtomicBoolean;
import org.json.JSONObject;

/** The player's app: board setup, the two files a trade needs, then the FireRed/LeafGreen trade. */
public class AppActivity extends Activity {
    private static final String TAG = "PokeLDNApp";
    private static final String PERMISSION = "org.pokeldn.usbprobe.APP_USB_PERMISSION";
    private static final int PICK_KEYS = 1, PICK_OFFER = 2, SAVE_RECEIVED = 3;
    private static final int BLUE = 0xff2f6fde, RED = 0xffe0453a, GREEN = 0xff2e9e5b, MUTED = 0xff6b7280;

    private UsbManager manager;
    private UsbDevice device;
    private boolean denied;
    private String handshake;        // null untried, "" answered, else the error
    private String firmware = "";
    private final AtomicBoolean busy = new AtomicBoolean();
    private volatile boolean trading, destroyed;
    private File received;

    private TextView progress, boardTitle, boardText, filesText, tradeTitle, tradeText, log;
    private Button boardAction, settingsButton, keysButton, offerButton, tradeButton, saveButton;
    private View boardDot, filesDot, tradeDot;

    private final BroadcastReceiver usbEvents = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            if (PERMISSION.equals(intent.getAction()))
                denied = !intent.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED, false);
            if (UsbManager.ACTION_USB_DEVICE_DETACHED.equals(intent.getAction())) { handshake = null; firmware = ""; }
            refresh();
        }
    };

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        manager = (UsbManager)getSystemService(USB_SERVICE);
        buildViews();
        IntentFilter filter = new IntentFilter(PERMISSION);
        filter.addAction(UsbManager.ACTION_USB_DEVICE_ATTACHED);
        filter.addAction(UsbManager.ACTION_USB_DEVICE_DETACHED);
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(usbEvents, filter, Context.RECEIVER_NOT_EXPORTED);
        else registerReceiver(usbEvents, filter);
    }

    // Returning from Settings or from Android's USB prompt re-reads the whole state.
    @Override protected void onResume() { super.onResume(); refresh(); }
    @Override protected void onNewIntent(Intent intent) { super.onNewIntent(intent); refresh(); }

    private File folder() {
        File dir = new File(getFilesDir(), "trade");
        dir.mkdirs();
        return dir;
    }

    private void refresh() {
        if (destroyed) return;
        UsbDevice board = null;
        boolean bridge = false;
        for (UsbDevice candidate : manager.getDeviceList().values()) {
            if (Setup.isBoard(candidate.getVendorId(), candidate.getProductId())) board = candidate;
            else if (Setup.isBridge(candidate.getVendorId())) bridge = true;
        }
        if (board == null || (device != null && board.getDeviceId() != device.getDeviceId())) { handshake = null; firmware = ""; }
        device = board;
        boolean permission = board != null && manager.hasPermission(board);
        if (permission) denied = false;
        Setup.State state = Setup.decide(board != null, bridge, permission, denied, handshake);
        if (state == Setup.State.CHECKING && !trading) checkBoard();
        render(state);
    }

    private void render(Setup.State state) {
        boolean ready = state == Setup.State.READY || trading;
        boardTitle.setText(trading ? "Board in use" : Setup.title(state));
        boardText.setText(Setup.guidance(state, Build.MANUFACTURER, state == Setup.State.READY ? firmware : handshake));
        boardAction.setVisibility(View.VISIBLE);
        settingsButton.setVisibility(state == Setup.State.NO_DEVICE ? View.VISIBLE : View.GONE);
        switch (state) {
            case NEEDS_PERMISSION: case PERMISSION_DENIED:
                boardAction.setText("Allow USB access"); boardAction.setOnClickListener(v -> askPermission()); break;
            case HANDSHAKE_FAILED:
                boardAction.setText("Try again"); boardAction.setOnClickListener(v -> { handshake = null; refresh(); }); break;
            case CHECKING: case READY: boardAction.setVisibility(View.GONE); break;
            default:
                boardAction.setText("Check again"); boardAction.setOnClickListener(v -> refresh());
        }
        dot(boardDot, ready ? GREEN : (state == Setup.State.CHECKING ? BLUE : RED));

        boolean keys = new File(folder(), "prod.keys").isFile();
        JSONObject offer = offer();
        StringBuilder files = new StringBuilder();
        files.append(keys ? "Switch keys imported." : "Import prod.keys, dumped from your own Switch. They stay in this app.");
        files.append("\n\n");
        if (offer != null) {
            String species = offer.optString("species"), nickname = offer.optString("nickname").trim(), ot = offer.optString("ot").trim();
            files.append("Offering ").append(nickname.isEmpty() ? species : nickname + " (" + species + ")")
                .append(", level ").append(offer.optString("level"));
            if (!ot.isEmpty()) files.append(", OT ").append(ot);
        }
        else files.append("Choose the Pokemon to send, a .pk3 file.");
        filesText.setText(files);
        keysButton.setText(keys ? "Replace keys" : "Import prod.keys");
        offerButton.setText(offer != null ? "Choose another Pokemon" : "Choose a .pk3");
        boolean filesReady = keys && offer != null;
        dot(filesDot, filesReady ? GREEN : MUTED);
        keysButton.setEnabled(!trading); offerButton.setEnabled(!trading);

        int step = !ready ? 1 : (!filesReady ? 2 : 3);
        progress.setText("Step " + step + " of 3");
        tradeButton.setEnabled(trading || (ready && filesReady));
        tradeButton.setText(trading ? "Stop the trade" : "Start hosting");
        if (!trading && received == null) {
            tradeTitle.setText("FireRed / LeafGreen trade");
            tradeText.setText(step < 3 ? "Finish the steps above first." :
                "Tap Start hosting, then on the Switch: Pokemon Center 2F, the third attendant, Trade Center, "
                + "JOIN, and pick POKELDN.\n\nOther games are not available on the phone yet; use the desktop app for them.");
        }
        saveButton.setVisibility(received != null && !trading ? View.VISIBLE : View.GONE);
        for (Button each : new Button[] {keysButton, offerButton, tradeButton}) each.setAlpha(each.isEnabled() ? 1f : 0.4f);
        dot(tradeDot, trading ? BLUE : (received != null ? GREEN : MUTED));
    }

    private JSONObject offer() {
        File manifest = new File(folder(), "offer.json");
        if (!manifest.isFile() || !new File(folder(), "offer.pk3").isFile()) return null;
        try { return new JSONObject(new String(read(manifest), "UTF-8")); }
        catch (Exception error) { return null; }
    }

    private void askPermission() {
        if (device == null) return;
        manager.requestPermission(device, PendingIntent.getBroadcast(this, 0,
            new Intent(PERMISSION).setPackage(getPackageName()), PendingIntent.FLAG_MUTABLE));
    }

    private Python python() {
        if (!Python.isStarted()) Python.start(new AndroidPlatform(getApplicationContext()));
        return Python.getInstance();
    }

    private void checkBoard() {
        if (device == null || !busy.compareAndSet(false, true)) return;
        UsbDevice selected = device;
        new Thread(() -> {
            String result;
            try (UsbStream stream = new UsbStream(manager, selected)) {
                JSONObject answer = new JSONObject(python().getModule("android_app").callAttr("hello", stream).toString());
                if (answer.getBoolean("ok")) { firmware = answer.getString("firmware"); result = ""; }
                else result = answer.getString("error");
            } catch (Exception error) { result = String.valueOf(error.getMessage()); Log.e(TAG, "Handshake", error); }
            handshake = result;
            busy.set(false);
            runOnUiThread(this::refresh);
        }, "board-check").start();
    }

    private void pick(int request) {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*");
        startActivityForResult(intent, request);
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (result != RESULT_OK || data == null || data.getData() == null) return;
        Uri uri = data.getData();
        new Thread(() -> {
            try {
                if (request == SAVE_RECEIVED) {
                    try (OutputStream out = getContentResolver().openOutputStream(uri)) { out.write(read(received)); }
                    toast("Saved.");
                    return;
                }
                File incoming = new File(folder(), "import.tmp");
                try (InputStream in = getContentResolver().openInputStream(uri);
                     OutputStream out = new FileOutputStream(incoming)) { copy(in, out, 1 << 20); }
                Python py = python();
                JSONObject answer;
                if (request == PICK_KEYS) {
                    answer = new JSONObject(py.getModule("android_app").callAttr("check_keys", incoming.getPath()).toString());
                    if (answer.getBoolean("ok")) incoming.renameTo(new File(folder(), "prod.keys"));
                } else {
                    File manifest = new File(folder(), "offer.json.tmp");
                    answer = new JSONObject(py.getModule("android_app")
                        .callAttr("check_offer", incoming.getPath(), manifest.getPath()).toString());
                    if (answer.getBoolean("ok")) {
                        incoming.renameTo(new File(folder(), "offer.pk3"));
                        manifest.renameTo(new File(folder(), "offer.json"));
                    }
                }
                // The trade worker's tested crypto option (examples/android/README.md, Scheduling).
                new File(folder(), "crypto_hold_gil").createNewFile();
                incoming.delete();
                if (!answer.getBoolean("ok")) toast(answer.getString("error"));
            } catch (Exception error) { toast("Import failed: " + error.getMessage()); Log.e(TAG, "Import", error); }
            runOnUiThread(this::refresh);
        }, "import").start();
    }

    private void toggleTrade() {
        if (trading) {
            python().getModule("android_trade").callAttr("cancel");
            tradeText.setText("Stopping...");
            return;
        }
        if (device == null || !busy.compareAndSet(false, true)) return;
        trading = true; received = null;
        log.setText("");
        tradeTitle.setText("Starting the host...");
        tradeText.setText("Keep the app open during the trade.");
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        UsbDevice selected = device;
        new Thread(() -> {
            try (UsbStream stream = new UsbStream(manager, selected)) {
                python().getModule("android_trade").callAttr("run", stream, this);
            } catch (Exception error) {
                report("ERROR " + error.getMessage());
                status("The trade stopped", "Error: " + error.getMessage());
                Log.e(TAG, "Trade", error);
            } finally {
                trading = false; busy.set(false);
                runOnUiThread(() -> { getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON); refresh(); });
            }
        }, "trade").start();
        refresh();
    }

    /** android_trade's output; the lines the player needs become the status card, the rest go under Details. */
    public void report(String message) {
        Log.i(TAG, message);
        if (message.startsWith("ANDROID_HOST_READY"))
            status("Host is up: join POKELDN", "On the Switch: Pokemon Center 2F, the third attendant, Trade Center, JOIN, "
                + "then pick POKELDN. Choose a Pokemon on the trade screen as usual.");
        else if (message.startsWith("ANDROID_TRADE_RESULT=")) {
            try {
                JSONObject result = new JSONObject(message.substring("ANDROID_TRADE_RESULT=".length()));
                File file = new File(result.getString("run_folder"), "received.pk3");
                if (result.optBoolean("received") && file.isFile()) {
                    received = file;
                    status("Trade complete", "The Pokemon you received is kept in the app. Tap Save to copy it to your files.");
                } else status("No trade this time", "The host closed before a Pokemon arrived.");
            } catch (Exception error) { status("Trade finished", message); }
        } else if (message.startsWith("Radio: ")) status("Board connected", "Opening the network...");
        else if (message.startsWith("Trade stopped")) status("Trade stopped", "You stopped the host.");
        if (!destroyed) runOnUiThread(() -> log.append(message + "\n"));
    }

    private void status(String title, String text) {
        if (!destroyed) runOnUiThread(() -> { tradeTitle.setText(title); tradeText.setText(text); });
    }

    private void toast(String text) { runOnUiThread(() -> Toast.makeText(this, text, Toast.LENGTH_LONG).show()); }

    private void saveReceived() {
        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE)
            .setType("application/octet-stream").putExtra(Intent.EXTRA_TITLE, "received.pk3");
        startActivityForResult(intent, SAVE_RECEIVED);
    }

    private static byte[] read(File file) throws IOException {
        try (InputStream in = new FileInputStream(file)) {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            copy(in, out, Integer.MAX_VALUE);
            return out.toByteArray();
        }
    }

    private static void copy(InputStream in, OutputStream out, int limit) throws IOException {
        byte[] buffer = new byte[8192];
        int total = 0, count;
        while ((count = in.read(buffer)) > 0) {
            total += count;
            if (total > limit) throw new IOException("the file is too large");
            out.write(buffer, 0, count);
        }
    }

    @Override public void onDestroy() {
        destroyed = true;
        if (trading && Python.isStarted()) Python.getInstance().getModule("android_trade").callAttr("cancel");
        unregisterReceiver(usbEvents);
        super.onDestroy();
    }

    // Views ------------------------------------------------------------------------------------

    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }

    private void dot(View view, int color) {
        GradientDrawable shape = new GradientDrawable();
        shape.setShape(GradientDrawable.OVAL); shape.setColor(color);
        view.setBackground(shape);
    }

    private LinearLayout card(LinearLayout page, String heading, View[] dotOut) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(16), dp(14), dp(16), dp(14));
        GradientDrawable background = new GradientDrawable();
        background.setColor(Color.WHITE); background.setCornerRadius(dp(14));
        background.setStroke(dp(1), 0xffe3e7ee);
        card.setBackground(background);
        LinearLayout row = new LinearLayout(this);
        row.setGravity(Gravity.CENTER_VERTICAL);
        View dot = new View(this);
        row.addView(dot, new LinearLayout.LayoutParams(dp(10), dp(10)));
        TextView label = text(heading, 13, MUTED);
        label.setPadding(dp(8), 0, 0, 0);
        row.addView(label);
        card.addView(row);
        dotOut[0] = dot;
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, -2);
        params.topMargin = dp(12);
        page.addView(card, params);
        return card;
    }

    private TextView text(String value, int size, int color) {
        TextView view = new TextView(this);
        view.setText(value); view.setTextSize(size); view.setTextColor(color);
        return view;
    }

    private TextView title(LinearLayout card) {
        TextView view = text("", 19, 0xff111827);
        view.setTypeface(Typeface.DEFAULT_BOLD);
        view.setPadding(0, dp(6), 0, dp(4));
        card.addView(view);
        return view;
    }

    private Button button(LinearLayout card, String label, int color, View.OnClickListener action) {
        Button view = new Button(this);
        view.setText(label); view.setAllCaps(false); view.setTextColor(Color.WHITE);
        GradientDrawable background = new GradientDrawable();
        background.setColor(color); background.setCornerRadius(dp(10));
        view.setBackground(background);
        view.setOnClickListener(action);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(-1, dp(48));
        params.topMargin = dp(10);
        card.addView(view, params);
        return view;
    }

    private void buildViews() {
        LinearLayout page = new LinearLayout(this);
        page.setOrientation(LinearLayout.VERTICAL);
        page.setPadding(dp(16), dp(40), dp(16), dp(96));
        TextView name = text("PokeLDN", 28, BLUE);
        name.setTypeface(Typeface.DEFAULT_BOLD);
        page.addView(name);
        progress = text("", 14, RED);
        page.addView(progress);

        View[] holder = new View[1];
        LinearLayout board = card(page, "1  RADIO BOARD", holder); boardDot = holder[0];
        boardTitle = title(board);
        boardText = text("", 15, 0xff374151); board.addView(boardText);
        boardAction = button(board, "", BLUE, null);
        settingsButton = button(board, "Open Settings", MUTED, v -> startActivity(new Intent(Settings.ACTION_SETTINGS)));

        LinearLayout files = card(page, "2  YOUR FILES", holder); filesDot = holder[0];
        filesText = text("", 15, 0xff374151); files.addView(filesText);
        keysButton = button(files, "", BLUE, v -> pick(PICK_KEYS));
        offerButton = button(files, "", BLUE, v -> pick(PICK_OFFER));

        LinearLayout trade = card(page, "3  TRADE", holder); tradeDot = holder[0];
        tradeTitle = title(trade);
        tradeText = text("", 15, 0xff374151); trade.addView(tradeText);
        tradeButton = button(trade, "", RED, v -> toggleTrade());
        saveButton = button(trade, "Save the received Pokemon", GREEN, v -> saveReceived());

        TextView details = text("Details", 14, BLUE);
        details.setPadding(0, dp(20), 0, dp(6));
        log = text("", 12, MUTED);
        log.setTextIsSelectable(true); log.setVisibility(View.GONE);
        details.setOnClickListener(v -> log.setVisibility(log.getVisibility() == View.GONE ? View.VISIBLE : View.GONE));
        page.addView(details); page.addView(log);

        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(0xfff3f5f9);
        scroll.addView(page);
        setContentView(scroll);
    }
}
