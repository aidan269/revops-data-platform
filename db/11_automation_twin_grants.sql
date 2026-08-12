-- AUTOMATION-DIGITAL-TWIN — SELECT-only grants for hermes_reader.
-- Separate migration so migration 10's checksum stays stable once applied.
-- Idempotent: schema guard uses IF NOT EXISTS and every GRANT is repeat-safe.
-- SELECT only. hermes_reader never gains INSERT, UPDATE, DELETE, or DDL.

CREATE SCHEMA IF NOT EXISTS analytics;

DO $$
DECLARE t TEXT;
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hermes_reader') THEN
        GRANT USAGE ON SCHEMA raw TO hermes_reader;
        GRANT USAGE ON SCHEMA analytics TO hermes_reader;
        FOREACH t IN ARRAY ARRAY[
            'automation_source_snapshots','automation_assets','automation_nodes','automation_edges',
            'automation_field_access','automation_runs','automation_findings','automation_approvals'
        ] LOOP
            EXECUTE format('GRANT SELECT ON raw.%I TO hermes_reader', t);
        END LOOP;
        EXECUTE 'GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO hermes_reader';
        EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT SELECT ON TABLES TO hermes_reader';
        RAISE NOTICE 'AUTOMATION-DIGITAL-TWIN: SELECT-only grants applied to hermes_reader';
    ELSE
        RAISE NOTICE 'AUTOMATION-DIGITAL-TWIN: role hermes_reader absent; grants skipped';
    END IF;
END
$$;
