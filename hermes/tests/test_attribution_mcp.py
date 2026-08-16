import unittest

from hermes.codex_mcp import (
    _attribution_defensibility,
    _claim_decision,
    _tracking_contract,
    _weekly_report_from_rows,
)


FUNNEL = [
    {"funnel_stage": "live_deal_population", "deal_count": 5388, "closed_won_deal_count": 1901, "coverage_of_live_deals_pct": "100.00"},
    {"funnel_stage": "associated_contact", "deal_count": 3484, "closed_won_deal_count": 1161, "coverage_of_live_deals_pct": "64.66"},
    {"funnel_stage": "clean_first_touch_utm", "deal_count": 1119, "closed_won_deal_count": 34, "coverage_of_live_deals_pct": "20.77"},
    {"funnel_stage": "predeal_form_evidence", "deal_count": 0, "closed_won_deal_count": 0, "coverage_of_live_deals_pct": "0.00"},
    {"funnel_stage": "website_click_evidence", "deal_count": 0, "closed_won_deal_count": 0, "coverage_of_live_deals_pct": "0.00"},
]
INVENTORY = [
    {"evidence_type": "website_click", "availability": "unavailable"},
    {"evidence_type": "form_submission", "availability": "available", "available_fields": "engagement_id, contact_id, timestamp, campaign_id"},
    {"evidence_type": "bot_or_junk_signal", "availability": "unavailable"},
]


class AttributionSafetyTests(unittest.TestCase):
    def test_email_click_is_never_website_click(self):
        contract = _tracking_contract()
        self.assertIn("email_click must not be mapped to website_click", contract["prohibited_substitutions"])
        self.assertEqual(_attribution_defensibility(FUNNEL, INVENTORY)["website_click_roi"], "unsupported_event_unavailable")

    def test_form_roi_requires_temporal_event_evidence(self):
        result = _claim_decision("form_to_deal_roi", FUNNEL, INVENTORY)
        self.assertFalse(result["supported"])
        self.assertEqual(result["status"], "unsupported_missing_temporal_or_event_level_evidence")

        predeal_without_event_fields = [
            {**row, "deal_count": 25}
            if row["funnel_stage"] == "predeal_form_evidence"
            else row
            for row in FUNNEL
        ]
        result = _claim_decision("form_to_deal_roi", predeal_without_event_fields, INVENTORY)
        self.assertFalse(result["supported"])

    def test_bot_claim_requires_deterministic_evidence(self):
        result = _claim_decision("bot_or_junk", FUNNEL, INVENTORY)
        self.assertFalse(result["supported"])
        self.assertEqual(result["status"], "unsupported_no_deterministic_signal")

    def test_crm_write_is_always_prohibited(self):
        result = _claim_decision("crm_write", FUNNEL, INVENTORY)
        self.assertEqual(result["status"], "prohibited")
        self.assertIn("never recommend CRM writes", result["reason"])

    def test_weekly_report_is_read_only_and_evidence_bound(self):
        report = _weekly_report_from_rows(FUNNEL, [], INVENTORY)
        self.assertEqual(report["defensibility"]["web_to_form_to_deal_to_won"], "not_defensible")
        self.assertIn("do not write CRM records", report["recommended_next_step"])


if __name__ == "__main__":
    unittest.main()
