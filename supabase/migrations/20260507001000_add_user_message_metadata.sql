ALTER TABLE user_messages
    ADD COLUMN IF NOT EXISTS metadata JSONB;
