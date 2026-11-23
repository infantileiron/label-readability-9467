from fastapi import HTTPException

from src.constants.enums import PAIR_LIMIT
from src.services.audit import record

PAIR_FIELDS = 'visitor_code, reading_order, old_ok, new_ok'


def get_study(db, study_id, lock=False):
    sql = 'SELECT * FROM studies WHERE id = %s'
    study = db.execute(sql + (' FOR UPDATE' if lock else ''), (study_id,)).fetchone()
    if not study:
        raise HTTPException(404, '复验批次不存在')
    return study


def list_pairs(db, study_id):
    return db.execute(f'SELECT {PAIR_FIELDS} FROM reading_pairs WHERE study_id = %s ORDER BY visitor_code',
                      (study_id,)).fetchall()


def add_version(db, data, actor):
    row = db.execute('''INSERT INTO label_versions(code, title, exhibit, body, type_pt, line_height)
                        VALUES (%(code)s, %(title)s, %(exhibit)s, %(body)s, %(type_pt)s, %(line_height)s)
                        ON CONFLICT (code) DO NOTHING RETURNING *''', data).fetchone()
    if not row:
        raise HTTPException(409, '展签版本编号已存在')
    record(db, actor, 'version.created', row['code'])
    return row


def add_study(db, data, actor):
    versions = db.execute('SELECT id, exhibit FROM label_versions WHERE id IN (%s, %s)',
                          (data['old_id'], data['new_id'])).fetchall()
    if len(versions) != 2 or versions[0]['exhibit'] != versions[1]['exhibit']:
        raise HTTPException(422, '请选择同一展品的两个已登记版本')
    row = db.execute('''INSERT INTO studies(code, title, station, reading_task, old_id, new_id)
                        VALUES (%(code)s, %(title)s, %(station)s, %(reading_task)s, %(old_id)s, %(new_id)s)
                        ON CONFLICT (code) DO NOTHING RETURNING *''', data).fetchone()
    if not row:
        raise HTTPException(409, '复验批次编号已存在')
    record(db, actor, 'study.created', row['code'])
    return row


def save_pair(db, study_id, visitor_code, data, actor, expected_revision):
    study = get_study(db, study_id, lock=True)
    if study['revision'] != expected_revision:
        raise HTTPException(409, '批次已更新，请刷新配对记录后再提交')
    existing = db.execute(f'SELECT {PAIR_FIELDS} FROM reading_pairs WHERE study_id=%s AND visitor_code=%s',
                          (study_id, visitor_code)).fetchone()
    row = {'visitor_code': visitor_code, **data}
    if row == existing:
        return {**row, 'revision': study['revision']}
    if existing is None:
        count = db.execute('SELECT count(*) AS n FROM reading_pairs WHERE study_id = %s', (study_id,)).fetchone()
        if count['n'] >= PAIR_LIMIT:
            raise HTTPException(409, f'每批最多登记 {PAIR_LIMIT} 对')
    db.execute('''INSERT INTO reading_pairs(study_id, visitor_code, reading_order, old_ok, new_ok)
                  VALUES (%(study_id)s, %(visitor_code)s, %(reading_order)s, %(old_ok)s, %(new_ok)s)
                  ON CONFLICT (study_id, visitor_code) DO UPDATE SET
                    reading_order=excluded.reading_order, old_ok=excluded.old_ok,
                    new_ok=excluded.new_ok, updated_at=now()''', {'study_id': study_id, **row})
    revision = db.execute('UPDATE studies SET revision=revision+1 WHERE id=%s RETURNING revision',
                          (study_id,)).fetchone()['revision']
    record(db, actor, 'pair.saved', f'{study["code"]}/{visitor_code}',
           {'revision': revision, 'before': existing, 'after': row})
    return {**row, 'revision': revision}
