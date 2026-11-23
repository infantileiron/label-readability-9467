-- Enrollment order is independent of later corrections: the earliest N enrolled
-- visitors form each interim look cohort, and a corrected row keeps its place.
-- A per-study sequence makes the order deterministic even for rows inserted in
-- the same transaction.
ALTER TABLE reading_pairs
    ADD COLUMN enrolled_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    ADD COLUMN enrollment_seq bigint;
WITH ordered AS (
    SELECT study_id, visitor_code,
           row_number() OVER (PARTITION BY study_id ORDER BY enrolled_at, visitor_code) AS seq
    FROM reading_pairs
)
UPDATE reading_pairs p SET enrollment_seq = ordered.seq
FROM ordered WHERE p.study_id = ordered.study_id AND p.visitor_code = ordered.visitor_code;
ALTER TABLE reading_pairs
    ALTER COLUMN enrollment_seq SET NOT NULL,
    ADD CONSTRAINT reading_pairs_enrollment_seq_positive CHECK (enrollment_seq > 0);
CREATE UNIQUE INDEX reading_pairs_enrollment ON reading_pairs (study_id, enrollment_seq);

-- One pre-registered monitoring plan per study. Editable until locked_at is set.
-- test_quota is the whole-batch evaluation allowance; alpha_one_sided is the
-- one-sided type-I error of the monitoring scheme, spent across looks.
CREATE TABLE monitor_plans (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    study_id bigint NOT NULL UNIQUE REFERENCES studies(id),
    test_quota smallint NOT NULL CHECK (test_quota BETWEEN 1 AND 50),
    alpha_one_sided numeric(12,10) NOT NULL CHECK (alpha_one_sided > 0 AND alpha_one_sided < 1),
    method text NOT NULL,
    created_by text NOT NULL REFERENCES accounts(username),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_by text REFERENCES accounts(username),
    updated_at timestamptz NOT NULL DEFAULT now(),
    locked_by text REFERENCES accounts(username),
    locked_at timestamptz
);

-- Each look fixes its cumulative headcount before start. alpha_threshold is the
-- one-sided spending increment this look may use to declare "significantly better".
CREATE TABLE monitor_looks (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    plan_id bigint NOT NULL REFERENCES monitor_plans(id) ON DELETE CASCADE,
    ordinal smallint NOT NULL CHECK (ordinal BETWEEN 1 AND 20),
    cumulative_n int NOT NULL CHECK (cumulative_n BETWEEN 1 AND 1000),
    alpha_threshold numeric(12,10) NOT NULL CHECK (alpha_threshold > 0 AND alpha_threshold < 1),
    UNIQUE (plan_id, ordinal),
    UNIQUE (plan_id, cumulative_n)
);

-- Every evaluation keeps its own input cohort, result and charge. Charges are
-- never refunded; after a correction invalidates a conclusion the recompute
-- consumes one more unit of the batch quota.
CREATE TABLE look_evaluations (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    study_id bigint NOT NULL REFERENCES studies(id),
    plan_id bigint NOT NULL REFERENCES monitor_plans(id),
    look_id bigint NOT NULL REFERENCES monitor_looks(id),
    ordinal smallint NOT NULL,
    cumulative_n int NOT NULL,
    alpha_threshold numeric(12,10) NOT NULL CHECK (alpha_threshold > 0 AND alpha_threshold < 1),
    cohort_codes text[] NOT NULL,
    cohort_fingerprint text NOT NULL,
    cohort jsonb NOT NULL,
    result jsonb NOT NULL,
    method text NOT NULL,
    quota_before smallint NOT NULL CHECK (quota_before >= 0),
    quota_after smallint NOT NULL CHECK (quota_after = quota_before + 1),
    evaluated_by text NOT NULL REFERENCES accounts(username),
    created_at timestamptz NOT NULL DEFAULT now(),
    invalidated_at timestamptz,
    invalidated_reason text,
    invalidated_by text REFERENCES accounts(username)
);

-- A look has at most one standing conclusion. Concurrent or repeated requests
-- for the same (look, cohort) reuse it instead of charging again. A correction
-- must invalidate it before a fresh charge can create the replacement.
CREATE UNIQUE INDEX look_evaluation_current ON look_evaluations (look_id) WHERE invalidated_at IS NULL;
CREATE INDEX look_evaluation_study ON look_evaluations (study_id, id DESC);
CREATE INDEX look_evaluation_cohort ON look_evaluations USING GIN (cohort_codes);
