from psycopg.types.json import Jsonb


def record(db, actor, action, target, detail=None):
    db.execute('INSERT INTO audit_events(actor, action, target, detail) VALUES (%s, %s, %s, %s)',
               (actor, action, target, Jsonb(detail or {})))
