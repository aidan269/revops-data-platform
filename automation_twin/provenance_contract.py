"""Fix 2 — proposed canonical property contract for Lead Data Provider.

LOCAL DEFINITION ONLY. This does not create, modify, or request a HubSpot
property. It renders an approval-ready proposal for a human to act on.
"""
from __future__ import annotations

LEAD_DATA_PROVIDER_CONTRACT: dict = {
    "proposal_id": "ADT-PROP-LEAD-DATA-PROVIDER",
    "status": "PROPOSED_NOT_CREATED",
    "internal_name": "lead_data_provider",
    "label": "Lead Data Provider",
    "object_type": "CONTACT",
    "field_type": "single-line text",
    "description": (
        "Which enrichment or list-building tool supplied this contact record. "
        "Provenance evidence only. Never campaign attribution."
    ),
    "allowed_values": ["Apollo", "Findymail", "LeadMagic", "Prospeo", "Icypeas",
                       "User Managed", "Clay", "Nooks", "Read AI", "Make"],
    "ownership": "RevOps",
    "allowed_writers": ["CSV import templates with an approved provenance mapping"],
    "forbidden_writers": ["any automation that also writes a protected attribution field"],
    "overwrite_rules": "write only when empty; never overwrite an existing provider value",
    "null_behavior": "blank is valid and means provenance unknown; never backfill a guess",
    "relationship_to_campaign_attribution": (
        "Strictly disjoint from primary_campaign_source and latest_campaign_source. "
        "A value belonging in this field must never be written to either."
    ),
    "migration_plan": [
        "1. Create the property (human action, separate approval).",
        "2. Repoint import templates so provenance columns map here.",
        "3. Only then consider historical remediation, per exact-record approval.",
    ],
    "rollback_plan": (
        "The property is additive. Rollback is to stop mapping to it and, if required, "
        "delete the property; no existing attribution value is modified at any step."
    ),
    "authorizes_external_write": False,
}
