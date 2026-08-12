"""BRAND-INBOUND-RECOVERY — source-control, parsing, and load-safety tests.

Source-integrity tests run without a database. Database tests skip cleanly when
Postgres is unavailable so a missing warehouse never masquerades as a pass.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import import_brand_inbound as imp  # noqa: E402

DB_URL = os.getenv("DATABASE_URL", "postgresql://revops:revops@localhost:5432/warehouse")

# Source-evidence tests need the human-maintained CSV/PDF, which are operational
# inputs and are deliberately NOT committed. Skip cleanly when they are absent so
# a checkout without the evidence never reports a false pass or a false failure.
_EVIDENCE_PRESENT = imp.CSV_PATH.exists() and imp.PDF_PATH.exists()
requires_evidence = pytest.mark.skipif(
    not _EVIDENCE_PRESENT,
    reason="brand inbound evidence not present; set BRAND_INBOUND_CSV / BRAND_INBOUND_PDF",
)


# --------------------------------------------------------------------------
# Source controls
# --------------------------------------------------------------------------
@requires_evidence
def test_csv_sha256_matches_recorded_control():
    assert imp.sha256_of(imp.CSV_PATH) == imp.EXPECTED_CSV_SHA


@requires_evidence
def test_pdf_sha256_matches_recorded_control():
    assert imp.sha256_of(imp.PDF_PATH) == imp.EXPECTED_PDF_SHA


@pytest.fixture(scope="module")
def rows():
    if not _EVIDENCE_PRESENT:
        pytest.skip("brand inbound evidence not present")
    return imp.read_csv_rows()


@requires_evidence
def test_csv_has_353_rows(rows):
    assert len(rows) == 353


@requires_evidence
def test_exactly_29_twitter_rows(rows):
    twitter = [r for r in rows if (r["source_raw"] or "").strip() == "Twitter / X"]
    assert len(twitter) == 29


@requires_evidence
def test_283_links_split_282_deals_and_1_company(rows):
    links = [r for r in rows if (r["hubspot_link_raw"] or "").strip()]
    assert len(links) == 283
    assert sum(1 for r in links if r["hubspot_object_type"] == "0-3") == 282
    assert sum(1 for r in links if r["hubspot_object_type"] == "0-2") == 1


@requires_evidence
def test_company_link_is_never_treated_as_a_deal(rows):
    company = [r for r in rows if r["hubspot_object_type"] == "0-2"]
    assert len(company) == 1
    assert company[0]["is_deal_link"] is False


def test_27_crosschecked_ids(rows):
    assert len(imp.PDF_CROSSCHECK) == 27


def test_22_overwritten_and_5_intact():
    statuses = [v[2] for v in imp.PDF_CROSSCHECK.values()]
    assert statuses.count("OVERWRITTEN") == 22
    assert statuses.count("STILL_INTACT") == 5


@requires_evidence
def test_pdf_ids_are_exact_subset_of_csv_twitter_ids(rows):
    twitter_ids = {
        r["hubspot_record_id"]
        for r in rows
        if (r["source_raw"] or "").strip() == "Twitter / X"
    }
    assert set(imp.PDF_CROSSCHECK).issubset(twitter_ids)


@requires_evidence
def test_the_two_not_crosschecked_ids(rows):
    twitter_ids = {
        r["hubspot_record_id"]
        for r in rows
        if (r["source_raw"] or "").strip() == "Twitter / X"
    }
    assert twitter_ids - set(imp.PDF_CROSSCHECK) == {"53398797749", "54040556044"}


@requires_evidence
def test_not_crosschecked_rows_are_neither_clean_nor_corrupted(rows):
    twitter = [r for r in rows if (r["source_raw"] or "").strip() == "Twitter / X"]
    built = imp.build_crosscheck_rows(twitter, "csv-sha", "pdf-sha")
    unchecked = [r for r in built if r["crosscheck_status"] == "NOT_CROSSCHECKED"]
    assert len(unchecked) == 2
    for row in unchecked:
        assert row["overwrite_status"] is None
        assert row["pdf_current_source"] is None
        assert "Neither clean nor corrupted" in row["evidence_limitations"]


def test_no_mechanism_is_attributed_to_zapier():
    """Observed drill-down labels only. Causation is never asserted."""
    mechanisms = {v[3] for v in imp.PDF_CROSSCHECK.values()}
    assert not any("zapier" in m.lower() for m in mechanisms)


def test_numeric_parsing_refuses_unsafe_values():
    assert imp.parse_numeric("N/A") is None
    assert imp.parse_numeric("") is None
    assert imp.parse_numeric("  ") is None
    assert imp.parse_numeric("TBD") is None
    assert imp.parse_numeric("12%") is None
    assert imp.parse_numeric("3") == 3
    assert imp.parse_numeric("1,250") == 1250


@requires_evidence
def test_report_month_is_filled_down(rows):
    assert rows[0]["report_month_filled"] == "January 2025"
    assert rows[1]["month_raw"].strip() == ""
    assert rows[1]["report_month_filled"] == "January 2025"


@requires_evidence
def test_raw_rows_are_preserved_verbatim(rows):
    for row in rows[:25]:
        assert row["raw_row"]["Deal Name"] == row["deal_name_raw"]
        assert row["raw_row"]["Source"] == row["source_raw"]


@requires_evidence
def test_validation_fails_closed_on_bad_hash(rows):
    with pytest.raises(SystemExit):
        imp.validate_sources(rows, "wrong-sha", imp.EXPECTED_PDF_SHA)


# --------------------------------------------------------------------------
# Load safety
# --------------------------------------------------------------------------
def test_migration_declares_no_crm_authorization():
    sql = (ROOT / "db" / "08_brand_inbound_recovery.sql").read_text(encoding="utf-8")
    for table in ("brand_inbound_imports", "brand_inbound_lines",
                  "brand_inbound_twitter_crosscheck"):
        assert table in sql
    assert sql.count("authorizes_crm_change = false") >= 3
    assert "authorizes_crm_change BOOLEAN    NOT NULL DEFAULT false" in sql


def test_grants_are_select_only_for_hermes_reader():
    sql = (ROOT / "db" / "09_brand_inbound_grants.sql").read_text(encoding="utf-8")
    assert "hermes_reader" in sql
    for table in ("brand_inbound_imports", "brand_inbound_lines",
                  "brand_inbound_twitter_crosscheck"):
        assert f"GRANT SELECT ON raw.{table} TO hermes_reader" in sql
    for forbidden in ("GRANT INSERT", "GRANT UPDATE", "GRANT DELETE", "GRANT ALL"):
        assert forbidden not in sql


def test_migration_runner_includes_new_migrations_without_touching_old():
    from scripts.run_db_migrations import MIGRATIONS

    assert MIGRATIONS[:5] == (
        "03_hubspot_deals.sql",
        "04_hubspot_campaigns.sql",
        "05_deal_source_migration.sql",
        "06_original_traffic_source.sql",
        "07_gtm_campaigns.sql",
    )
    # Forward-compatible: later tasks append migrations without reordering these.
    assert MIGRATIONS[5:7] == (
        "08_brand_inbound_recovery.sql",
        "09_brand_inbound_grants.sql",
    )
    assert list(MIGRATIONS) == sorted(MIGRATIONS), "migrations must stay in numeric order"
    assert len(MIGRATIONS) == len(set(MIGRATIONS)), "migration names must be unique"


def test_mart_never_supersedes_the_live_snapshot():
    sql = (ROOT / "transform" / "models" / "marts"
           / "mart_brand_inbound_evidence.sql").read_text(encoding="utf-8")
    assert "never supersede" in sql.lower()
    assert "left join" in sql.lower()          # live snapshot is never filtered away
    assert "false as authorizes_crm_change" in sql
    for forbidden in ("insert into", "update ", "delete from"):
        assert forbidden not in sql.lower()


def test_importer_requires_an_explicit_database_url():
    """No implicit default: the runner's `revops` default must not be inherited."""
    source = (ROOT / "scripts" / "import_brand_inbound.py").read_text(encoding="utf-8")
    assert "--database-url or DATABASE_URL is required" in source
    assert 'default=os.getenv("DATABASE_URL")' in source


