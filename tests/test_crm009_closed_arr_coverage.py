"""CRM-009 — Closed ARR Deal Source coverage, focused tests.

Guards the authoritative definition (Closed Won stage AND billing_model =
'subscription-arr'), proves ARR is never inferred from amount or closed-won
status, and asserts the empty result is recorded as a blocked measurement rather
than a measured zero. Local artifacts only; no HubSpot, no CRM write.
"""
import csv
import hashlib
import json
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
ART = REPO / "hermes_shared/artifacts"
REGISTER = ART / "CRM-009_closed_arr_population_register.csv"
BLANK = ART / "CRM-009_closed_arr_blank_deal_source.csv"
METHOD = REPO / "hermes_shared/methodologies/CRM-009_closed_arr_deal_source_coverage.md"
PROPOSALS = REPO / "hermes_shared/ledger/proposals.json"
LEDGER = REPO / "hermes_shared/ledger/execution_events.jsonl"
CRM008_TARGET = (REPO / "hermes_shared/execution_packages/CRM-008_closed_won"
                 / "CRM-008_closed_won_final_target.csv")

# METHOD is committed; everything else here is operational evidence — live CRM
# state, regenerated per run, deliberately NOT committed. Skip the module cleanly
# when it is absent so a checkout without the evidence never reports a false pass
# or a false failure.
_EVIDENCE_PRESENT = all(
    p.exists() for p in (REGISTER, BLANK, PROPOSALS, LEDGER, CRM008_TARGET)
)
pytestmark = pytest.mark.skipif(
    not _EVIDENCE_PRESENT,
    reason="CRM-009 closed-ARR evidence not present; hermes_shared/artifacts, "
           "ledger and execution_packages are not committed",
)


def proposal():
    data = json.loads(PROPOSALS.read_text())
    return next(p for p in data["proposals"] if p["proposal_id"] == "CRM-009")


def rows(p):
    with open(p, newline="") as f:
        return list(csv.DictReader(f))


def header(p):
    with open(p, newline="") as f:
        return next(csv.reader(f))


# ── Artifacts are well-formed even though empty ────────────────────────────

def test_register_has_the_exact_closed_arr_population():
    r = rows(REGISTER)
    assert len(r) == 223
    assert proposal()["target_population"]["record_count"] == 223


def test_every_register_row_matches_both_definition_clauses():
    """Closed Won stage AND the exact option label — no near-misses."""
    for r in rows(REGISTER):
        assert r["billing_model"] == "Subscription - ARR", r["deal_id"]
        assert r["dealstage"] in {"206310249", "closedwon", "206310247"}, r["deal_id"]


def test_option_label_is_matched_exactly_not_slugified():
    """The superseded run used 'subscription-arr'; that value must never appear."""
    for r in rows(REGISTER):
        assert r["billing_model"] != "subscription-arr", r["deal_id"]
    assert "Subscription - ARR" in proposal()["target_population"]["selection_rule"]


def test_other_billing_models_are_excluded():
    for r in rows(REGISTER):
        assert r["billing_model"] not in {
            "One-off Project", "Subscription - Deal", "Retainer Deal",
            "Retainer Top Up", "Deprecated", "Subscription - Trial & Pilot Programs"}


def test_deal_source_coverage_counts_and_percentage():
    r = rows(REGISTER)
    pop = [x for x in r if x["deal_source_state"] == "populated"]
    blank = [x for x in r if x["deal_source_state"] == "blank"]
    assert len(pop) == 14
    assert len(blank) == 209
    assert len(pop) + len(blank) == 223
    assert round(100.0 * len(pop) / len(r), 2) == 6.28
    e = proposal()["evidence"]
    assert e["deal_source_populated"] == 14 and e["deal_source_blank"] == 209


