import os
from decimal import Decimal

import psycopg
import pytest
from psycopg.rows import dict_row

from src.services.monitoring import (allocate_spending, evaluate_look, lock_plan, monitor_state,
                                     save_plan)
from src.services.records import save_pair
from src.services.statistics import one_sided_exact, obf_spend

DATABASE_URL = os.environ.get('DATABASE_URL')
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='DATABASE_URL 未配置，跳过数据库测试')


@pytest.fixture()
def db():
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        yield conn
        conn.rollback()


@pytest.fixture()
def study(db):
    """A disposable study with no pairs, rolled back after the test."""
    old = db.execute("INSERT INTO label_versions(code,title,exhibit,body,type_pt,line_height) "
                     "VALUES ('T-OLD','旧','测试展品','测试旧版文案内容',16,1.35) RETURNING id").fetchone()['id']
    new = db.execute("INSERT INTO label_versions(code,title,exhibit,body,type_pt,line_height) "
                     "VALUES ('T-NEW','新','测试展品','测试新版文案内容',24,1.60) RETURNING id").fetchone()['id']
    row = db.execute("INSERT INTO studies(code,title,station,reading_task,old_id,new_id) "
                     "VALUES ('T-STUDY','测试批次','测试厅','测试判定题',%s,%s) RETURNING id",
                     (old, new)).fetchone()
    yield row['id']
    db.execute('DELETE FROM look_evaluations WHERE study_id=%s', (row['id'],))
    db.execute('DELETE FROM monitor_looks USING monitor_plans p '
               'WHERE monitor_looks.plan_id=p.id AND p.study_id=%s', (row['id'],))
    db.execute('DELETE FROM monitor_plans WHERE study_id=%s', (row['id'],))
    db.execute('DELETE FROM reading_pairs WHERE study_id=%s', (row['id'],))
    db.execute('DELETE FROM studies WHERE id=%s', (row['id'],))


def enroll(db, study_id, visitor, old, new, actor='analyst'):
    revision = db.execute('SELECT revision FROM studies WHERE id=%s', (study_id,)).fetchone()['revision']
    save_pair(db, study_id, visitor, {'reading_order': 'old_first', 'old_ok': old, 'new_ok': new},
              actor, revision)


def plan(db, study_id, quota=4, alpha=0.05, ns=(4, 8)):
    return save_plan(db, study_id, quota, alpha, list(ns), 'analyst')


def test_spending_increments_sum_to_alpha():
    increments = allocate_spending(Decimal('0.05'), [12, 24, 36])
    assert sum(increments) == Decimal('0.0500000000')
    assert all(value > 0 for value in increments)
    assert [round(float(v), 6) for v in increments] == [0.002193, 0.019784, 0.028023]


def test_one_sided_exact_matches_binomial_tail():
    # 12 of 14 discordant wins for the new label.
    assert one_sided_exact(12, 14) == pytest.approx(0.0064697265625)
    assert one_sided_exact(0, 5) == pytest.approx(1.0)
    assert one_sided_exact(5, 5) == pytest.approx(1 / 32)


def test_obf_spending_is_monotone_and_ends_at_alpha():
    values = [obf_spend(0.05, n, 40) for n in (5, 10, 20, 40)]
    assert values == sorted(values)
    assert values[-1] == pytest.approx(0.05)


def test_look_waits_until_pairing_complete(db, study):
    plan(db, study, ns=(2, 4))
    lock_plan(db, study, 'analyst')
    enroll(db, study, 'T-01', True, True)
    enroll(db, study, 'T-02', True, None)
    state = monitor_state(db, study)
    look = state['looks'][0]
    assert look['status'] == 'blocked'
    assert look['missing'] == ['T-02']
    assert state['recommendation']['action'] == 'wait'
    with pytest.raises(Exception):
        evaluate_look(db, study, look['id'], 'analyst')
    assert state['budget']['spent'] == 0


