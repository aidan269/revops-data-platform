"""CRM-008 closed-won-only execution package — focused tests.

Proves the target set is exactly the revalidated closed-won subset, that the
rollback file covers it per record, that ARR is never asserted from CRM deal
amount, and that execution remains unauthorized. Local artifacts only.
"""
import csv
import hashlib
import json
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
PKG = REPO / "hermes_shared/execution_packages/CRM-008_closed_won"
TARGET = PKG / "CRM-008_closed_won_final_target.csv"
ROLLBACK = PKG / "CRM-008_closed_won_rollback.csv"
SUMMARY = PKG / "CRM-008_closed_won_dry_run_summary.json"
CANDIDATES = REPO / "hermes_shared/artifacts/CRM-008_x_twitter_taxonomy_candidates.csv"
EXCEPTIONS = REPO / "hermes_shared/artifacts/CRM-008_utm_normalization_exceptions.csv"
PROPOSALS = REPO / "hermes_shared/ledger/proposals.json"

RULE_INPUTS = {"x", "Twitter"}
HELD_OUT = {"twitter.com", "twitter", "t.co"}
PROPOSED = "X / Twitter"

# The execution package and its supporting artifacts are operational evidence —
# live CRM state, regenerated per run, deliberately NOT committed. Skip the
# module cleanly when it is absent so a checkout without the evidence never
# reports a false pass or a false failure.
_EVIDENCE_PRESENT = all(
    p.exists() for p in (TARGET, ROLLBACK, SUMMARY, CANDIDATES, EXCEPTIONS, PROPOSALS)
)
pytestmark = pytest.mark.skipif(
    not _EVIDENCE_PRESENT,
    reason="CRM-008 closed-won execution package not present; "
           "hermes_shared/execution_packages, artifacts and ledger are not committed",
)


def rows(p):
    with open(p, newline="") as f:
        return list(csv.DictReader(f))


def target():
    return rows(TARGET)


def summary():
    return json.loads(SUMMARY.read_text())


# ── Scope: closed-won only ─────────────────────────────────────────────────

def test_target_is_exactly_twenty_closed_won_deals():
    assert len(target()) == 20


def test_every_target_is_closed_won():
    for r in target():
        assert r["hs_is_closed_won"] == "True", r["deal_id"]


def test_every_target_is_blank_deal_source():
    for r in target():
        assert r["current_deal_source"].strip() == "", r["deal_id"]


def test_every_target_has_exact_approved_utm_evidence():
    for r in target():
        assert r["raw_utm_source"] in RULE_INPUTS, r["deal_id"]
        assert r["first_touch_channel" if "first_touch_channel" in r else "utm_quality"]
        assert r["utm_quality"] == "clean", r["deal_id"]
        assert r["attribution_evidence_status"] == "first_touch_utm", r["deal_id"]


def test_every_target_proposes_x_twitter():
    for r in target():
        assert r["proposed_deal_source"] == PROPOSED, r["deal_id"]


def test_held_out_variants_never_appear():
    for r in target():
        assert r["raw_utm_source"] not in HELD_OUT, r["deal_id"]


def test_target_is_a_subset_of_the_approved_candidate_set():
    approved = {r["deal_id"] for r in rows(CANDIDATES)}
    for r in target():
        assert r["deal_id"] in approved, r["deal_id"]


def test_exception_records_never_appear():
    excluded = {r["deal_id"] for r in rows(EXCEPTIONS)}
    assert not (excluded & {r["deal_id"] for r in target()})


def test_deal_ids_unique():
    ids = [r["deal_id"] for r in target()]
    assert len(ids) == len(set(ids))


# ── Amount and ARR separation ──────────────────────────────────────────────

def test_crm_deal_amount_total_and_split():
    t = target()
    with_amt = [r for r in t if r["has_crm_deal_amount"] == "True"]
    assert len(with_amt) == 19
    assert len(t) - len(with_amt) == 1
    total = sum(float(r["crm_deal_amount"]) for r in with_amt)
    assert round(total, 2) == 976462.00, total


def test_no_arr_evidence_is_claimed_anywhere():
    """Zero verified ARR; every record must say so explicitly."""
    for r in target():
        assert r["arr_evidence_status"] == "not_verifiable_from_current_evidence", r["deal_id"]
        assert r["customer_motion"] == "unclassified", r["deal_id"]


def test_amount_is_never_labelled_arr_or_revenue():
    for r in target():
        assert r["amount_basis"] == (
            "hubspot_crm_deal_amount_not_arr_not_recognized_revenue"), r["deal_id"]


