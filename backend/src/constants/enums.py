from enum import StrEnum


class Role(StrEnum):
    ANALYST = 'analyst'
    CURATOR = 'curator'
    VIEWER = 'viewer'


class Order(StrEnum):
    OLD_FIRST = 'old_first'
    NEW_FIRST = 'new_first'


class RunStatus(StrEnum):
    QUEUED = 'queued'
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'


class Decision(StrEnum):
    PUBLISH = 'publish'
    REVISE = 'revise'


METHOD = 'paired-exact-v1'
PAIR_LIMIT = 1000