# --------------------------------------------------------------------------
# Database state (skipped when Postgres is unavailable)
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def cursor():
    psycopg2 = pytest.importorskip("psycopg2")
    try:
        conn = psycopg2.connect(DB_URL)
    except psycopg2.OperationalError as exc:  # pragma: no cover
        pytest.skip(f"warehouse unavailable: {exc}")
    conn.autocommit = True
    with conn.cursor() as cur:
        yield cur
    conn.close()


def _scalar(cursor, sql):
    cursor.execute(sql)
    return cursor.fetchone()[0]


def test_db_line_count_is_353(cursor):
    assert _scalar(cursor, "SELECT count(*) FROM raw.brand_inbound_lines") == 353


def test_db_twitter_count_is_29(cursor):
    assert _scalar(
        cursor,
        "SELECT count(*) FROM raw.brand_inbound_lines WHERE trim(source_raw) = 'Twitter / X'",
    ) == 29


def test_db_link_split(cursor):
    assert _scalar(cursor, """SELECT count(*) FROM raw.brand_inbound_lines
                              WHERE hubspot_object_type = '0-3'""") == 282
    assert _scalar(cursor, """SELECT count(*) FROM raw.brand_inbound_lines
                              WHERE hubspot_object_type = '0-2'""") == 1


def test_db_crosscheck_distribution(cursor):
    assert _scalar(cursor, "SELECT count(*) FROM raw.brand_inbound_twitter_crosscheck") == 29
    assert _scalar(cursor, """SELECT count(*) FROM raw.brand_inbound_twitter_crosscheck
                              WHERE crosscheck_status = 'CROSSCHECKED'""") == 27
    assert _scalar(cursor, """SELECT count(*) FROM raw.brand_inbound_twitter_crosscheck
                              WHERE overwrite_status = 'OVERWRITTEN'""") == 22
    assert _scalar(cursor, """SELECT count(*) FROM raw.brand_inbound_twitter_crosscheck
                              WHERE overwrite_status = 'STILL_INTACT'""") == 5


