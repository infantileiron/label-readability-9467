from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from redis import Redis

from src.config.settings import DATABASE_URL, REDIS_URL

cache = Redis.from_url(REDIS_URL, socket_connect_timeout=2, socket_timeout=2)


@contextmanager
def connect():
    with psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=3) as conn:
        yield conn
