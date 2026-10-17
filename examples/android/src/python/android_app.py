"""Checks the guided Android app runs before a trade: the board's HELLO and the imported files."""
import hashlib
import json
from pathlib import Path

# The keys ldn.Network derives the LDN session keys from [vendor/LDN/ldn/__init__.py:138-149].
REQUIRED_KEYS = ('master_key_00', 'aes_kek_generation_source', 'aes_key_generation_source')
PK3_SIZES = (80, 100)


def hello(usb):
    """One HELLO exchange with the board; closing the radio closes the stream."""
    from android_probe import AndroidStream
    from pokeldn.ldn import esp32
    radio = esp32.Radio(AndroidStream(usb))
    try:
        error = None
        for _ in range(10):
            try:
                info = esp32.Info.parse(radio.request(esp32.CMD_HELLO, b'', esp32.MSG_INFO, timeout=1))
                break
            except esp32.RadioError as caught:
                error = caught
        else:
            return json.dumps({'ok': False, 'error': 'The board did not answer: %s' % error})
        if info.version != esp32.PROTOCOL_VERSION:
            return json.dumps({'ok': False, 'error': 'The board speaks radio protocol %d; this app needs %d. '
                               'Flash the firmware from the desktop app.' % (info.version, esp32.PROTOCOL_VERSION)})
        return json.dumps({'ok': True, 'firmware': info.firmware_version or 'unknown', 'text': info.text})
    finally:
        radio.close()


def check_keys(path):
    text = Path(path).read_bytes()
    keys = {}
    try:
        for line in text.decode('ascii').splitlines():
            name, sep, value = line.partition('=')
            if sep:
                keys[name.strip()] = bytes.fromhex(value.strip())
    except (UnicodeDecodeError, ValueError):
        return json.dumps({'ok': False, 'error': 'This is not a prod.keys file.'})
    missing = [name for name in REQUIRED_KEYS if name not in keys]
    if missing:
        return json.dumps({'ok': False, 'error': 'prod.keys lacks ' + ', '.join(missing) + '.'})
    return json.dumps({'ok': True, 'count': len(keys)})


def check_offer(path, manifest_path):
    """Accepts a PK3 whose checksum holds and writes the manifest android_trade checks."""
    from pokeldn.frlg.save.mon import decode_mon
    record = Path(path).read_bytes()
    if len(record) not in PK3_SIZES:
        return json.dumps({'ok': False, 'error': 'A .pk3 file is 80 or 100 bytes; this one is %d.' % len(record)})
    mon = decode_mon(record)
    if not mon['checksum_ok'] or not 1 <= mon['species'] <= 411:
        return json.dumps({'ok': False, 'error': 'This .pk3 is damaged: its checksum does not match.'})
    manifest = {'sha256': hashlib.sha256(record).hexdigest(), 'legal': None, 'checked': 'checksum',
                'species': mon['species_name'].title(), 'level': mon['level'] or '?', 'ot': mon['otName'],
                'nickname': mon['nickname']}
    Path(manifest_path).write_text(json.dumps(manifest))
    return json.dumps({'ok': True, **manifest})
