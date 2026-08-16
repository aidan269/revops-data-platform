"""CRM-012 — GTM Campaign measurement layer tests.

Two groups:
  * Static tests — run now, with no warehouse. They guard the safety model:
    read-only extraction, no inference paths, correct object type, amount and
    attribution labelling.
  * Reconciliation tests — skipped until the GTM tables are populated. They
    assert the CRM facts hold. They never create or repair an association; a
    failure is a review finding for a human.
"""
import json
import os
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parents[1]
EXTRACTOR = REPO / "extract/extract_gtm_campaigns.py"
MIGRATION = REPO / "db/07_gtm_campaigns.sql"
MART = REPO / "transform/models/marts/mart_gtm_campaign_performance_live.sql"
STG_DIR = REPO / "transform/models/staging"
MCP = REPO / "hermes/codex_mcp.py"
METHOD = REPO / "hermes_shared/methodologies/CRM-012_gtm_campaign_measurement.md"
PROPOSALS = REPO / "hermes_shared/ledger/proposals.json"

GTM_OBJECT_TYPE = "2-63647366"


def _sql_without_comments(path):
    """Executable SQL only. A forbidden token inside a comment that explains why
    it is forbidden must not fail the test."""
    lines = []
    for line in pathlib.Path(path).read_text().splitlines():
        lines.append(line.split("--", 1)[0])
    return "\n".join(lines)


def _flat(text):
    """Collapse whitespace so a string split across source lines still matches."""
    return re.sub(r"\s+", " ", text)


def _plain(text):
    """Collapse whitespace and drop markdown emphasis."""
    return re.sub(r"\s+", " ", text.replace("*", "").replace("`", ""))


def _conn():
    """Return a warehouse connection, or None when unavailable."""
    try:
        import psycopg2
    except ImportError:
        return None
    url = os.getenv("DATABASE_URL", "postgresql://revops:revops@localhost:5432/revops")
    try:
        return psycopg2.connect(url, connect_timeout=3)
    except Exception:
        return None


def _rows(sql, params=None):
    conn = _conn()
    if conn is None:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception:
        return None
    finally:
        conn.close()


def _gtm_populated():
    r = _rows("select count(*) as n from raw.hubspot_gtm_campaigns")
    return bool(r) and r[0]["n"] > 0


# ── Safety model: read-only extraction ─────────────────────────────────────

def test_extractor_issues_only_get_requests():
    src = EXTRACTOR.read_text()
    for verb in ("requests.post", "requests.put", "requests.patch", "requests.delete",
                 "session.post", "session.put", "session.patch", "session.delete"):
        assert verb not in src, f"extractor must not use {verb}"
    assert "requests.get" in src


def test_extractor_targets_the_custom_object_not_native_campaigns():
    src = EXTRACTOR.read_text()
    assert GTM_OBJECT_TYPE in src
    assert f"/crm/v3/objects/{{GTM_OBJECT_TYPE}}" in src or "objects/{GTM_OBJECT_TYPE}" in src


def test_extractor_fails_closed_without_a_token():
    src = EXTRACTOR.read_text()
    assert "HUBSPOT_PRIVATE_APP_TOKEN is not set" in src
    assert "raise RuntimeError" in src


def test_extractor_fails_closed_without_migrations():
    assert "assert_schema_ready" in EXTRACTOR.read_text()


def test_migration_grants_read_access_to_hermes_reader():
    """Per-table grants: without these the read-only tools cannot see the data."""
    sql = MIGRATION.read_text()
    assert "hermes_reader" in sql
    for table in ("hubspot_gtm_campaigns", "hubspot_gtm_campaign_contacts",
                  "hubspot_gtm_campaign_deals"):
        assert f"GRANT SELECT ON raw.{table} TO hermes_reader" in sql


def test_migration_is_idempotent():
    sql = MIGRATION.read_text()
    assert sql.count("CREATE TABLE IF NOT EXISTS") == 3
    assert "DROP TABLE" not in sql.upper()


# ── Safety model: no inference paths ───────────────────────────────────────

