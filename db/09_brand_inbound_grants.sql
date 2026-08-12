-- BRAND-INBOUND-RECOVERY — SELECT-only grants for hermes_reader.
--
-- Kept separate from 08 because 08 was already applied and recorded; editing an
-- applied migration would trip the runner's checksum-drift guard. Grants belong
-- in their own idempotent migration.
--
-- The Hermes MCP server connects as hermes_reader. Grants are guarded so this
-- migration is safe on machines where the role has not been provisioned.
-- SELECT only: hermes_reader never gains INSERT, UPDATE, DELETE, or DDL.

-- Idempotent by construction: the schema guard uses IF NOT EXISTS and every
-- GRANT is repeat-safe. Re-running changes nothing.
CREATE SCHEMA IF NOT EXISTS analytics;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hermes_reader') THEN
        GRANT USAGE ON SCHEMA raw TO hermes_reader;
        GRANT USAGE ON SCHEMA analytics TO hermes_reader;

        GRANT SELECT ON raw.brand_inbound_imports TO hermes_reader;
        GRANT SELECT ON raw.brand_inbound_lines TO hermes_reader;
        GRANT SELECT ON raw.brand_inbound_twitter_crosscheck TO hermes_reader;

        -- dbt models are created after this migration runs, so grant on whatever
        -- already exists and set default privileges for what follows.
        EXECUTE 'GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO hermes_reader';
        EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT SELECT ON TABLES TO hermes_reader';
        EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA raw GRANT SELECT ON TABLES TO hermes_reader';

        RAISE NOTICE 'BRAND-INBOUND-RECOVERY: SELECT-only grants applied to hermes_reader';
    ELSE
        RAISE NOTICE 'BRAND-INBOUND-RECOVERY: role hermes_reader absent; grants skipped';
    END IF;
END
$$;
