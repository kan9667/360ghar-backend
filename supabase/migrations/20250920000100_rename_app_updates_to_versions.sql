BEGIN;

-- Rename app_updates table to app_versions and align related database objects
ALTER TABLE app_updates RENAME TO app_versions;
ALTER SEQUENCE app_updates_id_seq RENAME TO app_versions_id_seq;

ALTER INDEX idx_app_updates_platform RENAME TO idx_app_versions_platform;
ALTER INDEX idx_app_updates_is_active RENAME TO idx_app_versions_is_active;
ALTER INDEX idx_app_updates_created_at RENAME TO idx_app_versions_created_at;

ALTER FUNCTION update_app_updates_updated_at() RENAME TO update_app_versions_updated_at;
DROP TRIGGER trigger_app_updates_updated_at ON app_versions;
CREATE TRIGGER trigger_app_versions_updated_at
    BEFORE UPDATE ON app_versions
    FOR EACH ROW
    EXECUTE FUNCTION update_app_versions_updated_at();

ALTER TABLE app_versions
    ADD COLUMN app TEXT DEFAULT 'default' NOT NULL;
ALTER TABLE app_versions
    ALTER COLUMN app DROP DEFAULT;

CREATE INDEX idx_app_versions_app ON app_versions(app);
CREATE INDEX idx_app_versions_app_platform ON app_versions(app, platform);

COMMIT;