def test_crm_deal_amount_is_labelled_not_revenue():
    assert "crm_deal_amount_not_revenue" in header(REGISTER)
    for col in header(REGISTER):
        assert "arr_amount" not in col.lower(), col
    total = sum(float(x["crm_deal_amount_not_revenue"]) for x in rows(REGISTER)
                if x["crm_deal_amount_not_revenue"])
    assert round(total, 2) == 10742820.12


def test_blank_csv_holds_exactly_the_blank_records():
    b = rows(BLANK)
    assert len(b) == 209
    for x in b:
        assert x["deal_source"].strip() == "", x["deal_id"]
        assert x["deal_source_state"] == "blank", x["deal_id"]
        assert x["authorizes_crm_change"] == "False", x["deal_id"]
        assert x["proposed_deal_source_pending_approval"] == "", x["deal_id"]


def test_no_blank_record_has_deterministic_evidence():
    """Zero safe write candidates: nothing may be proposed for a write."""
    b = rows(BLANK)
    det = [x for x in b if x["evidence_class"] == "deterministic_approved_evidence"]
    rev = [x for x in b if x["evidence_class"] == "needs_human_review"]
    assert len(det) == 0
    assert len(rev) == 209
    assert proposal()["evidence"]["blank_deterministic_approved_evidence"] == 0
    assert proposal()["evidence"]["safe_write_candidates"] == 0


def test_review_reasons_reconcile():
    e = proposal()["evidence"]["blank_review_reasons"]
    assert sum(e.values()) == 209


def test_definition_requires_both_clauses():
    rule = proposal()["target_population"]["selection_rule"].lower()
    assert "closed won" in rule and "billing_model" in rule


def test_definition_forbids_inferring_arr():
    rule = proposal()["target_population"]["selection_rule"].lower()
    for forbidden in ("deal amount", "closed-won status", "finance", "product/service"):
        assert forbidden in rule, f"definition must disclaim {forbidden}"


def test_prior_zero_result_is_recorded_as_superseded():
    """The old 0 must be preserved as a blocked measurement, not deleted."""
    s = proposal()["evidence"]["prior_zero_result_superseded"]
    assert "not requested" in s and "3208" in s


def test_x_twitter_overlap_is_seven_and_explained():
    o = proposal()["evidence"]["x_twitter_overlap"]
    assert "7 are Subscription - ARR" in o
    ids = {r["deal_id"] for r in rows(CRM008_TARGET)}
    assert len(ids) == 20
    in_pop = ids & {r["deal_id"] for r in rows(REGISTER)}
    assert len(in_pop) == 7


def test_x_twitter_records_in_population_are_populated_not_blank():
    ids = {r["deal_id"] for r in rows(CRM008_TARGET)}
    for r in rows(REGISTER):
        if r["deal_id"] in ids:
            assert r["deal_source"] == "X / Twitter", r["deal_id"]
            assert r["deal_source_state"] == "populated", r["deal_id"]


def test_crm009_is_read_only_and_unauthorized():
    p = proposal()
    assert p["execution_authorized"] is False
    assert p["status"] == "proposed"
    assert p["approval"]["approved_by"] is None


def test_ledger_hashes_match_artifacts_on_disk():
    tp = proposal()["target_population"]
    assert (tp["record_ids_or_artifact"].split("sha256:")[1]
            == hashlib.sha256(REGISTER.read_bytes()).hexdigest())
    assert (tp["blank_deal_source_artifact"].split("sha256:")[1]
            == hashlib.sha256(BLANK.read_bytes()).hexdigest())


def test_audit_events_recorded_and_ledger_valid():
    lines = [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()]
    crm009 = [e for e in lines if e["proposal_id"] == "CRM-009"]
    assert len(crm009) >= 6


def test_methodology_documents_the_definition_and_supersession():
    t = METHOD.read_text()
    assert "Subscription - ARR" in t
    assert "superseded" in t.lower()
    assert "not revenue" in t.lower()


def test_proposal_ids_remain_unique():
    ids = [p["proposal_id"] for p in json.loads(PROPOSALS.read_text())["proposals"]]
    assert len(ids) == len(set(ids)), ids
