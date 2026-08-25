-- Raw-platform initialization for the RevOps warehouse (Postgres).
-- Runs automatically on first `docker compose up` (mounted into the postgres image).
--
-- Only the append-only landing schema is created here. The migration runner
-- (scripts/run_db_migrations.py) creates analytics.schema_migrations itself as
-- its own ledger; no analytics model or writeback table belongs in this platform.

CREATE SCHEMA IF NOT EXISTS raw;   -- immutable "bronze" landing zone
