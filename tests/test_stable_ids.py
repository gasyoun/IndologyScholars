import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


build = load_module("build_and_populate_db_under_test", "build_and_populate_db.py")
compare_manifests = load_module("compare_id_manifests_under_test", "scratch/compare_id_manifests.py")
export_manifest = load_module("export_presentation_id_manifest_under_test", "scratch/export_presentation_id_manifest.py")


class StableIdTests(unittest.TestCase):
    def test_canonical_id_text_normalizes_spacing_case_and_nbsp(self):
        self.assertEqual(build.canonical_id_text("  PRES\u00a0Title \n With   Space  "), "pres title with space")
        self.assertEqual(export_manifest.canonical_text("  PRES\u00a0Title \n With   Space  "), "pres title with space")

    def test_stable_hash_is_deterministic_and_normalized(self):
        first = build.stable_hash("Zograf", 2026, "  Test\u00a0Title  ", length=12)
        second = build.stable_hash("zograf", "2026", "test title", length=12)
        self.assertEqual(first, second)
        self.assertRegex(first, r"^[0-9a-f]{12}$")

    def test_stable_ids_keep_expected_prefixes(self):
        presentation_id = build.stable_presentation_id("zograf", 2026, "A Title", "Ivanov I. I.", 7)
        zograf_session_id = build.stable_session_id("zograf", 2026, "day-1", "Morning", "10:00", "source.html", "line")
        roerich_session_id = build.stable_session_id("roerich", 2026, "day-1", "Morning", "10:00", "source.html", "line")

        self.assertRegex(presentation_id, r"^PRES_[0-9a-f]{10}$")
        self.assertRegex(zograf_session_id, r"^SESS_[0-9a-f]{10}$")
        self.assertRegex(roerich_session_id, r"^SESS_R_[0-9a-f]{10}$")

    def test_compare_manifests_reports_clean_unchanged_rebuild(self):
        before = [
            {
                "presentation_id": "PRES_abc",
                "stable_key_candidate": "key-1",
                "year": "2026",
                "series": "Zograf Readings",
                "title": "A Title",
                "first_speaker": "Ivanov I. I.",
                "source_url": "source.html",
            }
        ]
        after = [dict(before[0])]

        audit = compare_manifests.compare(before, after)
        summary = audit["summary"]

        self.assertEqual(summary["before_rows"], 1)
        self.assertEqual(summary["after_rows"], 1)
        self.assertEqual(summary["changed_ids_for_same_stable_key"], 0)
        self.assertEqual(summary["missing_stable_keys_after"], 0)
        self.assertEqual(summary["new_stable_keys_after"], 0)
        self.assertEqual(summary["after_duplicate_stable_key_rows"], 0)

    def test_compare_manifests_detects_changed_id_for_same_stable_key(self):
        before = [{"presentation_id": "PRES_old", "stable_key_candidate": "key-1"}]
        after = [{"presentation_id": "PRES_new", "stable_key_candidate": "key-1"}]

        audit = compare_manifests.compare(before, after)

        self.assertEqual(audit["summary"]["changed_ids_for_same_stable_key"], 1)
        self.assertEqual(
            audit["changed_ids_for_same_stable_key_records"][0]["before_presentation_id"],
            "PRES_old",
        )
        self.assertEqual(
            audit["changed_ids_for_same_stable_key_records"][0]["after_presentation_id"],
            "PRES_new",
        )


if __name__ == "__main__":
    unittest.main()
