-- Data-only tracking for FlatMates smart recommendation training.
-- Stores per-session profile view duration from the mobile swipe deck.

CREATE TABLE IF NOT EXISTS flatmate_profile_view_events (
    id                   BIGSERIAL PRIMARY KEY,
    viewer_user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    viewed_user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    context_property_id  INTEGER REFERENCES properties(id) ON DELETE SET NULL,
    source               VARCHAR(64) NOT NULL DEFAULT 'swipe_deck',
    duration_seconds     INTEGER NOT NULL DEFAULT 0,
    scroll_depth_percent INTEGER,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_flatmate_profile_views_viewer
    ON flatmate_profile_view_events (viewer_user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_flatmate_profile_views_viewed
    ON flatmate_profile_view_events (viewed_user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_flatmate_profile_views_property
    ON flatmate_profile_view_events (context_property_id, created_at DESC);
