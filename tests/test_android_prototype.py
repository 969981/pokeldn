"""The Android scheduler runs protocol work on LDN's Trio thread and closes its worker."""
import subprocess
import sys
from pathlib import Path


def test_android_shared_loop_thread_ownership_and_close_grace():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, str(root / 'examples/android/check_shared_loop.py')],
                            cwd=root, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def _android_app():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'examples/android/src/python'))
    try:
        import android_app
    finally:
        sys.path.pop(0)
    return android_app


def _pikachu_pk3():
    record = bytearray(100)
    record[32:34] = (25).to_bytes(2, 'little')  # PID 0, OT 0: key 0, order GAEM, growth first
    record[28:30] = (25).to_bytes(2, 'little')  # the secure region's word sum
    record[84] = 5
    return bytes(record)


def test_android_import_accepts_a_pk3_and_refuses_damage(tmp_path):
    import hashlib
    import json
    app = _android_app()
    offer, manifest = tmp_path / 'offer.pk3', tmp_path / 'offer.json'
    offer.write_bytes(_pikachu_pk3())
    answer = json.loads(app.check_offer(offer, manifest))
    assert answer['ok'] and answer['species'] == 'Pikachu' and answer['level'] == 5
    written = json.loads(manifest.read_text())
    assert written['sha256'] == hashlib.sha256(offer.read_bytes()).hexdigest() and written['legal'] is None
    for damaged in (_pikachu_pk3()[:99], _pikachu_pk3()[:28] + b'\x00\x00' + _pikachu_pk3()[30:]):
        offer.write_bytes(damaged)
        assert not json.loads(app.check_offer(offer, tmp_path / 'other.json'))['ok']
    assert not (tmp_path / 'other.json').exists()


def test_android_import_refuses_keys_ldn_cannot_use(tmp_path):
    import json
    app = _android_app()
    keys = tmp_path / 'prod.keys'
    keys.write_text('master_key_00 = ' + '00' * 16 + '\n')
    assert 'aes_kek_generation_source' in json.loads(app.check_keys(keys))['error']
    keys.write_bytes(b'\x89PNG\r\n')
    assert not json.loads(app.check_keys(keys))['ok']
    keys.write_text(''.join('%s = %s\n' % (name, '11' * 16) for name in app.REQUIRED_KEYS))
    assert json.loads(app.check_keys(keys))['ok']
