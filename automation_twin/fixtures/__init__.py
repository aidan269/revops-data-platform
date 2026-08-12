"""Synthetic dry-run fixtures. No real names, emails, or submission contents.

A `linkage` value must name exactly one candidate deal id (e.g. "D1"); the
simulator rejects sentinels, lists, and ids absent from the candidate set.

Record identifiers are synthetic placeholders (D1, C1...) except where a prior
finding is reproduced, in which case only an opaque numeric CRM id appears.
"""
from __future__ import annotations

WF_CAMPAIGN = "hubspot:workflow:1833911074"
WF_DEMO = "hubspot:workflow:1858050407"
APOLLO_IMPORT = "hubspot:import:unidentified_writer"

FIXTURES: dict[str, dict] = {
    "valid_campaign_propagation": {
        "fixture_name": "valid_campaign_propagation", "asset_id": WF_CAMPAIGN,
        "record": {"linkage": "D1"},
        "current_values": {"primary_campaign_source": None},
        "associations": {"deals": ["D1"]},
        "rules": [{"property": "primary_campaign_source",
                   "value": "Q326 - BlackHat - Event", "overwrite": "only_if_empty"}],
        "expect": "one proposed write",
    },
    "vendor_contamination_attempt": {
        "fixture_name": "vendor_contamination_attempt", "asset_id": APOLLO_IMPORT,
        "record": {"linkage": "D1"},
        "current_values": {"primary_campaign_source": None},
        "associations": {"deals": ["D1"]},
        "rules": [{"property": "primary_campaign_source", "value": "Apollo",
                   "overwrite": "replace"}],
        "expect": "blocked: unregistered writer and vendor literal",
    },
    "blank_destination": {
        "fixture_name": "blank_destination", "asset_id": WF_DEMO,
        "record": {"linkage": "D1"},
        "current_values": {"requested_service": None},
        "associations": {"deals": ["D1"]},
        "rules": [{"property": "requested_service", "value": "Code Analyzer",
                   "overwrite": "only_if_empty"}],
        "expect": "one proposed write",
    },
    "populated_destination_conflict": {
        "fixture_name": "populated_destination_conflict", "asset_id": WF_DEMO,
        "record": {"linkage": "D1"},
        "current_values": {"repo_uri": "https://example.invalid/repo/pull/1"},
        "associations": {"deals": ["D1"]},
        "rules": [{"property": "repo_uri", "value": "https://example.invalid/repo",
                   "overwrite": "only_if_empty"}],
        "expect": "would_skip: populated destination preserved",
    },
    "multi_deal_ambiguity": {
        "fixture_name": "multi_deal_ambiguity", "asset_id": WF_DEMO,
        "record": {}, "current_values": {"requested_service": None},
        "associations": {"deals": ["D1", "D2", "D3"]},
        "rules": [{"property": "requested_service", "value": "Code Analyzer"}],
        "expect": "stopped_safe: ambiguous target",
    },
    "deal_created_before_submission": {
        "fixture_name": "deal_created_before_submission", "asset_id": WF_CAMPAIGN,
        "record": {"linkage": "D1", "deal_created": "2024-09-23",
                   "form_submitted": "2026-07-16"},
        "current_values": {"primary_campaign_source": None},
        "associations": {"deals": ["D1"]},
        "rules": [{"property": "primary_campaign_source", "value": None}],
        "expect": "cannot_evaluate: source value absent at run time",
    },
    "missing_associated_contact": {
        "fixture_name": "missing_associated_contact", "asset_id": WF_DEMO,
        "record": {}, "current_values": {}, "associations": {"deals": []},
        "rules": [{"property": "requested_service", "value": "Code Analyzer"}],
        "expect": "stopped_safe: no target",
    },
    "inactive_owner_notification": {
        "fixture_name": "inactive_owner_notification", "asset_id": WF_DEMO,
        "record": {"linkage": "D1", "owner_state": "inactive"},
        "current_values": {"requested_service": None},
        "associations": {"deals": ["D1"]},
        "rules": [{"property": "requested_service", "value": "Code Analyzer",
                   "overwrite": "only_if_empty"}],
        "expect": "one proposed write; owner state surfaced by policy, not by simulation",
    },
    "duplicate_creator": {
        "fixture_name": "duplicate_creator", "asset_id": WF_DEMO,
        "record": {"linkage": "D1"},
        "current_values": {"dealname": "Acme - Demo"},
        "associations": {"deals": ["D1"]},
        "rules": [{"property": "dealname", "value": "Acme - Demo",
                   "overwrite": "only_if_empty"}],
        "expect": "would_skip: idempotent on replay",
    },
    "unresolved_zap_target": {
        "fixture_name": "unresolved_zap_target", "asset_id": "zapier:zap:285219462",
        "record": {}, "current_values": {}, "associations": {"deals": []},
        "rules": [],
        "expect": "stopped_safe: no target, Zap definition NOT_COLLECTED",
    },
}
