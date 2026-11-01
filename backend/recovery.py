"""Validated local recovery; restore is serialized with every API request."""
import base64
import hashlib
import hmac
import re
import sqlite3
import time
from contextlib import closing
from pathlib import Path
import security

MAX_BYTES = 64 * 1024 * 1024
NAME = re.compile(r'ledgerly-[A-Za-z0-9-]+\.sqlite3\Z')


def initialize(c):
    c.execute('CREATE TABLE IF NOT EXISTS recovery_event(id INTEGER PRIMARY KEY,actor TEXT NOT NULL,source TEXT NOT NULL,digest TEXT NOT NULL,created_at INTEGER NOT NULL)')


def location(db, name):
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise ValueError('Select a database backup from the list')
    path = db.parent / 'backups' / name
    if path.is_symlink() or not path.is_file():
        raise ValueError('Backup file is unavailable')
    return path


def schema(c):
    return sorted((r[0], r[1], r[2]) for r in c.execute("SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'"))


def inspect(db, name):
    path = location(db, name)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError('Backup exceeds the 64 MB recovery limit')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    try:
        with closing(sqlite3.connect(db)) as current, closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as source:
            source.row_factory = sqlite3.Row
            source.execute('PRAGMA trusted_schema=OFF')
            if source.execute('PRAGMA user_version').fetchone()[0] != current.execute('PRAGMA user_version').fetchone()[0] or schema(source) != schema(current):
                raise ValueError('Backup schema differs from this application; use a backup made with this version')
            if [r[0] for r in source.execute('PRAGMA integrity_check')] != ['ok'] or source.execute('PRAGMA foreign_key_check').fetchone():
                raise ValueError('Backup integrity or reference check failed')
            if not source.execute("SELECT 1 FROM operator WHERE active=1 AND role='admin'").fetchone():
                raise ValueError('Backup must contain an active administrator')
            if source.execute('SELECT document FROM journal GROUP BY document HAVING SUM(debit-credit)!=0').fetchone():
                raise ValueError('Backup contains an unbalanced journal')
            if source.execute('SELECT 1 FROM products WHERE stock<0 OR quarantine<0').fetchone():
                raise ValueError('Backup contains invalid stock')
            company = source.execute('SELECT name,year_start,year_end FROM company').fetchone()
            return {'filename': name, 'sha256': digest, 'bytes': path.stat().st_size,
                    'company': dict(company) if company else None,
                    'documents': source.execute('SELECT COUNT(*) FROM documents').fetchone()[0],
                    'products': source.execute('SELECT COUNT(*) FROM products').fetchone()[0],
                    'operators': source.execute('SELECT COUNT(*) FROM operator').fetchone()[0]}
    except sqlite3.DatabaseError as e:
        raise ValueError('Backup is not a readable Ledgerly database') from e


def listing(db):
    folder = db.parent / 'backups'
    if not folder.exists():
        return []
    return [{'filename': p.name, 'bytes': p.stat().st_size} for p in sorted(folder.glob('ledgerly-*.sqlite3'), reverse=True) if NAME.fullmatch(p.name) and not p.is_symlink()]


def import_file(db, d):
    data = d.get('content')
    if not isinstance(data, str) or len(data) > (MAX_BYTES + 2) // 3 * 4:
        raise ValueError('Select a SQLite backup up to 64 MB')
    try:
        raw = base64.b64decode(data, validate=True)
    except ValueError as e:
        raise ValueError('Invalid backup encoding') from e
    if len(raw) > MAX_BYTES or not raw.startswith(b'SQLite format 3\x00'):
        raise ValueError('Select a SQLite backup up to 64 MB')
    import secrets
    folder = db.parent / 'backups'
    folder.mkdir(exist_ok=True)
    path = folder / ('ledgerly-import-' + secrets.token_hex(12) + '.sqlite3')
    try:
        path.write_bytes(raw)
        return inspect(db, path.name)
    except Exception:
        path.unlink(missing_ok=True)
        raise


def restore(db, d, actor, backup):
    if not actor or actor['role'] != 'admin':
        raise PermissionError('Only an administrator may restore the database')
    # Reauthenticate against the live database, before its credentials are replaced.
    with closing(sqlite3.connect(db)) as c:
        c.row_factory = sqlite3.Row
        user = c.execute('SELECT * FROM operator WHERE id=? AND active=1 AND role=?', (actor['id'], 'admin')).fetchone()
        password = d.get('password')
        if not user or not isinstance(password, str) or len(password) > 256 or not hmac.compare_digest(security.password_hash(password, user['salt']), user['password_hash']):
            raise ValueError('Current administrator password is required')
        company = c.execute('SELECT name FROM company').fetchone()
        expected = company['name'] if company else 'RESTORE'
        if d.get('confirm') != expected:
            raise ValueError('Enter the current business name exactly to confirm replacement')
    info = inspect(db, d.get('filename'))
    if not isinstance(d.get('sha256'), str) or not hmac.compare_digest(info['sha256'], d['sha256']):
        raise ValueError('Backup changed; inspect it again before restoring')
    safety = backup()
    path = location(db, info['filename'])
    # All handles close before returning, including on Windows. The SQLite backup
    # API replaces the destination in one database transaction, preserving atomicity.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='ledgerly-restore-') as folder:
        staged = Path(folder) / 'restore.sqlite3'
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as source, closing(sqlite3.connect(staged)) as clean:
            source.backup(clean)
            with clean:
                clean.execute('DELETE FROM session')
                clean.execute('INSERT INTO recovery_event(actor,source,digest,created_at) VALUES(?,?,?,?)', (actor['username'], info['filename'], info['sha256'], int(time.time())))
            with closing(sqlite3.connect(db)) as target:
                clean.backup(target)
    return {'ok': True, 'safety_backup': safety['filename'], 'restored': info['filename'], 'sign_in_required': True}
