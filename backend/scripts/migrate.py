from pathlib import Path

from src.models.database import connect

with connect() as db:
    db.execute('SELECT pg_advisory_xact_lock(5203)')
    db.execute('CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY)')
    for path in sorted(Path(__file__).resolve().parents[1].joinpath('migrations').glob('*.sql')):
        if not db.execute('SELECT 1 FROM schema_migrations WHERE name = %s', (path.name,)).fetchone():
            db.execute(path.read_text())
            db.execute('INSERT INTO schema_migrations VALUES (%s)', (path.name,))