def test_mart_never_joins_deals_through_contacts_or_engagement():
    """A deal may enter a campaign only via a campaign→deal association edge."""
    sql = _sql_without_comments(MART)
    for forbidden in ("utm_source", "utm_campaign", "email_click", "email_open",
                      "form_submission", "hubspot_engagements", "first_touch_channel"):
        assert forbidden not in sql, f"mart must not reference {forbidden}"
    assert "stg_gtm_campaign_deals" in sql


def test_staging_copies_association_edges_without_inference():
    for name in ("stg_gtm_campaign_contacts", "stg_gtm_campaign_deals"):
        sql = _sql_without_comments(STG_DIR / f"{name}.sql")
        assert "select distinct" in sql.lower()
        for forbidden in ("utm", "engagement", "click"):
            assert forbidden not in sql.lower(), f"{name} must not reference {forbidden}"


def test_gtm_object_is_kept_separate_from_native_campaigns():
    sql = MART.read_text()
    assert "hubspot_campaigns" not in sql
    assert "stg_campaign_members" not in sql


# ── Safety model: labelling ────────────────────────────────────────────────

def test_every_money_column_is_labelled_crm_deal_amount():
    """Any column carrying money must say it is CRM deal amount, so a reader
    cannot mistake it for ARR or revenue. Counts, boolean gap flags and label
    columns are named with 'amount' too and are explicitly not money."""
    NOT_MONEY = {
        "amount_basis",             # label string
        "deals_missing_amount",     # count of deals
        "gap_deal_missing_amount",  # boolean flag
    }
    sql = MART.read_text()
    money_cols = {c for c in re.findall(r"as (\w*amount\w*)", sql) if c not in NOT_MONEY}
    assert money_cols, "expected money columns"
    for col in money_cols:
        assert "crm_deal_amount" in col, f"{col} must be labelled crm_deal_amount"
        assert "arr_amount" not in col
        assert "revenue" not in col
    # And the non-money names must not have quietly become money columns.
    for col in NOT_MONEY:
        assert col in sql, f"{col} missing; update the allowlist deliberately"


def test_mart_carries_amount_and_attribution_basis():
    sql = MART.read_text()
    assert "crm_deal_amount_not_arr_not_recognized_revenue" in sql
    assert "associated_influence_only_not_sourced" in sql


def test_mart_exposes_no_arr_amount():
    """closed_arr_deals is a count cross-reference; no ARR amount may be exposed."""
    sql = MART.read_text()
    assert "closed_arr_deals" in sql
    assert "closed_arr_amount" not in sql


def test_mart_reports_all_required_metrics():
    sql = MART.read_text()
    for col in ("associated_contacts", "associated_deals", "influenced_crm_deal_amount",
                "open_pipeline_crm_deal_amount", "closed_won_deals",
                "closed_won_crm_deal_amount", "measurement_status"):
        assert col in sql, col


def test_mart_flags_association_quality_gaps():
    sql = MART.read_text()
    for gap in ("gap_no_associated_contacts", "gap_no_associated_deals",
                "gap_missing_campaign_name", "gap_deal_not_in_live_warehouse",
                "gap_deal_missing_amount"):
        assert gap in sql, gap


# ── Hermes tools ───────────────────────────────────────────────────────────

def test_three_read_only_tools_exist():
    src = MCP.read_text()
    for tool in ("hermes_gtm_campaign_performance", "hermes_gtm_campaign_ranking",
                 "hermes_gtm_campaign_evidence_gaps"):
        assert f"def {tool}(" in src, tool


def test_tools_only_read():
    src = MCP.read_text()
    block = src[src.index("GTM_CAMPAIGN_PLAYBOOK_VERSION"):]
    block = block[:block.index("def hermes_data_health")]
    assert "_run_read_query" in block
    for forbidden in ("insert", "update ", "delete", "requests.post"):
        assert forbidden not in block.lower(), forbidden


def test_roi_is_declared_uncomputable_not_merely_unproven():
    src = MCP.read_text()
    assert "uncomputable" in src.lower() or "cannot be computed" in src.lower()
    assert "No campaign cost or spend" in src


