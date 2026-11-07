"""Process-scoped connection to the same exchange ticker client used by the panel."""
import atexit
import json
import os
from pathlib import Path
import queue
import subprocess
import threading

SCRIPT = Path(__file__).resolve().parents[3] / 'terminal' / 'agent-quotes.mjs'
_lock = threading.RLock()
_process = None
_symbols = set()
_replies = None


def close():
    global _process
    with _lock:
        if _process is None:
            return
        process, _process = _process, None
        try:
            process.stdin.close()
        except OSError:
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


atexit.register(close)


def _read_replies(process, replies):
    try:
        for line in process.stdout:
            replies.put(line)
    finally:
        process.stdout.close()
        replies.put(None)


def start(symbols):
    global _process, _replies, _symbols
    requested = set(symbols)
    with _lock:
        if _process is not None and _process.poll() is None and requested <= _symbols:
            return
        close()
        _process = subprocess.Popen(
            ['node', str(SCRIPT), json.dumps(sorted(requested))],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding='utf-8',
        )
        _symbols = requested
        _replies = queue.Queue()
        threading.Thread(target=_read_replies, args=(_process, _replies), daemon=True).start()


def read(symbols, execution=None):
    with _lock:
        start(symbols)
        audit = not execution and os.getenv('LIAM_QUOTE_PARITY') == '1'
        try:
            _process.stdin.write(json.dumps({'symbols':sorted(set(symbols)), 'execution':execution, 'audit':audit})+'\n')
            _process.stdin.flush()
            line = _replies.get(timeout=65 if audit else 16)
            if line is None:
                raise OSError('exchange ticker client exited')
            packet = json.loads(line)
            if isinstance(packet, dict) and 'error' in packet:
                raise ValueError(packet['error'])
            return packet
        except (ValueError, OSError, queue.Empty) as error:
            close()
            raise OSError('WebSocket quote collection unavailable') from error
