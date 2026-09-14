"""Raw-ingestion platform guardrails.

Covers the whole retained scope: migration planning is stable and idempotent,
extractors fail closed on a stale schema, HubSpot access is GET-only, the GTM
Campaign custom object and its associations land in raw tables, and no CRM
write path or writeback module has crept back in.
"""

import importlib.util
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_DIR = ROOT / "db"
EXTRACT_DIR = ROOT / "extract"

# The migration runner's retained plan, in apply order.
RETAINED_MIGRATIONS = [
    "03_hubspot_deals.sql",
    "04_hubspot_campaigns.sql",
    "06_original_traffic_source.sql",
    "07_gtm_campaigns.sql",
]

# Migrations deleted with the transform/automation/brand-inbound layers.
REMOVED_MIGRATIONS = [
    "05_deal_source_migration.sql",
    "08_brand_inbound_recovery.sql",
    "09_brand_inbound_grants.sql",
    "10_automation_digital_twin.sql",
    "11_automation_twin_grants.sql",
    "12_automation_twin_refresh.sql",
]

# HubSpot mutation would surface as one of these call shapes.
HTTP_WRITE_CALLS = ("requests.post", "requests.patch", "requests.put", "requests.delete")

# Module/directory names that must stay gone from the raw-only platform.
FORBIDDEN_PATHS = (
    "writeback", "automation_twin", "hermes", "hermes_shared", "hermes_crm_admin",
    "transform", "ingestion",
)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeCursor:
    """Records SQL instead of touching a database."""

    def __init__(self, rows=()):
        self.rows = list(rows)
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params=None):
        self.executed.append((" ".join(sql.split()), params))

    def fetchall(self):
        return [(row,) for row in self.rows]

    def fetchone(self):
        return None


class FakeConnection:
    def __init__(self, rows=()):
        self.cursor_obj = FakeCursor(rows)
        self.committed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeRequests:
    """Stand-in for the requests module that records GETs and bans writes."""

    def __init__(self, pages=()):
        self.pages = list(pages)
        self.get_calls = []

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return FakeResponse(self.pages.pop(0) if self.pages else {"results": []})

    def _forbidden(self, *_args, **_kwargs):
        raise AssertionError("extraction attempted a non-GET HubSpot request")

    post = patch = put = delete = _forbidden


class ExplodingRequests(FakeRequests):
    def get(self, *_args, **_kwargs):
        raise AssertionError("a request was issued when none was expected")


def _module_source(paths):
    return {path.name: path.read_text(encoding="utf-8") for path in paths}


class ModuleLoadMixin:
    @classmethod
    def setUpClass(cls):
        cls.runner = load_module("run_db_migrations", ROOT / "scripts" / "run_db_migrations.py")
        cls.deals = load_module("extract_deals", EXTRACT_DIR / "extract_deals.py")
        cls.gtm = load_module("extract_gtm_campaigns", EXTRACT_DIR / "extract_gtm_campaigns.py")


