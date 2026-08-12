#!/usr/bin/env python3
"""BRAND-INBOUND-RECOVERY — idempotent import of historical brand inbound evidence.

Loads the human-maintained CSV line-by-line sheet and the Twitter/X cross-check PDF
into append-only local warehouse tables. Historical evidence only: this writes
nothing to HubSpot and authorizes no CRM change.

Re-running is safe. Rows are keyed by (source_sha256, source_row_number) and
(csv_source_sha256, deal_id) with ON CONFLICT DO NOTHING.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

import psycopg2
from psycopg2.extras import Json

ROOT = Path(__file__).resolve().parents[1]

# Evidence locations are supplied at runtime; no developer filesystem is hardcoded.
#   BRAND_INBOUND_CSV / BRAND_INBOUND_PDF  explicit file paths, or
#   REVOPS_EVIDENCE_ROOT                   directory containing both by their known names
CSV_NAME = "Combined Brand Inbound Analysis [Feb 14 2026] - Line by Line.csv"
PDF_NAME = ("Twitter_deals_overwritten_to_Offline_-_before-after"
            " - Twitter deals overwritten.pdf")
_EVIDENCE_ROOT = Path(os.getenv("REVOPS_EVIDENCE_ROOT", "."))
CSV_PATH = Path(os.getenv("BRAND_INBOUND_CSV", _EVIDENCE_ROOT / CSV_NAME))
PDF_PATH = Path(os.getenv("BRAND_INBOUND_PDF", _EVIDENCE_ROOT / PDF_NAME))

EXPECTED_CSV_SHA = "2be0f1ed4996d0b5efedfe494f6aab7dcea968f19eb7ab96eaa933857982fce9"
EXPECTED_PDF_SHA = "39a4dd0aa3635db5023b1eff66efe2c4cc19ee2770ff42ca6d300303f6715d77"

EXPECTED_ROWS = 353
EXPECTED_TWITTER = 29
EXPECTED_LINKS = 283
EXPECTED_DEAL_LINKS = 282
EXPECTED_COMPANY_LINKS = 1
EXPECTED_CROSSCHECKED = 27
EXPECTED_OVERWRITTEN = 22
EXPECTED_INTACT = 5

TWITTER_SOURCE_VALUE = "Twitter / X"
EVIDENCE_DATE = "2026-07-15"          # PDF: live HubSpot observed on this date
EVIDENCE_PERIOD = "Dec 2025 - Feb 2026"

LINK_RE = re.compile(r"/record/(0-\d+)/(\d+)")

CSV_FIELDS = [
    ("Month", "month_raw"),
    ("Deal Name", "deal_name_raw"),
    ("Organisation Name", "organisation_name_raw"),
    ("ICP Fit", "icp_fit_raw"),
    ("Source", "source_raw"),
    ("Current Stage", "current_stage_raw"),
    ("Solution Requested", "solution_requested_raw"),
    ("Call booked?", "call_booked_raw"),
    ("Days to move to Discovery", "days_to_discovery_raw"),
    ("Days to Scope Complete (if applicable)", "days_to_scope_complete_raw"),
    ("Days to Call Booked (If applicable)", "days_to_call_booked_raw"),
    ("Days to Next Follow Up/Stage", "days_to_next_follow_up_raw"),
    ("AE Name", "ae_name_raw"),
    ("Deals?", "deals_raw"),
    ("Hubspot Link", "hubspot_link_raw"),
    ("GMV", "gmv_raw"),
    ("Revenue", "revenue_raw"),
    ("ARR", "arr_raw"),
]

NUMERIC_PAIRS = [
    ("days_to_discovery_raw", "days_to_discovery_num"),
    ("days_to_scope_complete_raw", "days_to_scope_complete_num"),
    ("days_to_call_booked_raw", "days_to_call_booked_num"),
    ("days_to_next_follow_up_raw", "days_to_next_follow_up_num"),
    ("deals_raw", "deals_num"),
    ("gmv_raw", "gmv_num"),
    ("revenue_raw", "revenue_num"),
    ("arr_raw", "arr_num"),
]

# The PDF identifies deals by NAME ONLY and contains no HubSpot record IDs.
# This mapping is the auditable, hand-verified name correspondence to CSV deal
# IDs. Eight of the 27 names differ in wording, case, or truncation between the
# two sources; name_match_exact records which.
#   deal_id: (pdf_deal_name, pdf_current_source, overwrite_status, mechanism, closed_won)
PDF_CROSSCHECK: dict[str, tuple[str, str, str, str, str]] = {
    "52071473447": ("Chronicle Labs - protocol-governance", "Offline Sources", "OVERWRITTEN", "Manual CRM entry (CRM_UI)", "Yes"),
    "53418959731": ("Solana Foundation ARR deal", "Offline Sources", "OVERWRITTEN", "Integration / enrichment sync (INTEGRATION)", "Yes"),
    "53421607764": ("Initia - Code Analyzer", "Offline Sources", "OVERWRITTEN", "Integration / enrichment sync (INTEGRATION)", "No"),
    "53404010115": ("dHEDGE - AI Code Analyzer", "Offline Sources", "OVERWRITTEN", "Integration / enrichment sync (INTEGRATION)", "No"),
    "53404788367": ("SenseiLang - AI Code Analyzer", "Offline Sources", "OVERWRITTEN", "Integration / enrichment sync (INTEGRATION)", "No"),
    "53398604650": ("IbxLab", "Offline Sources", "OVERWRITTEN", "Integration / enrichment sync (INTEGRATION)", "No"),
    "53442627497": ("EF", "Offline Sources", "OVERWRITTEN", "Integration / enrichment sync (INTEGRATION)", "No"),
    "53398768905": ("Tailwind", "Offline Sources", "OVERWRITTEN", "Integration / enrichment sync (INTEGRATION)", "No"),
    "53414602624": ("Sola", "Offline Sources", "OVERWRITTEN", "Integration / enrichment sync (INTEGRATION)", "No"),
    "53404230444": ("React Wallet", "Offline Sources", "OVERWRITTEN", "Integration / enrichment sync (INTEGRATION)", "No"),
    "53454431883": ("Solulab", "Offline Sources", "OVERWRITTEN", "Integration / enrichment sync (INTEGRATION)", "No"),
    "53498769423": ("Offchain Labs - Apex", "Offline Sources", "OVERWRITTEN", "CSV import (IMPORT)", "No"),
    "53735855033": ("unimodular", "Offline Sources", "OVERWRITTEN", "Integration / enrichment sync (INTEGRATION)", "No"),
    "54112788100": ("Tempus Finance (Nostra Finance)", "Offline Sources", "OVERWRITTEN", "Integration / enrichment sync (INTEGRATION)", "No"),
    "54205709633": ("Wormhole Labs - Code Analyzer", "Offline Sources", "OVERWRITTEN", "CSV import (IMPORT)", "No"),
    "54217602083": ("Openfort", "Offline Sources", "OVERWRITTEN", "Manual CRM entry (CRM_UI)", "No"),
    "54386580351": ("POK Vault", "Offline Sources", "OVERWRITTEN", "Integration / enrichment sync (INTEGRATION)", "No"),
    "54651832985": ("DLT Maritime", "Offline Sources", "OVERWRITTEN", "Integration / enrichment sync (INTEGRATION)", "No"),
    "54793808304": ("Alchemix - AI Scan", "Offline Sources", "OVERWRITTEN", "Manual CRM entry (CRM_UI)", "No"),
    "54987553675": ("QSTN", "Offline Sources", "OVERWRITTEN", "Integration / enrichment sync (INTEGRATION)", "No"),
    "55380793136": ("Urban Tiger", "Offline Sources", "OVERWRITTEN", "Integration / enrichment sync (INTEGRATION)", "No"),
    "55903233116": ("Silicon Inc", "Offline Sources", "OVERWRITTEN", "Integration / enrichment sync (INTEGRATION)", "No"),
    "57164950441": ("Ekubo - Apex Scan", "Organic Social (Twitter)", "STILL_INTACT", "— (still intact)", "No"),
    "57035627041": ("Galaxy - Apex Scan", "Organic Social (Twitter)", "STILL_INTACT", "— (still intact)", "No"),
    "56892667034": ("Skatechain - Code Analyzer Waitlist", "Organic Social (Twitter)", "STILL_INTACT", "— (still intact)", "No"),
    "56875071664": ("Raise - Code Analyzer", "Organic Social (Twitter)", "STILL_INTACT", "— (still intact)", "No"),
    "56296085508": ("Lighthouse Labs - Code Analyzer One-Off", "Organic Social (Twitter)", "STILL_INTACT", "— (still intact)", "No"),
}

NOT_CROSSCHECKED_EXPECTED = {"53398797749", "54040556044"}

CROSSCHECKED_LIMITATION = (
    "PDF carries no HubSpot record IDs; deal_id resolved by deal-name correspondence to the CSV. "
    "PDF observed live HubSpot on 2026-07-15, so current CRM state may since have changed. "
    "observed_mechanism is the HubSpot drill-down label only and is not a causal attribution."
)
NOT_CROSSCHECKED_LIMITATION = (
    "Present in the CSV as Twitter / X but absent from the PDF cross-check. "
    "Neither clean nor corrupted: current source was never observed for this deal."
)
CREATION_SOURCE = "AUTOMATION_PLATFORM (record source at creation, per PDF)"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_numeric(value: str | None):
    """Return a Decimal only when the cell is unambiguously numeric, else None."""
    if value is None:
        return None
    cleaned = value.strip().replace(",", "").replace("$", "")
    if not cleaned or cleaned.upper() in {"N/A", "NA", "-", "TBD", "?"}:
        return None
    if cleaned.endswith("%"):
        return None
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def parse_link(link: str | None) -> tuple[str | None, str | None]:
    if not link or not link.strip():
        return None, None
    match = LINK_RE.search(link.strip())
    if not match:
        return None, None
    return match.group(1), match.group(2)


def read_csv_rows() -> list[dict]:
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
    parsed: list[dict] = []
    current_month = None
    for index, row in enumerate(rows, start=1):
        record: dict = {"source_row_number": index}
        for source_name, column in CSV_FIELDS:
            record[column] = row.get(source_name)
        month = (record.get("month_raw") or "").strip()
        if month:
            current_month = month
        record["report_month_filled"] = current_month
        object_type, record_id = parse_link(record.get("hubspot_link_raw"))
        record["hubspot_object_type"] = object_type
        record["hubspot_record_id"] = record_id
        record["is_deal_link"] = (object_type == "0-3") if object_type else None
        for raw_col, num_col in NUMERIC_PAIRS:
            record[num_col] = parse_numeric(record.get(raw_col))
        record["raw_row"] = {k: v for k, v in row.items()}
        parsed.append(record)
    return parsed


def validate_sources(rows: list[dict], csv_sha: str, pdf_sha: str) -> dict:
    """Fail closed before any load if the evidence does not match its controls."""
    problems: list[str] = []
    if csv_sha != EXPECTED_CSV_SHA:
        problems.append(f"csv sha256 mismatch: {csv_sha}")
    if pdf_sha != EXPECTED_PDF_SHA:
        problems.append(f"pdf sha256 mismatch: {pdf_sha}")
    if len(rows) != EXPECTED_ROWS:
        problems.append(f"expected {EXPECTED_ROWS} rows, found {len(rows)}")

    twitter = [r for r in rows if (r.get("source_raw") or "").strip() == TWITTER_SOURCE_VALUE]
    if len(twitter) != EXPECTED_TWITTER:
        problems.append(f"expected {EXPECTED_TWITTER} Twitter rows, found {len(twitter)}")

    links = [r for r in rows if (r.get("hubspot_link_raw") or "").strip()]
    deal_links = [r for r in links if r["hubspot_object_type"] == "0-3"]
    company_links = [r for r in links if r["hubspot_object_type"] == "0-2"]
    if len(links) != EXPECTED_LINKS:
        problems.append(f"expected {EXPECTED_LINKS} links, found {len(links)}")
    if len(deal_links) != EXPECTED_DEAL_LINKS:
        problems.append(f"expected {EXPECTED_DEAL_LINKS} deal links, found {len(deal_links)}")
    if len(company_links) != EXPECTED_COMPANY_LINKS:
        problems.append(f"expected {EXPECTED_COMPANY_LINKS} company link, found {len(company_links)}")

    overwritten = sum(1 for v in PDF_CROSSCHECK.values() if v[2] == "OVERWRITTEN")
    intact = sum(1 for v in PDF_CROSSCHECK.values() if v[2] == "STILL_INTACT")
    if len(PDF_CROSSCHECK) != EXPECTED_CROSSCHECKED:
        problems.append(f"expected {EXPECTED_CROSSCHECKED} cross-checked, found {len(PDF_CROSSCHECK)}")
    if overwritten != EXPECTED_OVERWRITTEN:
        problems.append(f"expected {EXPECTED_OVERWRITTEN} overwritten, found {overwritten}")
    if intact != EXPECTED_INTACT:
        problems.append(f"expected {EXPECTED_INTACT} intact, found {intact}")

    twitter_ids = {r["hubspot_record_id"] for r in twitter}
    pdf_ids = set(PDF_CROSSCHECK)
    if not pdf_ids.issubset(twitter_ids):
        problems.append(f"pdf ids not a subset of csv twitter ids: {sorted(pdf_ids - twitter_ids)}")
    if twitter_ids - pdf_ids != NOT_CROSSCHECKED_EXPECTED:
        problems.append(
            f"unexpected NOT_CROSSCHECKED set: {sorted(twitter_ids - pdf_ids)}"
        )

    if problems:
        raise SystemExit("[validate] FAILED before load:\n  - " + "\n  - ".join(problems))

    print(f"[validate] ok: {len(rows)} rows, {len(twitter)} twitter, "
          f"{len(links)} links ({len(deal_links)} deal / {len(company_links)} company), "
          f"{len(PDF_CROSSCHECK)} cross-checked ({overwritten} overwritten / {intact} intact)")
    return {"rows": rows, "twitter": twitter}


def build_crosscheck_rows(twitter: list[dict], csv_sha: str, pdf_sha: str) -> list[dict]:
    out = []
    for row in sorted(twitter, key=lambda r: r["hubspot_record_id"]):
        deal_id = row["hubspot_record_id"]
        csv_name = (row.get("deal_name_raw") or "").strip()
        entry = PDF_CROSSCHECK.get(deal_id)
        if entry:
            pdf_name, current_source, status, mechanism, closed_won = entry
            out.append({
                "csv_source_sha256": csv_sha,
                "pdf_source_sha256": pdf_sha,
                "pdf_source_filename": PDF_PATH.name,
                "deal_id": deal_id,
                "csv_deal_name": csv_name,
                "csv_organisation_name": (row.get("organisation_name_raw") or "").strip(),
                "csv_source_value": (row.get("source_raw") or "").strip(),
                "crosscheck_status": "CROSSCHECKED",
                "pdf_deal_name": pdf_name,
                "pdf_current_source": current_source,
                "overwrite_status": status,
                "observed_mechanism": mechanism,
                "observed_creation_source": CREATION_SOURCE,
                "closed_won_flag": closed_won,
                "name_match_exact": pdf_name.strip().lower() == csv_name.strip().lower(),
                "evidence_date": EVIDENCE_DATE,
                "evidence_limitations": CROSSCHECKED_LIMITATION,
            })
        else:
            out.append({
                "csv_source_sha256": csv_sha,
                "pdf_source_sha256": pdf_sha,
                "pdf_source_filename": PDF_PATH.name,
                "deal_id": deal_id,
                "csv_deal_name": csv_name,
                "csv_organisation_name": (row.get("organisation_name_raw") or "").strip(),
                "csv_source_value": (row.get("source_raw") or "").strip(),
                "crosscheck_status": "NOT_CROSSCHECKED",
                "pdf_deal_name": None,
                "pdf_current_source": None,
                "overwrite_status": None,
                "observed_mechanism": None,
                "observed_creation_source": None,
                "closed_won_flag": None,
                "name_match_exact": None,
                "evidence_date": None,
                "evidence_limitations": NOT_CROSSCHECKED_LIMITATION,
            })
    return out


def load(database_url: str, rows: list[dict], crosscheck: list[dict],
         csv_sha: str, pdf_sha: str) -> dict:
    counts = {}
    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", (714008,))
            for kind, filename, sha, count, notes in (
                ("csv_line_by_line", CSV_PATH.name, csv_sha, len(rows),
                 "Human-maintained line-by-line brand inbound sheet. Historical evidence, not CRM truth."),
                ("pdf_twitter_crosscheck", PDF_PATH.name, pdf_sha, len(PDF_CROSSCHECK),
                 "Twitter/X before-after cross-check. Identifies deals by name only; contains no record IDs."),
            ):
                cur.execute(
                    """INSERT INTO raw.brand_inbound_imports
                         (source_kind, source_filename, source_sha256, source_row_count,
                          evidence_period, evidence_observed_on, notes)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (source_kind, source_sha256) DO NOTHING""",
                    (kind, filename, sha, count, EVIDENCE_PERIOD, EVIDENCE_DATE, notes),
                )

            line_cols = [
                "source_sha256", "source_filename", "source_row_number",
                *[c for _, c in CSV_FIELDS],
                "report_month_filled", "hubspot_object_type", "hubspot_record_id", "is_deal_link",
                *[n for _, n in NUMERIC_PAIRS],
                "raw_row",
            ]
            placeholders = ", ".join(["%s"] * len(line_cols))
            statement = (
                f"INSERT INTO raw.brand_inbound_lines ({', '.join(line_cols)}) "
                f"VALUES ({placeholders}) ON CONFLICT (source_sha256, source_row_number) DO NOTHING"
            )
            inserted_lines = 0
            for row in rows:
                values = [csv_sha, CSV_PATH.name, row["source_row_number"]]
                values += [row.get(c) for _, c in CSV_FIELDS]
                values += [row["report_month_filled"], row["hubspot_object_type"],
                           row["hubspot_record_id"], row["is_deal_link"]]
                values += [row.get(n) for _, n in NUMERIC_PAIRS]
                values.append(Json(row["raw_row"]))
                cur.execute(statement, values)
                inserted_lines += cur.rowcount
            counts["lines_inserted"] = inserted_lines

            cc_cols = list(crosscheck[0].keys())
            cc_stmt = (
                f"INSERT INTO raw.brand_inbound_twitter_crosscheck ({', '.join(cc_cols)}) "
                f"VALUES ({', '.join(['%s'] * len(cc_cols))}) "
                f"ON CONFLICT (csv_source_sha256, deal_id) DO NOTHING"
            )
            inserted_cc = 0
            for row in crosscheck:
                cur.execute(cc_stmt, [row[c] for c in cc_cols])
                inserted_cc += cur.rowcount
            counts["crosscheck_inserted"] = inserted_cc

            cur.execute("SELECT count(*) FROM raw.brand_inbound_lines")
            counts["lines_total"] = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM raw.brand_inbound_twitter_crosscheck")
            counts["crosscheck_total"] = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM raw.brand_inbound_imports")
            counts["imports_total"] = cur.fetchone()[0]
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"),
                        help="explicit PostgreSQL URL (required; no implicit default)")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    csv_sha = sha256_of(CSV_PATH)
    pdf_sha = sha256_of(PDF_PATH)
    print(f"[source] csv sha256={csv_sha}")
    print(f"[source] pdf sha256={pdf_sha}")

    rows = read_csv_rows()
    validated = validate_sources(rows, csv_sha, pdf_sha)
    crosscheck = build_crosscheck_rows(validated["twitter"], csv_sha, pdf_sha)

    if args.validate_only:
        print("[import] validate-only; no database write attempted")
        return
    if not args.database_url:
        raise SystemExit("[import] --database-url or DATABASE_URL is required")

    counts = load(args.database_url, rows, crosscheck, csv_sha, pdf_sha)
    print(f"[import] lines inserted={counts['lines_inserted']} total={counts['lines_total']}")
    print(f"[import] crosscheck inserted={counts['crosscheck_inserted']} total={counts['crosscheck_total']}")
    print(f"[import] imports total={counts['imports_total']}")
    print("[import] complete — no HubSpot or CRM write occurred")


if __name__ == "__main__":
    main()