def test_summary_arr_coverage_is_zero_of_twenty():
    s = summary()
    assert s["population_2_verified_arr_evidence"]["deals"] == 0
    assert s["population_3_arr_not_verifiable"]["deals"] == 20
    assert s["arr_evidence_coverage"] == "0 of 20"


def test_summary_populations_reconcile():
    s = summary()
    p1 = s["population_1_closed_won_with_crm_deal_amount"]
    assert p1["deals"] + p1["deals_without_amount"] == 20
    assert p1["crm_deal_amount"] == 976462.00
    assert sum(s["population_3_arr_not_verifiable"]["reasons"].values()) == 20


# ── Rollback ───────────────────────────────────────────────────────────────

def test_rollback_covers_every_target_record():
    t = {r["deal_id"] for r in target()}
    rb = rows(ROLLBACK)
    assert len(rb) == len(t)
    assert {r["deal_id"] for r in rb} == t


def test_rollback_captures_the_prior_blank_value():
    for r in rows(ROLLBACK):
        assert r["prior_value"] == "", r["deal_id"]
        assert r["prior_value_is_blank"] == "True", r["deal_id"]
        assert r["hubspot_property"] == "deal_source", r["deal_id"]
        assert "restore blank" in r["restore_action"], r["deal_id"]


# ── Authorization boundary ─────────────────────────────────────────────────

def test_no_target_row_authorizes_a_crm_change():
    for r in target():
        assert r["authorizes_crm_change"] == "False", r["deal_id"]


def test_dry_run_made_no_calls_and_no_writes():
    s = summary()
    assert s["dry_run"] is True
    assert s["hubspot_calls_made"] == 0
    assert s["crm_records_changed"] == 0
    assert s["warehouse_writes"] == 0
    assert s["execution_authorized"] is False


def test_ledger_entry_is_not_execution_authorized():
    data = json.loads(PROPOSALS.read_text())
    p = next(x for x in data["proposals"] if x["proposal_id"] == "CRM-008-EXEC-CW")
    assert p["execution_authorized"] is False
    assert p["status"] == "proposed"
    assert p["approval"]["approved_by"] is None


def test_ledger_hash_matches_target_csv_on_disk():
    data = json.loads(PROPOSALS.read_text())
    p = next(x for x in data["proposals"] if x["proposal_id"] == "CRM-008-EXEC-CW")
    recorded = p["target_population"]["record_ids_or_artifact"].split("sha256:")[1]
    assert recorded == hashlib.sha256(TARGET.read_bytes()).hexdigest()


def test_proposal_ids_remain_unique():
    data = json.loads(PROPOSALS.read_text())
    ids = [x["proposal_id"] for x in data["proposals"]]
    assert len(ids) == len(set(ids)), ids


def test_revalidated_against_a_fresh_extraction():
    """Revalidation must run against a genuinely fresh snapshot, not the one that
    produced the candidate set."""
    s = summary()["revalidation"]
    assert s["fresh_extraction_run"] is True
    assert s["drift_detectable"] is True
    assert s["revalidated_against_snapshot"] > s["prior_snapshot"]


def test_revalidation_found_no_drift_and_population_held():
    s = summary()["revalidation"]
    assert s["eligible"] == 20
    assert s["excluded"] == 0
    assert s["excluded_since_prior_package"] == 0
    assert s["population_changed"] is False


def test_warehouse_and_package_fingerprints_match():
    """Set equality against the warehouse, proven independently of row order."""
    v = summary()["revalidation"]["verification"]
    assert v["fingerprints_match"] is True
    assert v["field_level_diffs"] == 0
    assert v["warehouse_id_fingerprint_md5"] == v["package_id_fingerprint_md5"]


def test_unchanged_population_left_artifacts_untouched():
    """Target and rollback must not be rewritten when nothing changed."""
    s = summary()["revalidation"]
    assert s["target_and_rollback_replaced"] is False
    assert summary()["artifacts"]["final_target_sha256"] == hashlib.sha256(
        TARGET.read_bytes()).hexdigest()


def test_ledger_records_the_fresh_revalidation():
    data = json.loads(PROPOSALS.read_text())
    p = next(x for x in data["proposals"] if x["proposal_id"] == "CRM-008-EXEC-CW")
    assert p["evidence"]["fresh_extraction_run"] is True
    assert p["evidence"]["revalidation_result"]["excluded_since_prior_package"] == 0
    assert p["evidence"]["revalidation_result"]["population_changed"] is False
