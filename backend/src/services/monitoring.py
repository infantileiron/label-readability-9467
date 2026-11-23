"""Pre-registered sequential looks for a paired label study.

The plan fixes, before the first reading, each look's cumulative headcount and
the whole-batch evaluation quota. The quota is a count of charged evaluations:
an evaluation of a look with its current cohort costs exactly one unit, repeated
or concurrent requests for the same cohort reuse the standing conclusion, and a
correction that invalidates a conclusion forces the recompute to cost another
unit. Spent units are never refunded, so the sum can never exceed the cap.

A look's cohort is the earliest-enrolled N visitors, regardless of later
corrections to their outcomes; a look with an incomplete pairing waits. The
significance threshold of a look is its pre-registered O'Brien–Fleming spending
increment, and the increments sum to the batch one-sided alpha, so the family-
wise error stays at or below the batch level even though looks are dependent.
"""

import hashlib
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from fastapi import HTTPException
from psycopg.types.json import Jsonb

from src.constants.enums import LOOK_LIMIT, MONITOR_METHOD, PAIR_LIMIT
from src.services.audit import record
from src.services.records import get_study
from src.services.statistics import analyze, obf_spend, one_sided_exact

QUANTUM = Decimal('0.0000000001')
COHORT_SQL = '''SELECT visitor_code, reading_order, old_ok, new_ok, enrolled_at, enrollment_seq
                FROM reading_pairs WHERE study_id = %s ORDER BY enrollment_seq'''
EVAL_COLUMNS = '''id, study_id, plan_id, look_id, ordinal, cumulative_n, alpha_threshold,
                  cohort_codes, cohort_fingerprint, cohort, result, method, quota_before,
                  quota_after, evaluated_by, created_at, invalidated_at, invalidated_reason,
                  invalidated_by'''