def test_db_not_crosschecked_ids(cursor):
    cursor.execute("""SELECT deal_id FROM raw.brand_inbound_twitter_crosscheck
                      WHERE crosscheck_status = 'NOT_CROSSCHECKED' ORDER BY deal_id""")
    assert [r[0] for r in cursor.fetchall()] == ["53398797749", "54040556044"]


def test_db_no_row_authorizes_a_crm_change(cursor):
    for table in ("brand_inbound_imports", "brand_inbound_lines",
                  "brand_inbound_twitter_crosscheck"):
        assert _scalar(
            cursor, f"SELECT count(*) FROM raw.{table} WHERE authorizes_crm_change"
        ) == 0


@requires_evidence
def test_db_reimport_is_idempotent(cursor):
    """Re-running the importer must not duplicate rows."""
    before = _scalar(cursor, "SELECT count(*) FROM raw.brand_inbound_lines")
    rows = imp.read_csv_rows()
    csv_sha = imp.sha256_of(imp.CSV_PATH)
    pdf_sha = imp.sha256_of(imp.PDF_PATH)
    twitter = [r for r in rows if (r["source_raw"] or "").strip() == "Twitter / X"]
    counts = imp.load(DB_URL, rows, imp.build_crosscheck_rows(twitter, csv_sha, pdf_sha),
                      csv_sha, pdf_sha)
    assert counts["lines_inserted"] == 0
    assert counts["crosscheck_inserted"] == 0
    assert counts["lines_total"] == before


def test_db_historical_evidence_is_not_merged_into_hubspot_snapshots(cursor):
    """The recovery tables must stay separate from raw.hubspot_deals."""
    assert _scalar(cursor, """SELECT count(*) FROM information_schema.columns
                              WHERE table_schema = 'raw' AND table_name = 'hubspot_deals'
                                AND column_name LIKE 'brand_inbound%'""") == 0
