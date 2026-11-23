from src.constants.enums import MONITOR_METHOD
from src.models.database import connect
from src.services.monitoring import allocate_spending
from src.utils.passwords import hash_password

VERSIONS = [
    ('YA-01', '原版 · 图录用语', '青釉刻划纹执壶',
     '北宋中晚期青釉刻划纹执壶。器表以刻划法于坯体施饰，罩釉入窑，经高温还原焰烧成。可见细密纹样随釉层厚薄呈现深浅变化。', 16, 1.35),
    ('YA-02', '样张 · 易读改写', '青釉刻划纹执壶',
     '这把青釉壶烧制于北宋。\n工匠先在未烧的壶身上刻出花纹，再涂上青色釉料，把壶放进窑里烧。\n看一看花纹凹进去的地方，釉色更深。', 24, 1.60),
]
# Adjacent participant codes have opposite read orders. Each outcome occurs in both orders.
OUTCOME_TABLE = [(True, True)] * 16 + [(True, False)] * 2 + [(False, True)] * 12 + [(False, False)] * 4
# Interleave the outcome mix across enrollment order so the interim looks at the
# first 12 / 24 visitors each contain discordant pairs (the last two are the
# deliberate one-sided missing pairs PD-35 and PD-36).
OUTCOME_ORDER = [0, 18, 0, 30, 18, 0, 18, 0, 16, 0, 18, 0,
                 18, 30, 0, 18, 0, 0, 18, 0, 30, 18, 0, 18,
                 0, 16, 0, 18, 0, 18, 30, 0, 18, 0]
OUTCOMES = [OUTCOME_TABLE[i] for i in OUTCOME_ORDER] + [(None, True), (True, None)]
# Pre-registered monitoring: three looks at the first 12 / 24 / 36 enrolled
# visitors, a whole-batch quota of four charged evaluations, one-sided alpha 5%.
MONITOR_QUOTA = 4
MONITOR_ALPHA = 0.05
MONITOR_NS = [12, 24, 36]


def seed():
    with connect() as db:
        db.execute('SELECT pg_advisory_xact_lock(520301)')
        for username, name in [('analyst', '沈砚'), ('curator', '许禾'), ('viewer', '周简')]:
            if not db.execute('SELECT 1 FROM accounts WHERE username=%s', (username,)).fetchone():
                db.execute('INSERT INTO accounts VALUES (%s,%s,%s,%s)',
                           (username, name, username, hash_password('Proof5203!')))
        for version in VERSIONS:
            db.execute('''INSERT INTO label_versions(code,title,exhibit,body,type_pt,line_height)
                          VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (code) DO NOTHING''', version)
        study = db.execute('''INSERT INTO studies(code,title,station,reading_task,old_id,new_id,revision)
                              SELECT 'PD-1121', '青釉执壶展签复验', '常设展 · 二厅',
                                     '阅读后口述花纹是在上釉前还是上釉后刻出的，答「上釉前」记为成功。', a.id, b.id, 1
                              FROM label_versions a, label_versions b WHERE a.code='YA-01' AND b.code='YA-02'
                              ON CONFLICT (code) DO NOTHING RETURNING id''').fetchone()
        if study:
            with db.cursor() as cursor:
                cursor.executemany('''INSERT INTO reading_pairs(study_id, visitor_code, reading_order,
                                                          old_ok, new_ok, enrollment_seq)
                                      VALUES (%s,%s,%s,%s,%s,%s)''',
                                   [(study['id'], f'PD-{i:02}', 'old_first' if i % 2 else 'new_first', old, new, i)
                                    for i, (old, new) in enumerate(OUTCOMES, 1)])
            plan = db.execute('''INSERT INTO monitor_plans(study_id, test_quota, alpha_one_sided, method, created_by)
                                 VALUES (%s, %s, %s, %s, 'analyst')
                                 ON CONFLICT (study_id) DO NOTHING RETURNING id''',
                              (study['id'], MONITOR_QUOTA, MONITOR_ALPHA, MONITOR_METHOD)).fetchone()
            if plan:
                for ordinal, (cumulative, threshold) in enumerate(
                        zip(MONITOR_NS, allocate_spending(MONITOR_ALPHA, MONITOR_NS)), 1):
                    db.execute('''INSERT INTO monitor_looks(plan_id, ordinal, cumulative_n, alpha_threshold)
                                  VALUES (%s, %s, %s, %s)''', (plan['id'], ordinal, cumulative, threshold))
        for table in ('accounts', 'label_versions', 'studies', 'reading_pairs', 'analysis_runs', 'signoffs',
                      'monitor_plans', 'monitor_looks', 'look_evaluations', 'audit_events'):
            print(f'{table}={db.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]}')


if __name__ == '__main__':
    seed()
