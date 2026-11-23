CREATE TABLE accounts (
    username text PRIMARY KEY,
    display_name text NOT NULL,
    role text NOT NULL CHECK (role IN ('analyst', 'curator', 'viewer')),
    password_hash text NOT NULL
);

CREATE TABLE label_versions (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code text NOT NULL UNIQUE,
    title text NOT NULL,
    exhibit text NOT NULL,
    body text NOT NULL,
    type_pt smallint NOT NULL CHECK (type_pt BETWEEN 10 AND 72),
    line_height numeric(3,2) NOT NULL CHECK (line_height BETWEEN 1 AND 3),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE studies (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code text NOT NULL UNIQUE,
    title text NOT NULL,
    station text NOT NULL,
    reading_task text NOT NULL,
    old_id bigint NOT NULL REFERENCES label_versions(id),
    new_id bigint NOT NULL REFERENCES label_versions(id),
    revision int NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (old_id <> new_id)
);

CREATE TABLE reading_pairs (
    study_id bigint NOT NULL REFERENCES studies(id),
    visitor_code text NOT NULL,
    reading_order text NOT NULL CHECK (reading_order IN ('old_first', 'new_first')),
    old_ok boolean,
    new_ok boolean,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (study_id, visitor_code)
);

CREATE TABLE analysis_runs (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    study_id bigint NOT NULL REFERENCES studies(id),
    revision int NOT NULL,
    confidence smallint NOT NULL CHECK (confidence IN (90, 95, 99)),
    method text NOT NULL,
    snapshot jsonb NOT NULL,
    checksum text NOT NULL,
    status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'succeeded', 'failed')),
    result jsonb,
    error text,
    requested_by text NOT NULL REFERENCES accounts(username),
    created_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    CHECK ((status = 'queued' AND finished_at IS NULL) OR (status <> 'queued' AND finished_at IS NOT NULL))
);
CREATE INDEX analysis_queue ON analysis_runs(id) WHERE status = 'queued';
CREATE INDEX analysis_study ON analysis_runs(study_id, id DESC);

CREATE TABLE signoffs (
    run_id bigint PRIMARY KEY REFERENCES analysis_runs(id),
    decision text NOT NULL CHECK (decision IN ('publish', 'revise')),
    note text NOT NULL,
    signed_by text NOT NULL REFERENCES accounts(username),
    signed_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE audit_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor text NOT NULL,
    action text NOT NULL,
    target text NOT NULL,
    detail jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);
