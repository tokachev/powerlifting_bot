-- pwrbot schema. Timestamps are unix seconds (INTEGER). Weights are grams (INTEGER).
-- Run via db.connection.bootstrap() on first connect.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY,
    telegram_id     INTEGER NOT NULL UNIQUE,
    display_name    TEXT,
    created_at      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS workouts (
    id              INTEGER PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    performed_at    INTEGER NOT NULL,            -- unix seconds
    logged_at       INTEGER NOT NULL,
    source_text     TEXT NOT NULL,
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_workouts_user_time ON workouts(user_id, performed_at DESC);

CREATE TABLE IF NOT EXISTS exercise_entries (
    id               INTEGER PRIMARY KEY,
    workout_id       INTEGER NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
    position         INTEGER NOT NULL,
    raw_name         TEXT NOT NULL,
    canonical_name   TEXT,
    movement_pattern TEXT,                        -- push|pull|squat|hinge|carry|core|accessory|unknown
    UNIQUE(workout_id, position)
);
CREATE INDEX IF NOT EXISTS idx_exentry_workout ON exercise_entries(workout_id);
CREATE INDEX IF NOT EXISTS idx_exentry_canonical ON exercise_entries(canonical_name);

CREATE TABLE IF NOT EXISTS set_entries (
    id                INTEGER PRIMARY KEY,
    exercise_entry_id INTEGER NOT NULL REFERENCES exercise_entries(id) ON DELETE CASCADE,
    set_index         INTEGER NOT NULL,
    reps              INTEGER NOT NULL CHECK(reps >= 0),
    weight_g          INTEGER NOT NULL CHECK(weight_g >= 0),
    rpe               REAL,
    is_warmup         INTEGER NOT NULL DEFAULT 0 CHECK(is_warmup IN (0,1)),
    UNIQUE(exercise_entry_id, set_index)
);
CREATE INDEX IF NOT EXISTS idx_setentry_exentry ON set_entries(exercise_entry_id);

CREATE TABLE IF NOT EXISTS analysis_snapshots (
    id            INTEGER PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    window_days   INTEGER NOT NULL,
    computed_at   INTEGER NOT NULL,
    metrics_json  TEXT NOT NULL,
    flags_json    TEXT NOT NULL,
    explanation   TEXT
);
CREATE INDEX IF NOT EXISTS idx_snap_user_time ON analysis_snapshots(user_id, computed_at DESC);

CREATE TABLE IF NOT EXISTS body_weight (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    recorded_at INTEGER NOT NULL,            -- unix seconds, midnight UTC of the date
    weight_g    INTEGER NOT NULL CHECK(weight_g > 0),
    logged_at   INTEGER NOT NULL,            -- unix seconds, when the message was sent
    UNIQUE(user_id, recorded_at)
);
CREATE INDEX IF NOT EXISTS idx_bw_user_time ON body_weight(user_id, recorded_at DESC);

CREATE TABLE IF NOT EXISTS personal_records (
    id               INTEGER PRIMARY KEY,
    user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    canonical_name   TEXT NOT NULL,
    pr_type          TEXT NOT NULL CHECK(pr_type IN ('e1rm', 'weight', 'reps')),
    weight_g         INTEGER NOT NULL CHECK(weight_g >= 0),
    reps             INTEGER NOT NULL CHECK(reps >= 0),
    estimated_1rm_g  INTEGER NOT NULL CHECK(estimated_1rm_g >= 0),
    previous_value_g INTEGER,
    workout_id       INTEGER NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
    achieved_at      INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pr_user_exercise ON personal_records(user_id, canonical_name, achieved_at DESC);
CREATE INDEX IF NOT EXISTS idx_pr_user_time ON personal_records(user_id, achieved_at DESC);

CREATE TABLE IF NOT EXISTS video_analyses (
    id               INTEGER PRIMARY KEY,
    user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exercise_hint    TEXT,                            -- from video caption, nullable
    frame_count      INTEGER NOT NULL,
    duration_s       REAL NOT NULL,
    analysis_text    TEXT NOT NULL,                   -- LLM response
    model_used       TEXT NOT NULL,
    analyzed_at      INTEGER NOT NULL,               -- unix seconds
    telegram_file_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_vidanalysis_user_time
    ON video_analyses(user_id, analyzed_at DESC);
