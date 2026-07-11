-- Telemetry archive: narrow hypertable — schema never changes as the
-- telemetry dictionary grows, and it matches the one query shape the
-- OpenMCT historical provider needs (parameter + time range).
CREATE TABLE telemetry (
    time        TIMESTAMPTZ       NOT NULL,
    parameter   TEXT              NOT NULL,
    value       DOUBLE PRECISION,
    value_text  TEXT,
    alarm       TEXT              NOT NULL DEFAULT 'NOMINAL'
);

SELECT create_hypertable('telemetry', 'time');

CREATE INDEX idx_telemetry_param_time ON telemetry (parameter, time DESC);