def test_evaluation_charges_once_and_reuses_same_cohort(db, study):
    plan(db, study)
    lock_plan(db, study, 'analyst')
    for i in range(1, 5):
        enroll(db, study, f'T-0{i}', True, True)
    look = monitor_state(db, study)['looks'][0]
    first = evaluate_look(db, study, look['id'], 'analyst')
    second = evaluate_look(db, study, look['id'], 'analyst')
    assert first['id'] == second['id']
    assert monitor_state(db, study)['budget']['spent'] == 1


def test_new_enrollment_does_not_invalidate_looks(db, study):
    plan(db, study)
    lock_plan(db, study, 'analyst')
    for i in range(1, 5):
        enroll(db, study, f'T-0{i}', True, True)
    look = monitor_state(db, study)['looks'][0]
    evaluate_look(db, study, look['id'], 'analyst')
    enroll(db, study, 'T-99', True, True)
    state = monitor_state(db, study)
    assert state['budget']['spent'] == 1
    assert state['looks'][0]['decision'] == 'continue'


def test_correction_invalidates_and_recompute_charges_again(db, study):
    plan(db, study)
    lock_plan(db, study, 'analyst')
    for i in range(1, 5):
        enroll(db, study, f'T-0{i}', True, True)
    look = monitor_state(db, study)['looks'][0]
    evaluate_look(db, study, look['id'], 'analyst')
    enroll(db, study, 'T-02', False, True)  # correct a used sample
    state = monitor_state(db, study)
    assert state['looks'][0]['decision'] is None
    assert all(row['invalidated_at'] for row in state['evaluations'])
    assert state['budget']['spent'] == 1
    evaluate_look(db, study, look['id'], 'analyst')
    assert monitor_state(db, study)['budget']['spent'] == 2


def test_quota_cap_blocks_further_evaluation(db, study):
    plan(db, study, quota=1)
    lock_plan(db, study, 'analyst')
    for i in range(1, 9):
        enroll(db, study, f'T-0{i}', True, True)
    look = monitor_state(db, study)['looks'][0]
    evaluate_look(db, study, look['id'], 'analyst')
    second = monitor_state(db, study)['looks'][1]
    assert second['status'] == 'unfunded'
    with pytest.raises(Exception):
        evaluate_look(db, study, second['id'], 'analyst')
    assert monitor_state(db, study)['budget']['spent'] == 1


def test_plan_is_locked_after_start(db, study):
    plan(db, study)
    lock_plan(db, study, 'analyst')
    with pytest.raises(Exception):
        plan(db, study, quota=9)


def test_significant_improvement_recommends_early_stop(db, study):
    plan(db, study, ns=(6,))
    lock_plan(db, study, 'analyst')
    outcomes = [(False, True)] * 6
    for i, (old, new) in enumerate(outcomes, 1):
        enroll(db, study, f'T-0{i}', old, new)
    look = monitor_state(db, study)['looks'][0]
    evaluate_look(db, study, look['id'], 'analyst')
    state = monitor_state(db, study)
    assert state['looks'][0]['decision'] == 'stop'
    assert state['recommendation']['action'] == 'finish'


def test_unpaid_recompute_keeps_standing_conclusion(db, study):
    plan(db, study, quota=1)
    lock_plan(db, study, 'analyst')
    for i in range(1, 5):
        enroll(db, study, f'T-0{i}', True, True)
    look = monitor_state(db, study)['looks'][0]
    evaluate_look(db, study, look['id'], 'analyst')
    # Correction voids the conclusion through the pair write, but with no quota
    # left the recompute is refused and the stored evaluation stays voided.
    enroll(db, study, 'T-03', False, True)
    state = monitor_state(db, study)
    assert state['looks'][0]['decision'] is None
    with pytest.raises(Exception):
        evaluate_look(db, study, look['id'], 'analyst')
    assert monitor_state(db, study)['budget']['spent'] == 1
