import hashlib
import json

from fastapi import HTTPException
from psycopg.types.json import Jsonb

from src.constants.enums import METHOD, Decision, Role, RunStatus
from src.services.audit import record
from src.services.records import get_study, list_pairs

RUN_COLUMNS = '''r.id, r.study_id, r.revision, r.confidence, r.method, r.checksum, r.status, r.error,
                 r.requested_by, r.created_at, r.finished_at, s.signed_at, s.signed_by, s.decision, s.note'''
RUN_FROM = 'FROM analysis_runs r LEFT JOIN signoffs s ON s.run_id = r.id'


def snapshot_digest(snapshot):
    canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()


def enqueue(db, study_id, confidence, actor):
    study = get_study(db, study_id, lock=True)
    rows = list_pairs(db, study_id)
    if not rows:
        raise HTTPException(422, '请至少登记一条测读记录')
    data = {'study_id': study_id, 'revision': study['revision'], 'confidence': confidence, 'method': METHOD}
    versions = db.execute('''SELECT id, code, exhibit, title, body, type_pt, line_height::float AS line_height
                             FROM label_versions WHERE id IN (%s, %s) ORDER BY id''',
                          (study['old_id'], study['new_id'])).fetchall()
    snapshot = {**data, 'study_code': study['code'], 'study_title': study['title'], 'station': study['station'],
                'reading_task': study['reading_task'], 'old_id': study['old_id'], 'new_id': study['new_id'],
                'versions': versions, 'pairs': rows}
    checksum = snapshot_digest(snapshot)
    present = db.execute('''SELECT id FROM analysis_runs WHERE study_id = %s AND checksum = %s
                            AND status <> 'failed' ORDER BY id DESC LIMIT 1''', (study_id, checksum)).fetchone()
    if present:
        return present
    row = db.execute('''INSERT INTO analysis_runs(study_id, revision, confidence, method, snapshot, checksum, requested_by)
                        VALUES (%(study_id)s, %(revision)s, %(confidence)s, %(method)s,
                                %(snapshot)s, %(checksum)s, %(actor)s) RETURNING id''',
                     {**data, 'snapshot': Jsonb(snapshot), 'checksum': checksum, 'actor': actor}).fetchone()
    record(db, actor, 'analysis.queued', str(row['id']), {'checksum': checksum})
    return row


def list_runs(db, study_id, role):
    predicate = " AND s.decision = 'publish'" if role == Role.VIEWER else ''
    return db.execute(f'SELECT {RUN_COLUMNS} {RUN_FROM} WHERE r.study_id = %s{predicate} ORDER BY r.id DESC',
                      (study_id,)).fetchall()


def detail(db, run_id, role):
    row = db.execute(f'''SELECT {RUN_COLUMNS}, r.result, t.revision AS current_revision
                         {RUN_FROM} JOIN studies t ON t.id = r.study_id WHERE r.id = %s''', (run_id,)).fetchone()
    if not row or (role == Role.VIEWER and row['decision'] != Decision.PUBLISH):
        raise HTTPException(404, '复验运行不存在或尚未发布')
    return row


def review(db, run_id, decision, note, actor):
    run = detail(db, run_id, Role.CURATOR)
    # Lock in the same order as sample writes and read signoff again after acquiring it.
    study = get_study(db, run['study_id'], lock=True)
    run = detail(db, run_id, Role.CURATOR)
    if run['status'] != RunStatus.SUCCEEDED:
        raise HTTPException(409, '分析完成后才能会签')
    if study['revision'] != run['revision']:
        raise HTTPException(409, '样本已更新，请使用最新修订重新运行')
    if run['decision']:
        raise HTTPException(409, '该运行已有会签记录')
    if decision == Decision.PUBLISH:
        if not run['result']['complete']:
            raise HTTPException(409, '没有完整配对，只能退回复测')
        if db.execute('''SELECT 1 FROM signoffs s JOIN analysis_runs r ON r.id=s.run_id
                         WHERE r.study_id=%s AND r.revision=%s AND s.decision='publish' ''',
                      (study['id'], study['revision'])).fetchone():
            raise HTTPException(409, '本样本修订已有发布结论')
    db.execute('INSERT INTO signoffs(run_id, decision, note, signed_by) VALUES (%s,%s,%s,%s)',
               (run_id, decision, note, actor))
    record(db, actor, f'analysis.{decision}', str(run_id), {'note': note, 'revision': run['revision']})
    return detail(db, run_id, Role.CURATOR)


def export_data(db, run_id, role):
    run = detail(db, run_id, role)
    if run['status'] != RunStatus.SUCCEEDED:
        raise HTTPException(409, '分析完成后才能导出')
    snapshot = db.execute('SELECT snapshot FROM analysis_runs WHERE id = %s', (run_id,)).fetchone()['snapshot']
    run.pop('current_revision')
    return {**run, 'snapshot': snapshot}
