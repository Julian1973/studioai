import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import serve


def _fd_count():
    return len(os.listdir('/dev/fd'))


def test_repeated_json_route_reads_do_not_accumulate_file_descriptors(tmp_path):
    path = tmp_path / 'payload.json'
    path.write_text('{"ok": true}', encoding='utf-8')
    before = _fd_count()
    for _ in range(300):
        assert serve._read_json_file(path)['ok'] is True
    after = _fd_count()
    assert after <= before + 2
