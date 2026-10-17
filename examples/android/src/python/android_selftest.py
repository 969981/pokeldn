"""`adb shell am start -n org.pokeldn.usbprobe/.PokeldnActivity --ez selftest true`: imports what the
app's runs need on this phone and checks the PKHeX helper answers. Results go to logcat (PokeLDN)."""
import importlib
import traceback

MODULES = ('Crypto.Cipher.AES', 'trio', 'zstandard', 'serial', 'esptool', 'websockets', 'ldn',
           'pokeldn.ldn.esp32_wlan', 'pokeldn.ldn.userspace_ip', 'pokeldn.frlg.link.host_app',
           'pokeldn.swsh.host_trade', 'pokeldn.online.gts', 'gui.board', 'gui.views.games',
           'gui.views.boards', 'gui.views.bank', 'gui.views.gts', 'gui.views.settings')


def run():
    lines = []
    for name in MODULES:
        try:
            importlib.import_module(name)
            lines.append('PASS import ' + name)
        except Exception:
            lines.append('FAIL import ' + name + '\n' + traceback.format_exc())
    try:
        from pokeldn import pokemon
        species = pokemon.SERVICE.species('sv')
        lines.append('PASS PKHeX species: %d' % len(species))
    except Exception:
        lines.append('FAIL PKHeX\n' + traceback.format_exc())
    try:
        import time
        from pokeldn.app import android
        android.keep_awake(True)
        time.sleep(2)
        android.keep_awake(False)
        lines.append('PASS keep awake on and off')
    except Exception:
        lines.append('FAIL keep awake\n' + traceback.format_exc())
    return '\n'.join(lines)
