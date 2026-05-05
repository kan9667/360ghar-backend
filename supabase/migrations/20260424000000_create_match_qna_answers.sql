-- Create match_qna_answers table for post-match Q&A icebreakers.
-- Matches the MatchQnAAnswer ORM model in app/models/social.py.

CREATE TABLE IF NOT EXISTS match_qna_answers (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    match_id    BIGINT NOT NULL REFERENCES user_matches(id) ON DELETE CASCADE,
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    q1          TEXT,
    q2          VARCHAR(32),
    q3          TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index on match_id for lookups per match (matches the ORM index)
CREATE INDEX IF NOT EXISTS idx_match_qna_match ON match_qna_answers (match_id);

-- Prevent duplicate answers per user per match
CREATE UNIQUE INDEX IF NOT EXISTS idx_match_qna_unique_user_match
    ON match_qna_answers (match_id, user_id);
