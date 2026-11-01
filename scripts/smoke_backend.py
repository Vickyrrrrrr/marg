"""Exercise the packaged backend and close every process/handle before cleanup."""
import http.cookiejar
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[1]
EXECUTABLE = ROOT / 'backend-dist' / 'ledgerly-backend' / (
    'ledgerly-backend.exe' if sys.platform == 'win32' else 'ledgerly-backend'
)


def stop(process):
    if process.poll() is None:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


@contextmanager
def running_backend(data):
    log = Path(data) / 'startup.log'
    # Keep ownership of the log even when Popen/startup fails. The onedir build
    # runs the service directly, so terminating it cannot leave a onefile child
    # holding this log or the database open on Windows.
    with log.open('w', encoding='utf-8') as output:
        process = subprocess.Popen(
            [str(EXECUTABLE)],
            env={**os.environ, 'PORT': '0', 'LEDGERLY_DATA_DIR': data},
            stdout=output,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                text = log.read_text(encoding='utf-8', errors='replace')
                if process.poll() is not None:
                    raise RuntimeError('Packaged backend exited during startup:\n' + text)
                ready = next((line for line in text.splitlines() if line.startswith('LEDGERLY_READY=')), None)
                if ready:
                    yield ready.split('=', 1)[1]
                    return
                time.sleep(.1)
            raise RuntimeError('Packaged backend startup timed out:\n' + text)
        finally:
            stop(process)


def request(opener, url, payload=None):
    headers = {'Content-Type': 'application/json'} if payload is not None else {}
    body = json.dumps(payload).encode() if payload is not None else None
    with opener.open(urllib.request.Request(url, data=body, headers=headers), timeout=10) as response:
        return json.load(response)


def main():
    if not EXECUTABLE.is_file():
        raise FileNotFoundError('Build the backend first: ' + str(EXECUTABLE))
    with tempfile.TemporaryDirectory() as data:
        credentials = dict(username='smoke-owner', password='temporary-smoke-password')
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        with running_backend(data) as url:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status != 200:
                    raise RuntimeError('Packaged HTTP assets are unavailable')
            request(opener, url + '/api/bootstrap', credentials)
            result = request(opener, url + '/api/products', dict(
                name='Packaging check', batch='SMOKE', price=112, tax=12,
                tax_inclusive=True, mrp=112, pack_size=10,
            ))
            if result['products'][0]['name'] != 'Packaging check':
                raise RuntimeError('Packaged backend did not save the product')
        with running_backend(data) as url:
            request(opener, url + '/api/login', credentials)
            result = request(opener, url + '/api/state')
            if len(result['products']) != 1 or result['products'][0]['name'] != 'Packaging check':
                raise RuntimeError('Database did not survive restart')
    print('Packaged backend startup, assets, persistence and cleanup passed')


if __name__ == '__main__':
    main()
