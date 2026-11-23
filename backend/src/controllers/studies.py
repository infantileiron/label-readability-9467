from src.models.database import cache
from src.config.settings import HEARTBEAT
from src.services.records import get_study, list_pairs
from src.services.runs import list_runs
from src.services.statistics import summarize


def study_detail(db, study_id, role):
    # A share lock keeps the revision and displayed rows consistent with concurrent writes.
    db.execute('SELECT id FROM studies WHERE id=%s FOR SHARE', (study_id,))
    study = get_study(db, study_id)
    pairs = list_pairs(db, study_id)
    return {**study, 'pairs': pairs, 'summary': summarize(pairs), 'runs': list_runs(db, study_id, role),
            'worker_online': bool(cache.exists(HEARTBEAT))}