def test_meetings_ranking_is_refused_with_a_reason():
    src = _flat(MCP.read_text())
    assert "meetings_note" in src
    assert "meetings are not " in src
    assert "associated to the GTM Campaign object" in src


# ── Methodology ────────────────────────────────────────────────────────────

def test_methodology_distinguishes_the_three_required_boundaries():
    t = _plain(METHOD.read_text())
    assert "Sourced" in t and "Influenced" in t
    assert "not ARR and not recognized revenue" in t
    assert "must not be stated" in t or "Not supported" in t


def test_methodology_records_the_crm_facts_for_reconciliation():
    t = METHOD.read_text()
    for fact in ("Rahma Hafi", "Apex - Groupe APICIL", "Snehal Kumar", "Gillian Dom",
                 "Lily Chau", "lily@amplitude.com", "Sierra Nevada", "Aptean"):
        assert fact in t, fact


# ── Reconciliation (skipped until extraction has run) ──────────────────────

def _skip_unless_populated():
    if not _gtm_populated():
        print("    SKIP — raw.hubspot_gtm_campaigns is empty; run the extraction first")
        return True
    return False


def test_reconcile_expected_campaigns_exist():
    if _skip_unless_populated():
        return
    names = {r["campaign_name"] for r in _rows(
        "select distinct name as campaign_name from raw.hubspot_gtm_campaigns") or []}
    for expected in ("Q326 - Apex Free Exploitability Review", "Demo vs PLG", "CloudSec List"):
        assert expected in names, f"missing GTM campaign: {expected}"


def test_reconcile_cloudsec_excludes_gillian_and_sierra_nevada():
    """Gillian Dom and Sierra Nevada were deliberately removed from CloudSec."""
    if _skip_unless_populated():
        return
    rows = _rows("""
        select c.email, co.name as company
        from raw.hubspot_gtm_campaigns g
        left join raw.hubspot_gtm_campaign_contacts gc on gc.campaign_id = g.id
        left join raw.hubspot_contacts c on c.id = gc.contact_id
        left join raw.hubspot_gtm_campaign_deals gd on gd.campaign_id = g.id
        left join raw.hubspot_deal_companies dco on dco.deal_id = gd.deal_id
        left join raw.hubspot_companies co on co.id = dco.company_id
        where g.name = 'CloudSec List'""") or []
    blob = json.dumps(rows).lower()
    assert "gillian" not in blob, "Gillian Dom must not be associated with CloudSec List"
    assert "sierra nevada" not in blob, "Sierra Nevada must not be associated with CloudSec List"


def test_reconcile_cloudsec_has_lily_chau():
    if _skip_unless_populated():
        return
    rows = _rows("""
        select c.email
        from raw.hubspot_gtm_campaigns g
        join raw.hubspot_gtm_campaign_contacts gc on gc.campaign_id = g.id
        join raw.hubspot_contacts c on c.id = gc.contact_id
        where g.name = 'CloudSec List'""") or []
    assert any((r["email"] or "").lower() == "lily@amplitude.com" for r in rows), \
        "CloudSec List must include lily@amplitude.com"


def test_reconcile_one_row_per_campaign_in_the_mart():
    if _skip_unless_populated():
        return
    rows = _rows("""select gtm_campaign_id, count(*) as n
                    from analytics_analytics.mart_gtm_campaign_performance_live
                    group by 1 having count(*) > 1""")
    assert not rows, f"mart must have one row per campaign; duplicates: {rows}"


def test_reconcile_mart_totals_match_association_edges():
    if _skip_unless_populated():
        return
    rows = _rows("""
        select m.gtm_campaign_id, m.associated_deals,
               (select count(distinct deal_id) from raw.hubspot_gtm_campaign_deals x
                 where x.campaign_id = m.gtm_campaign_id) as edge_deals
        from analytics_analytics.mart_gtm_campaign_performance_live m""") or []
    for r in rows:
        assert r["associated_deals"] == r["edge_deals"], r
