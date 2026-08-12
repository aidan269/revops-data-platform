import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeCursor:
    def __init__(self, columns):
        self.columns = columns

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, *_):
        return None

    def fetchall(self):
        return [(column,) for column in self.columns]


class FakeConnection:
    def __init__(self, columns):
        self.columns = columns

    def cursor(self):
        return FakeCursor(self.columns)


class DatabaseMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = load_module("run_db_migrations", ROOT / "scripts" / "run_db_migrations.py")
        cls.extractor = load_module("extract_deals", ROOT / "extract" / "extract_deals.py")

    def test_order_is_stable_and_checksums_are_deterministic(self):
        first = self.runner.migration_plan(ROOT)
        second = self.runner.migration_plan(ROOT)
        names = [item[0] for item in first]
        # The ordered prefix is fixed; later migrations append without reordering.
        self.assertEqual(names[:3], [
            "03_hubspot_deals.sql", "04_hubspot_campaigns.sql", "05_deal_source_migration.sql",
        ])
        self.assertEqual(names, sorted(names), "migrations must stay in numeric order")
        self.assertEqual(len(names), len(set(names)), "migration names must be unique")
        self.assertEqual(first, second)
        self.assertTrue(all(len(checksum) == 64 for _, _, checksum in first))

    def test_missing_migration_file_fails_before_database_work(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                self.runner.migration_plan(Path(directory))

    def test_existing_sql_is_safe_for_repeat_runs(self):
        for name, path, _ in self.runner.migration_plan(ROOT):
            sql = path.read_text(encoding="utf-8").upper()
            self.assertTrue(
                "IF NOT EXISTS" in sql,
                f"{name} must use idempotent DDL",
            )

    def test_extractor_accepts_complete_schema(self):
        self.extractor.assert_live_schema_ready(
            FakeConnection(self.extractor.REQUIRED_DEAL_COLUMNS)
        )

    def test_extractor_rejects_stale_schema_with_command(self):
        with self.assertRaisesRegex(RuntimeError, "run_db_migrations.py"):
            self.extractor.assert_live_schema_ready(FakeConnection({"raw_properties"}))


if __name__ == "__main__":
    unittest.main()