class MigrationPlanningTests(ModuleLoadMixin, unittest.TestCase):
    def test_plan_is_exactly_the_retained_migration_set(self):
        names = [name for name, _, _ in self.runner.migration_plan(ROOT)]
        self.assertEqual(names, RETAINED_MIGRATIONS)

    def test_plan_is_stable_and_checksums_are_deterministic(self):
        first = self.runner.migration_plan(ROOT)
        second = self.runner.migration_plan(ROOT)
        names = [name for name, _, _ in first]
        self.assertEqual(first, second, "repeat planning must not reorder or re-digest")
        self.assertEqual(names, sorted(names), "migrations must stay in numeric order")
        self.assertEqual(len(names), len(set(names)), "migration names must be unique")
        for _, _, checksum in first:
            self.assertRegex(checksum, r"^[0-9a-f]{64}$")

    def test_referenced_migrations_exist_on_disk(self):
        for name, path, _ in self.runner.migration_plan(ROOT):
            self.assertTrue(path.is_file(), f"{name} is referenced but missing")

    def test_removed_migrations_are_gone_and_unreferenced(self):
        for name in REMOVED_MIGRATIONS:
            self.assertNotIn(name, self.runner.MIGRATIONS)
            self.assertFalse((DB_DIR / name).exists(), f"{name} should have been deleted")

    def test_missing_migration_file_fails_before_database_work(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                self.runner.migration_plan(Path(directory))

    def test_every_migration_is_idempotent_ddl(self):
        for name, path, _ in self.runner.migration_plan(ROOT):
            sql = path.read_text(encoding="utf-8").upper()
            self.assertIn("IF NOT EXISTS", sql, f"{name} must use idempotent DDL")

    def test_rerun_skips_applied_migrations_by_checksum(self):
        """The runner must compare a recorded checksum rather than reapplying."""
        source = (ROOT / "scripts" / "run_db_migrations.py").read_text(encoding="utf-8")
        self.assertIn("checksum drift", source)
        self.assertIn("already applied, checksum verified", source)
        self.assertIn("pg_advisory_xact_lock", source)


class SchemaReadinessTests(ModuleLoadMixin, unittest.TestCase):
    def test_deal_extractor_accepts_complete_schema(self):
        self.deals.assert_live_schema_ready(FakeConnection(self.deals.REQUIRED_DEAL_COLUMNS))

    def test_deal_extractor_rejects_stale_schema_with_command(self):
        with self.assertRaisesRegex(RuntimeError, "run_db_migrations.py"):
            self.deals.assert_live_schema_ready(FakeConnection({"raw_properties"}))

    def test_required_deal_columns_are_supplied_by_retained_migrations(self):
        """Every column the live extractor needs must come from a kept migration."""
        sql = "\n".join(
            (DB_DIR / name).read_text(encoding="utf-8")
            for name in ("03_hubspot_deals.sql", "06_original_traffic_source.sql")
        ).lower()
        for column in self.deals.REQUIRED_DEAL_COLUMNS:
            self.assertIn(column.lower(), sql, f"{column} is not created by a retained migration")

    def test_gtm_extractor_accepts_complete_schema(self):
        self.gtm.assert_schema_ready(FakeConnection(self.gtm.REQUIRED_TABLES))

    def test_gtm_extractor_rejects_missing_tables_with_command(self):
        with self.assertRaisesRegex(RuntimeError, "run_db_migrations.py") as ctx:
            self.gtm.assert_schema_ready(FakeConnection({"hubspot_gtm_campaigns"}))
        message = str(ctx.exception)
        self.assertIn("hubspot_gtm_campaign_contacts", message)
        self.assertIn("hubspot_gtm_campaign_deals", message)

    def test_gtm_required_tables_are_created_by_migration_07(self):
        sql = (DB_DIR / "07_gtm_campaigns.sql").read_text(encoding="utf-8").lower()
        for table in self.gtm.REQUIRED_TABLES:
            self.assertIn(table.lower(), sql, f"{table} is not created by 07_gtm_campaigns.sql")


class ReadOnlyExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = _module_source(sorted(EXTRACT_DIR.glob("*.py")))

    def test_extract_directory_is_not_empty(self):
        self.assertTrue(self.sources, "retained extractors are missing")

    def test_no_extractor_issues_a_write_request(self):
        for name, source in self.sources.items():
            for call in HTTP_WRITE_CALLS:
                self.assertNotIn(call, source, f"{name} contains a {call} call")

    def test_every_hubspot_call_is_a_get(self):
        for name, source in self.sources.items():
            calls = re.findall(r"requests\.(\w+)\(", source)
            self.assertTrue(
                all(call == "get" for call in calls),
                f"{name} uses non-GET HTTP verbs: {sorted(set(calls) - {'get'})}",
            )

    def test_no_writeback_or_agent_source_remains(self):
        """No removed component may survive as tracked or importable source.

        Stale __pycache__/ or dbt build output left in a working copy is
        ignored: it carries no source, and CI checks out a clean tree.
        """
        tracked = set(
            subprocess.run(
                ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
            ).stdout.split()
        )
        for name in FORBIDDEN_PATHS:
            self.assertFalse(
                [path for path in tracked if path == name or path.startswith(f"{name}/")],
                f"{name}/ is still tracked in the raw-only platform",
            )
            self.assertFalse(
                list((ROOT / name).rglob("*.py")) if (ROOT / name).is_dir() else [],
                f"{name}/ still contains Python source",
            )
            self.assertFalse(
                list((ROOT / name).rglob("*.sql")) if (ROOT / name).is_dir() else [],
                f"{name}/ still contains SQL models",
            )

    def test_no_extractor_imports_a_removed_component(self):
        for name, source in self.sources.items():
            for forbidden in FORBIDDEN_PATHS:
                self.assertNotIn(
                    f"import {forbidden}", source,
                    f"{name} imports removed component {forbidden}",
                )

    def test_extractors_only_write_to_the_raw_schema(self):
        """Raw ingestion must never target analytics or a CRM writeback log."""
        for name, source in self.sources.items():
            self.assertNotIn("hubspot_writeback_log", source, f"{name} references a writeback log")
            for statement in re.findall(r"(?is)\binsert\s+into\s+([a-z_.]+)", source):
                self.assertTrue(
                    statement.lower().startswith("raw."),
                    f"{name} inserts into {statement}, outside the raw schema",
                )

    def test_ingestion_is_append_only(self):
        """No retained extractor may UPDATE or DELETE landed raw history."""
        for name, source in self.sources.items():
            self.assertNotRegex(
                source, r"(?is)\bupdate\s+raw\.", f"{name} updates raw history in place",
            )
            self.assertNotRegex(
                source, r"(?is)\bdelete\s+from\s+raw\.", f"{name} deletes raw history",
            )
            self.assertNotRegex(
                source, r"(?is)\btruncate\b", f"{name} truncates a table",
            )


class GtmCampaignExtractionTests(ModuleLoadMixin, unittest.TestCase):
    def setUp(self):
        self._saved_requests = sys.modules.get("requests")

    def tearDown(self):
        if self._saved_requests is None:
            sys.modules.pop("requests", None)
        else:
            sys.modules["requests"] = self._saved_requests

    def test_dry_run_issues_no_request(self):
        sys.modules["requests"] = ExplodingRequests()
        counts = self.gtm.extract(FakeConnection(), dry_run=True)
        self.assertEqual(counts, {"campaigns": 0, "contact_links": 0, "deal_links": 0})

    def test_campaign_and_associations_land_in_raw_tables(self):
        page = {
            "results": [
                {
                    "id": "9001",
                    "archived": False,
                    "properties": {
                        "gtm_campaign_name": "Q3 Security Push",
                        "hs_createdate": "2026-01-01T00:00:00Z",
                        "hs_lastmodifieddate": "2026-02-01T00:00:00Z",
                    },
                    "associations": {
                        "contacts": {"results": [{"id": "c1"}, {"id": "c2"}]},
                        "deals": {"results": [{"id": "d1"}]},
                    },
                }
            ]
        }
        fake = FakeRequests([page])
        sys.modules["requests"] = fake
        conn = FakeConnection()

        counts = self.gtm.extract(conn, dry_run=False)

        self.assertEqual(counts, {"campaigns": 1, "contact_links": 2, "deal_links": 1})
        self.assertTrue(conn.committed, "extraction must commit landed rows")
        targets = [sql for sql, _ in conn.cursor_obj.executed]
        self.assertTrue(any("raw.hubspot_gtm_campaigns" in sql for sql in targets))
        self.assertTrue(any("raw.hubspot_gtm_campaign_contacts" in sql for sql in targets))
        self.assertTrue(any("raw.hubspot_gtm_campaign_deals" in sql for sql in targets))

    def test_request_is_a_read_only_get_with_associations(self):
        fake = FakeRequests([{"results": []}])
        sys.modules["requests"] = fake
        self.gtm.extract(FakeConnection(), dry_run=False)

        self.assertEqual(len(fake.get_calls), 1)
        url, kwargs = fake.get_calls[0]
        self.assertIn(self.gtm.GTM_OBJECT_TYPE, url)
        self.assertEqual(kwargs["params"]["associations"], "contacts,deals")
        self.assertEqual(kwargs["params"]["archived"], "false")

    def test_association_edges_are_copied_not_inferred(self):
        """Only ids HubSpot returns may be landed — nothing derived from UTM."""
        page = {
            "results": [
                {
                    "id": "9002",
                    "properties": {"name": "Named"},
                    "associations": {"contacts": {"results": [{"id": "keep"}, {"nope": "x"}]}},
                }
            ]
        }
        sys.modules["requests"] = FakeRequests([page])
        conn = FakeConnection()

        counts = self.gtm.extract(conn, dry_run=False)

        self.assertEqual(counts["contact_links"], 1, "an id-less association must be skipped")
        params = [p for sql, p in conn.cursor_obj.executed if "campaign_contacts" in sql]
        self.assertEqual(params, [("9002", "keep")])

    def test_campaign_name_is_resolved_without_invention(self):
        self.assertEqual(self.gtm.resolve_name({"gtm_campaign_name": "First"}), "First")
        self.assertEqual(self.gtm.resolve_name({"name": "Fallback"}), "Fallback")
        self.assertIsNone(self.gtm.resolve_name({"gtm_campaign_name": "   "}))
        self.assertIsNone(self.gtm.resolve_name({}))


if __name__ == "__main__":
    unittest.main()
