"""CRM-008 — focused tests on the X / Twitter taxonomy candidate set.

Proves that ONLY blank Deal Source records with clean, deterministic X / Twitter
evidence enter the candidate CSV. Reads local artifacts only: no HubSpot, no CRM,
no warehouse write, no writeback.
"""
import csv
import hashlib
import json
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]
ART = REPO / "hermes_shared/artifacts"
CANDIDATES = ART / "CRM-008_x_twitter_taxonomy_candidates.csv"
EXCEPTIONS = ART / "CRM-008_utm_normalization_exceptions.csv"
PROPOSALS = REPO / "hermes_shared/ledger/proposals.json"

NORMALIZE_INPUTS = {"x", "Twitter"}
NORMALIZED = "X / Twitter"


def rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def candidates():
    return rows(CANDIDATES)


# ── The four selection conditions ──────────────────────────────────────────

def test_every_candidate_has_blank_current_deal_source():
    """No record that already carries a Deal Source may enter."""
    assert candidates(), "candidate CSV is empty"
    for r in candidates():
        assert r["current_deal_source"].strip() == "", r["deal_id"]


def test_every_candidate_has_clean_utm_quality():
    for r in candidates():
        assert r["utm_quality"] == "clean", r["deal_id"]


def test_every_candidate_is_x_twitter_channel():
    for r in candidates():
        assert r["first_touch_channel"] == NORMALIZED, r["deal_id"]


def test_every_candidate_raw_utm_is_a_literal_rule_input():
    """Only the two exact strings in the proposed rule qualify."""
    for r in candidates():
        assert r["raw_utm_source"] in NORMALIZE_INPUTS, (
            f"{r['deal_id']} has un-ruled utm_source {r['raw_utm_source']!r}")


def test_every_candidate_uses_deterministic_first_touch_evidence():
    for r in candidates():
        assert r["attribution_evidence_status"] == "first_touch_utm", r["deal_id"]


def test_normalization_is_applied_uniformly():
    for r in candidates():
        assert r["normalized_utm_evidence"] == NORMALIZED, r["deal_id"]
        assert r["normalization_rule"] == (
            "exact_match:{'x','Twitter'}->'X / Twitter'"), r["deal_id"]


# ── Negative controls: what must be kept OUT ───────────────────────────────

def test_no_corrupted_or_missing_quality_leaked_in():
    for r in candidates():
        assert r["utm_quality"] not in {"corrupted", "missing", ""}, r["deal_id"]


def test_no_unknown_channel_leaked_in():
    for r in candidates():
        assert "Unknown" not in r["first_touch_channel"], r["deal_id"]


def test_exception_records_are_absent_from_candidates():
    """The 8 corrupted-channel and 4 variant records must not appear."""
    excluded = {r["deal_id"] for r in rows(EXCEPTIONS)}
    present = {r["deal_id"] for r in candidates()}
    assert not (excluded & present), sorted(excluded & present)


def test_the_eight_corrupted_records_are_listed_and_unclassified():
    corrupted = [r for r in rows(EXCEPTIONS)
                 if r["exception_type"] == "corrupted_channel_clean_quality"]
    assert len(corrupted) == 8
    for r in corrupted:
        assert r["first_touch_channel"] == "Unknown (corrupted UTM)"
        assert r["utm_quality"] == "clean"
        assert r["disposition"] == "do_not_classify"


def test_variant_exceptions_are_outside_the_rule():
    variants = [r for r in rows(EXCEPTIONS)
                if r["exception_type"] == "unnormalized_utm_variant"]
    assert variants
    for r in variants:
        assert r["raw_utm_source"] not in NORMALIZE_INPUTS
        assert r["disposition"] == "requires_normalization_decision"


def test_deal_ids_are_unique():
    ids = [r["deal_id"] for r in candidates()]
    assert len(ids) == len(set(ids))


# ── Population separation and counts ───────────────────────────────────────

def test_populations_are_separated_and_counts_hold():
    cw = [r for r in candidates() if r["population"] == "closed_won"]
    ao = [r for r in candidates() if r["population"] == "active_open"]
    assert len(cw) == 20, len(cw)
    assert len(ao) == 392, len(ao)
    assert len(cw) + len(ao) == len(candidates())


def test_closed_won_amount_matches_verified_total():
    cw = [r for r in candidates() if r["population"] == "closed_won"]
    total = sum(float(r["crm_deal_amount"]) for r in cw if r["crm_deal_amount"])
    assert round(total, 2) == 976462.00, total


def test_active_amount_matches_verified_total():
    ao = [r for r in candidates() if r["population"] == "active_open"]
    total = sum(float(r["crm_deal_amount"]) for r in ao if r["crm_deal_amount"])
    assert round(total, 2) == 1715358.00, total


# ── Authorization boundary ─────────────────────────────────────────────────

def test_no_candidate_row_authorizes_a_crm_change():
    for r in candidates():
        assert r["authorizes_crm_change"] == "False", r["deal_id"]
        assert "NOT approved" in r["proposed_deal_source_pending_approval"]


def test_proposal_is_not_execution_authorized():
    data = json.loads(PROPOSALS.read_text())
    p = next(p for p in data["proposals"] if p["proposal_id"] == "CRM-008")
    assert p["execution_authorized"] is False
    assert p["status"] == "proposed"
    assert p["approval"]["approved_by"] is None
    assert p["approval"]["approved_at"] is None


def test_proposal_checksum_matches_the_candidate_csv():
    """The ledger must point at exactly the bytes on disk."""
    data = json.loads(PROPOSALS.read_text())
    p = next(p for p in data["proposals"] if p["proposal_id"] == "CRM-008")
    recorded = p["target_population"]["record_ids_or_artifact"].split("sha256:")[1]
    actual = hashlib.sha256(CANDIDATES.read_bytes()).hexdigest()
    assert recorded == actual, f"ledger {recorded} != disk {actual}"


def test_existing_crm007_proposal_is_untouched():
    """CRM-008 must not have displaced the open owner-directory proposal."""
    data = json.loads(PROPOSALS.read_text())
    ids = [p["proposal_id"] for p in data["proposals"]]
    assert len(ids) == len(set(ids)), f"duplicate proposal ids: {ids}"
    crm007 = next(p for p in data["proposals"] if p["proposal_id"] == "CRM-007")
    assert crm007["title"] == "Read-only owner-directory and deal-name enrichment"
