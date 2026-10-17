"""Runs the desktop app's interface (gui/main.py) as a local web server the Activity's WebView shows,
with the tuning the FireRed trade measured on a phone applied to every run (README, Scheduling)."""
import os
import signal
import sys
import threading
from pathlib import Path

_signal = signal.signal


def _signal_on_main_thread_only(signum, handler):
    # Flet and the launchers install SIGINT handlers; Chaquopy runs them off Python's main thread.
    if threading.current_thread() is threading.main_thread():
        return _signal(signum, handler)
    return signal.getsignal(signum)


def _crypto_holds_the_gil():
    # PyCryptodome's tiny AES calls through ctypes.PyDLL: no GIL release per call.
    import ctypes
    from Crypto.Util import _raw_api
    if _raw_api.backend == 'ctypes':
        _raw_api.CDLL = ctypes.PyDLL


def _tuned_runs():
    import android_compat
    from pokeldn.app import android, runner
    state = {}

    def before():
        state['affinity'] = os.sched_getaffinity(0)
        state['interval'] = sys.getswitchinterval()
        cpu = android_compat.performance_cpu()
        if cpu is not None:
            os.sched_setaffinity(0, {cpu})
        sys.setswitchinterval(0.001)
        android.keep_awake(True)

    def after():
        from ldn import wlan
        from pokeldn.ldn import esp32_wlan
        radio, esp32_wlan._radio = esp32_wlan._radio, None   # a child process would have closed it
        if radio is not None:
            radio.close()
        wlan.set_factory(None)
        sys.setswitchinterval(state.get('interval', 0.005))
        if 'affinity' in state:
            os.sched_setaffinity(0, state['affinity'])
        android.keep_awake(False)

    runner.before_run(before)
    runner.after_run(after)


def _load_unicorn():
    # Unicorn turns importlib.resources.files("unicorn") into a Path, which Chaquopy's asset paths
    # refuse; its library comes from LIBUNICORN_PATH (the app's native library folder) anyway.
    import importlib.resources
    files = importlib.resources.files
    importlib.resources.files = lambda package: Path(os.environ["LIBUNICORN_PATH"]) if package == "unicorn" else files(package)
    try:
        import unicorn  # noqa: F401
    finally:
        importlib.resources.files = files


def _shared_trio_loop():
    # The FireRed host's protocol on LDN's own Trio thread (android_host_loop, README, Scheduling).
    import android_host_loop
    from pokeldn.frlg.link.host_app import HostApplication
    HostApplication._timing = {}
    HostApplication.run = android_host_loop.run


def serve(port, files_dir, native_dir):
    import android_compat
    android_compat.install()
    signal.signal = _signal_on_main_thread_only
    home = Path(files_dir)
    os.environ.update(HOME=str(home), POKELDN_DATA=str(home / "data"), POKELDN_GUI_WEB=str(port),
                      POKELDN_PLATFORM="android", POKELDN_PKHEX=str(Path(native_dir) / "libpokeldn_pkhex.so"), LIBUNICORN_PATH=str(native_dir))
    import shutil
    shutil.rmtree(home / "outbox", ignore_errors=True)   # copies already handed to Android's pickers
    import pokeldn
    os.chdir(Path(pokeldn.__file__).resolve().parent.parent)
    from pokeldn.app import android
    android.install()
    _crypto_holds_the_gil()
    _load_unicorn()
    _tuned_runs()
    _shared_trio_loop()
    from gui import main
    main.run()
