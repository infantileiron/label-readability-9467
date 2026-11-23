import logging
from time import sleep

from psycopg.types.json import Jsonb

from src.config.settings import HEARTBEAT
from src.constants.enums import METHOD
from src.models.database import cache, connect
from src.services.audit import record
from src.services.runs import snapshot_digest
from src.services.statistics import analyze

logger = logging.getLogger(__name__)


def execute_one():
    with connect() as db:
        # A killed worker rolls back this transaction and releases the queued row for retry.
        run = db.execute('''SELECT * FROM analysis_runs WHERE status='queued'
                            ORDER BY id LIMIT 1 FOR UPDATE SKIP LOCKED''').fetchone()
        if not run:
            return False
        try:
            snapshot = run['snapshot']
            if snapshot_digest(snapshot) != run['checksum'] or run['method'] != METHOD:
                raise ValueError('invalid input checksum or method')
            result = analyze(snapshot['pairs'], run['confidence'])
        except Exception:
            logger.exception('Run %s failed', run['id'])
            db.execute("UPDATE analysis_runs SET status='failed', error=%s, finished_at=now() WHERE id=%s",
                       ('分析失败，请检查样本后重新运行', run['id']))
            record(db, 'worker', 'analysis.failed', str(run['id']))
        else:
            db.execute("UPDATE analysis_runs SET status='succeeded', result=%s, finished_at=now() WHERE id=%s",
                       (Jsonb(result), run['id']))
            record(db, 'worker', 'analysis.completed', str(run['id']), {'complete': result['complete']})
    return True


def main():
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            worked = execute_one()
            cache.set(HEARTBEAT, 'ready', ex=8)
            if not worked:
                sleep(0.65)
        except Exception:
            logger.exception('Worker poll failed')
            sleep(2)


if __name__ == '__main__':
    main()
