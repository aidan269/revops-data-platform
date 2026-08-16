# RevOps cleanup workflow

`mart_deal_cleanup_queue_live` is a review queue, not a writeback job. It
separates direct company-association evidence from contact-derived company
information and prioritizes active deals with an amount before historical work.

Use only evidence-backed actions:

1. Confirm or add a direct company association when the queue identifies none.
2. Fill Deal Source only when UTM, campaign, referral, or another documented
   source provides enough evidence.
3. Leave ambiguous records blank and record the reason; do not manufacture
   attribution to improve a coverage metric.
