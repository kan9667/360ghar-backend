CREATE TABLE IF NOT EXISTS flatmate_super_like_usage (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    used_on DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_flatmate_super_like_usage_target_day
        UNIQUE (user_id, target_user_id, used_on)
);

CREATE INDEX IF NOT EXISTS idx_flatmate_super_like_usage_user_day
    ON flatmate_super_like_usage (user_id, used_on);