def _decimal(value):
    try:
        parsed = Decimal(str(value)).quantize(QUANTUM, ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise HTTPException(422, '请输入有效的单侧检验额度') from None
    if parsed <= 0 or parsed >= 1:
        raise HTTPException(422, '单侧检验额度须大于 0 且小于 1')
    return parsed


def allocate_spending(alpha, cumulative_ns):
    """O'Brien–Fleming spending increments for the pre-registered looks.

    Increments are cumulative spends at each look minus the previous one; they
    are positive and sum exactly to the batch alpha, so they form a valid alpha
    budget. Quantization is pushed to the final increment to keep the sum exact.
    """
    total_n = cumulative_ns[-1]
    cumulatives = [obf_spend(float(alpha), n, total_n) for n in cumulative_ns]
    thresholds, previous = [], Decimal(0)
    for spent in cumulatives[:-1]:
        value = Decimal(str(spent)).quantize(QUANTUM, ROUND_HALF_UP) - previous
        thresholds.append(value)
        previous += value
    thresholds.append(Decimal(str(alpha)) - previous)
    return thresholds


def _validate_ns(cumulative_ns):
    if not cumulative_ns or len(cumulative_ns) > LOOK_LIMIT:
        raise HTTPException(422, f'请登记 1 至 {LOOK_LIMIT} 个看点')
    if any(not 1 <= n <= PAIR_LIMIT for n in cumulative_ns):
        raise HTTPException(422, f'每个看点的累计人数须在 1 至 {PAIR_LIMIT} 之间')
    if any(later <= earlier for earlier, later in zip(cumulative_ns, cumulative_ns[1:])):
        raise HTTPException(422, '各看点的累计人数须严格递增')
    return cumulative_ns


def _fingerprint(cohort):
    canonical = json.dumps(cohort, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _cohort_json(rows):
    return [{'visitor_code': row['visitor_code'], 'reading_order': row['reading_order'],
             'old_ok': row['old_ok'], 'new_ok': row['new_ok']} for row in rows]


def _cohort_rows(db, study_id):
    return db.execute(COHORT_SQL, (study_id,)).fetchall()


def _plan(db, study_id, lock=False):
    return db.execute('SELECT * FROM monitor_plans WHERE study_id = %s' + (' FOR UPDATE' if lock else ''),
                      (study_id,)).fetchone()


def _looks(db, plan_id):
    return db.execute('''SELECT id, ordinal, cumulative_n, alpha_threshold::float AS alpha_threshold
                         FROM monitor_looks WHERE plan_id = %s ORDER BY ordinal''', (plan_id,)).fetchall()


def _evaluations(db, plan_id):
    return db.execute(f'SELECT {EVAL_COLUMNS} FROM look_evaluations WHERE plan_id = %s ORDER BY id',
                      (plan_id,)).fetchall()


def _number(value):
    return float(value) if value is not None else None


def _evaluation_json(row):
    data = dict(row)
    data['alpha_threshold'] = _number(data['alpha_threshold'])
    return data


def _spent(db, plan_id):
    return db.execute('SELECT count(*) AS n FROM look_evaluations WHERE plan_id = %s',
                      (plan_id,)).fetchone()['n']


def _missing(rows):
    return [row['visitor_code'] for row in rows if row['old_ok'] is None or row['new_ok'] is None]


def _look_view(look, rows, current, quota_left):
    cumulative = look['cumulative_n']
    enrolled = len(rows)
    if enrolled < cumulative:
        return {'status': 'enrolling', 'enrolled': enrolled, 'need': cumulative - enrolled,
                'missing': [], 'evaluation_id': None, 'decision': None, 'p_value': None}
    prefix = rows[:cumulative]
    missing = _missing(prefix)
    if missing:
        return {'status': 'blocked', 'enrolled': enrolled, 'need': 0, 'missing': missing,
                'evaluation_id': None, 'decision': None, 'p_value': None}
    if current:
        return {'status': 'evaluated', 'enrolled': enrolled, 'need': 0, 'missing': [],
                'evaluation_id': current['id'], 'decision': current['result']['decision'],
                'p_value': current['result']['p_value_one_sided']}
    if quota_left < 1:
        return {'status': 'unfunded', 'enrolled': enrolled, 'need': 0, 'missing': [],
                'evaluation_id': None, 'decision': None, 'p_value': None}
    return {'status': 'ready', 'enrolled': enrolled, 'need': 0, 'missing': [],
            'evaluation_id': None, 'decision': None, 'p_value': None}


def _recommendation(plan, views):
    if plan['locked_at'] is None:
        return {'action': 'unlocked', 'ordinal': None,
                'reason': '监看计划尚未锁定。确认累计人数与整批额度后锁定，开测后不再修改。'}
    decision = next((view for view in views if view['decision'] == 'stop'), None)
    if decision:
        last = views[-1]['ordinal'] if views else decision['ordinal']
        if decision['ordinal'] == last:
            return {'action': 'finish', 'ordinal': decision['ordinal'],
                    'reason': f'第 {decision["ordinal"]} 个看点样张显著更好，且已是最后一个看点，可收样。'}
        return {'action': 'stop', 'ordinal': decision['ordinal'],
                'reason': f'第 {decision["ordinal"]} 个看点样张显著更好，建议提前收样。'}
    # Looks are handled in enrollment order: the earliest look that still needs
    # action decides. A later look being ready does not unblock an earlier one.
    for view in views:
        if view['status'] == 'evaluated':
            continue
        if view['status'] == 'blocked':
            return {'action': 'wait', 'ordinal': view['ordinal'],
                    'reason': f'第 {view["ordinal"]} 个看点最早入组的前 {view["cumulative_n"]} 位中仍有缺测：'
                              f'{"、".join(view["missing"])}。配对没齐，先等。'}
        if view['status'] == 'enrolling':
            return {'action': 'wait', 'ordinal': view['ordinal'],
                    'reason': f'第 {view["ordinal"]} 个看点还需 {view["need"]} 位观众入组'
                              f'（已入组 {view["enrolled"]} 位）。配对没齐就等。'}
        if view['status'] == 'unfunded':
            return {'action': 'budget', 'ordinal': view['ordinal'],
                    'reason': f'整批检验额度已用完，第 {view["ordinal"]} 个看点无法再评估。'}
        return {'action': 'continue', 'ordinal': view['ordinal'],
                'reason': f'第 {view["ordinal"]} 个看点已可评估；至今未见样张显著更好，继续入组或补看。'}
    if views:
        return {'action': 'complete', 'ordinal': views[-1]['ordinal'],
                'reason': '计划内各看点均已评估，未见样张显著更好；可补看余下登记观众或按完整样本结束。'}
    return {'action': 'continue', 'ordinal': None, 'reason': '继续入组至下一看点。'}


def monitor_state(db, study_id):
    plan = _plan(db, study_id)
    if not plan:
        return {'plan': None, 'looks': [], 'evaluations': [],
                'budget': {'quota': None, 'spent': 0, 'remaining': None, 'exhausted': False},
                'recommendation': {'action': 'no_plan', 'ordinal': None,
                                   'reason': '尚未登记监看计划，请先定好各看点累计人数与整批检验额度。'}}
    looks = _looks(db, plan['id'])
    evaluations = _evaluations(db, plan['id'])
    rows = _cohort_rows(db, study_id)
    spent = len(evaluations)
    remaining = max(plan['test_quota'] - spent, 0)
    current = {row['look_id']: row for row in evaluations if row['invalidated_at'] is None}
    views = []
    for look in looks:
        view = _look_view(look, rows, current.get(look['id']), remaining)
        views.append({'id': look['id'], 'ordinal': look['ordinal'], 'cumulative_n': look['cumulative_n'],
                      'alpha_threshold': look['alpha_threshold'], **view})
    budget = {'quota': plan['test_quota'], 'spent': spent, 'remaining': remaining,
              'exhausted': remaining == 0,
              'alpha_one_sided': _number(plan['alpha_one_sided'])}
    return {'plan': {
        'id': plan['id'], 'study_id': plan['study_id'], 'test_quota': plan['test_quota'],
        'alpha_one_sided': _number(plan['alpha_one_sided']), 'method': plan['method'],
        'locked': plan['locked_at'] is not None, 'locked_at': plan['locked_at'],
        'locked_by': plan['locked_by'], 'created_by': plan['created_by'], 'created_at': plan['created_at'],
    }, 'looks': views, 'evaluations': [_evaluation_json(row) for row in evaluations],
        'budget': budget, 'recommendation': _recommendation(plan, views)}


def save_plan(db, study_id, test_quota, alpha_one_sided, cumulative_ns, actor):
    study = get_study(db, study_id, lock=True)
    alpha = _decimal(alpha_one_sided)
    if not 1 <= int(test_quota) <= 50:
        raise HTTPException(422, '整批检验额度须在 1 至 50 次之间')
    cumulative_ns = _validate_ns([int(n) for n in cumulative_ns])
    thresholds = allocate_spending(alpha, cumulative_ns)
    if any(value <= 0 for value in thresholds):
        raise HTTPException(422, '看点过多或额度过小，无法分配可用的检验门槛')
    plan = _plan(db, study_id, lock=True)
    if plan and plan['locked_at'] is not None:
        raise HTTPException(409, '计划已锁定，开测后不能修改累计人数或整批额度')
    if plan:
        db.execute('''UPDATE monitor_plans SET test_quota=%s, alpha_one_sided=%s, method=%s,
                      updated_by=%s, updated_at=now() WHERE id=%s''',
                   (int(test_quota), alpha, MONITOR_METHOD, actor, plan['id']))
        db.execute('DELETE FROM monitor_looks WHERE plan_id=%s', (plan['id'],))
        plan_id = plan['id']
    else:
        plan_id = db.execute('''INSERT INTO monitor_plans(study_id, test_quota, alpha_one_sided, method, created_by)
                                VALUES (%s, %s, %s, %s, %s) RETURNING id''',
                             (study_id, int(test_quota), alpha, MONITOR_METHOD, actor)).fetchone()['id']
    for ordinal, (cumulative, threshold) in enumerate(zip(cumulative_ns, thresholds), 1):
        db.execute('''INSERT INTO monitor_looks(plan_id, ordinal, cumulative_n, alpha_threshold)
                      VALUES (%s, %s, %s, %s)''', (plan_id, ordinal, cumulative, threshold))
    record(db, actor, 'monitor.plan.saved', study['code'],
           {'test_quota': int(test_quota), 'alpha_one_sided': str(alpha), 'cumulative_ns': cumulative_ns})
    return monitor_state(db, study_id)


def lock_plan(db, study_id, actor):
    study = get_study(db, study_id, lock=True)
    plan = _plan(db, study_id, lock=True)
    if not plan:
        raise HTTPException(409, '请先登记监看计划')
    if plan['locked_at'] is not None:
        return monitor_state(db, study_id)
    db.execute('UPDATE monitor_plans SET locked_by=%s, locked_at=now() WHERE id=%s', (actor, plan['id']))
    record(db, actor, 'monitor.plan.locked', study['code'],
           {'test_quota': plan['test_quota'], 'alpha_one_sided': str(plan['alpha_one_sided'])})
    return monitor_state(db, study_id)


def evaluate_look(db, study_id, look_id, actor):
    study = get_study(db, study_id, lock=True)
    plan = _plan(db, study_id, lock=True)
    if not plan:
        raise HTTPException(409, '请先登记监看计划')
    if plan['locked_at'] is None:
        raise HTTPException(409, '计划尚未锁定，开测前请先锁定累计人数与整批额度')
    look = db.execute('''SELECT id, ordinal, cumulative_n, alpha_threshold::float AS alpha_threshold
                         FROM monitor_looks WHERE id=%s AND plan_id=%s''',
                      (look_id, plan['id'])).fetchone()
    if not look:
        raise HTTPException(404, '看点不存在')

    rows = _cohort_rows(db, study_id)
    cumulative = look['cumulative_n']
    if len(rows) < cumulative:
        raise HTTPException(409, f'前 {cumulative} 位观众尚未全部入组（已入组 {len(rows)} 位），配对没齐就等')
    prefix = rows[:cumulative]
    missing = _missing(prefix)
    if missing:
        raise HTTPException(409, f'最早入组的前 {cumulative} 位中尚有缺测：{"、".join(missing)}，配对没齐就等')

    cohort = _cohort_json(prefix)
    fingerprint = _fingerprint(cohort)
    existing = db.execute(f'''SELECT {EVAL_COLUMNS} FROM look_evaluations
                              WHERE look_id=%s AND invalidated_at IS NULL FOR UPDATE''',
                          (look_id,)).fetchone()
    if existing:
        if existing['cohort_fingerprint'] == fingerprint:
            return _evaluation_json(existing)
    spent = _spent(db, plan['id'])
    if spent >= plan['test_quota']:
        # Do not void the standing conclusion unless the recompute can be paid for.
        raise HTTPException(409, '整批检验额度已用完，不能再评估；已用额度不能超过上限')
    if existing:
        db.execute('''UPDATE look_evaluations SET invalidated_at=now(), invalidated_reason=%s, invalidated_by=%s
                      WHERE id=%s''', ('已用样本更正', actor, existing['id']))
        record(db, actor, 'monitor.evaluation.invalidated', str(existing['id']),
               {'reason': '已用样本更正', 'ordinal': look['ordinal']})

    summary = analyze(prefix, 95)
    p_value = one_sided_exact(summary['new_only'], summary['discordant'])
    threshold = look['alpha_threshold']
    significant = (p_value is not None and p_value <= threshold
                   and summary['new_only'] > summary['old_only'])
    result = {key: summary[key] for key in (
        'total', 'complete', 'missing', 'both_ok', 'old_only', 'new_only', 'neither',
        'old_success', 'new_success', 'delta_pp', 'old_rate', 'new_rate', 'discordant',
        'new_win_share', 'missing_pairs', 'reading_orders')}
    result.update({'p_value_one_sided': p_value, 'alpha_threshold': threshold,
                   'significant': significant, 'decision': 'stop' if significant else 'continue'})
    row = db.execute(f'''INSERT INTO look_evaluations(study_id, plan_id, look_id, ordinal, cumulative_n,
                              alpha_threshold, cohort_codes, cohort_fingerprint, cohort, result, method,
                              quota_before, quota_after, evaluated_by)
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                         RETURNING {EVAL_COLUMNS}''',
                     (study_id, plan['id'], look_id, look['ordinal'], cumulative,
                      Decimal(str(threshold)), [item['visitor_code'] for item in cohort], fingerprint,
                      Jsonb(cohort), Jsonb(result), MONITOR_METHOD, spent, spent + 1, actor)).fetchone()
    record(db, actor, 'monitor.look.evaluated', f'{study["code"]}#{look["ordinal"]}',
           {'evaluation': row['id'], 'quota_before': spent, 'quota_after': spent + 1,
            'decision': result['decision'], 'p_value_one_sided': p_value,
            'cohort': [item['visitor_code'] for item in cohort]})
    return _evaluation_json(row)
