import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from studio_agent_gateway import Gateway


def _fd_count():
    return len(os.listdir('/dev/fd'))


class _Client:
    base = 'http://127.0.0.1:8899'


def test_receipt_reads_close_sqlite_connections(tmp_path):
    gateway = Gateway(_Client(), private=tmp_path)
    before = _fd_count()
    for _ in range(300):
        gateway.receipt('missing-command')
    after = _fd_count()
    assert after <= before + 2
