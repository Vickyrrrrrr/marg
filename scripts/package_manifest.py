"""Record installer identity and SHA-256 checksums without publishing a release."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def main():
    mode = os.environ.get('BUILD_MODE')
    if mode not in ('fast', 'release-candidate'):
        raise ValueError('BUILD_MODE must be fast or release-candidate')
    files = sorted([*(ROOT / 'dist').glob('*.exe'), *(ROOT / 'dist').glob('*.dmg')])
    if not files:
        raise ValueError('No desktop installers were produced')
    manifest = {
        'version': json.loads((ROOT / 'package.json').read_text())['version'],
        'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'mode': mode, 'validation': 'full' if mode == 'release-candidate' else 'packaging-only',
        'platform': platform.system(), 'architecture': platform.machine(),
        'python': sys.version.split()[0],
        'node': subprocess.check_output(['node', '--version'], text=True).strip(),
        'run_id': os.environ.get('GITHUB_RUN_ID'), 'run_attempt': os.environ.get('GITHUB_RUN_ATTEMPT'),
        'signed': False, 'published': False,
        'installers': [{'filename': p.name, 'bytes': p.stat().st_size, 'sha256': digest(p)} for p in files],
    }
    metadata = ROOT / 'dist' / 'build-info.json'
    metadata.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    checksums = ROOT / 'dist' / 'SHA256SUMS.txt'
    checksums.write_text(''.join(f'{digest(p)}  {p.name}\n' for p in [*files, metadata]), encoding='utf-8')
    print('Installer manifest and checksums written for ' + manifest['commit'])


if __name__ == '__main__':
    main()
