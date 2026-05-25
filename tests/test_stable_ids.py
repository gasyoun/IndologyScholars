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
publication_helpers = load_module("publication_helpers_under_test", "publication_helpers.py")
title_normalization = load_module("title_normalization_under_test", "title_normalization.py")
compare_manifests = load_module("compare_id_manifests_under_test", "scratch/compare_id_manifests.py")
export_manifest = load_module("export_presentation_id_manifest_under_test", "scratch/export_presentation_id_manifest.py")


class StableIdTests(unittest.TestCase):
    def test_canonical_id_text_normalizes_spacing_case_and_nbsp(self):
        self.assertEqual(build.canonical_id_text("  PRES\u00a0Title \n With   Space  "), "pres title with space")
        self.assertEqual(export_manifest.canonical_text("  PRES\u00a0Title \n With   Space  "), "pres title with space")

    def test_time_interval_uses_colons_and_spaced_en_dash(self):
        self.assertEqual(
            publication_helpers.normalize_time_interval("15.00 – 18.30"),
            "15:00 – 18:30",
        )
        self.assertEqual(
            publication_helpers.normalize_time_interval("10:00—12:30"),
            "10:00 – 12:30",
        )

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

    def test_public_title_normalization_capitalizes_named_texts(self):
        self.assertEqual(
            title_normalization.canonical_title(None, "версия «рамаяны» и история индии"),
            "версия «Рамаяны» и история Индии",
        )

    def test_public_title_override_removes_collapsed_2023_program_tail(self):
        self.assertEqual(
            title_normalization.canonical_title("PRES_956381eb58", "ignored source tail"),
            "Анализ аморальных поступков в «Абхидхармакоше» Васубандху",
        )

    def test_packed_zograf_line_separates_obninsk_talk(self):
        line = (
            "Малютин Иван Иванович (Санкт-Петербург). Средний залог в санскрите."
            "Гасунс Марцис Юрьевич (Обнинск). Древнеиндийская ономастика"
        )
        fragments = build.split_packed_zograf_lines([line])
        self.assertEqual(len(fragments), 2)
        self.assertIn("Гасунс Марцис Юрьевич (Обнинск)", fragments[1])

    def test_title_name_in_parentheses_is_not_split_as_a_speaker(self):
        line = (
            "Н.В.Хомутинникова. Опровержение атомизма в трактате "
            "Васубандху Виджняптиматратасиддхи («Доказательство единственности сознания»)."
        )
        fragments = build.split_packed_zograf_lines([line])
        self.assertEqual(fragments, [line])

    def test_wrapped_talk_title_is_coalesced(self):
        lines = [
            "Мотылёва Вера Леонидовна (Москва). Седукова Надежда Александровна",
            "(Новгород). Востоковед Павел Яковлевич Петров (1814–1875), его",
            "библиотека и архив.",
            "Возчиков Дмитрий Викторович (Екатеринбург). Следующий доклад.",
        ]
        merged = build.coalesce_zograf_talk_lines(lines, 2026)
        self.assertEqual(len(merged), 2)
        self.assertIn("Павел Яковлевич Петров (1814–1875)", merged[0])

    def test_initialled_speaker_starts_new_packed_entry_without_terminal_period(self):
        line = (
            "О.Н. Ерченков (Ленинградская обл.). Об особенностях герменевтики "
            "А. Ковалевская (Гамбург). Способы сокрытия мантр"
        )
        fragments = build.split_packed_zograf_lines([line])
        self.assertEqual(len(fragments), 2)
        self.assertIn("А. Ковалевская (Гамбург)", fragments[1])

    def test_institution_in_title_does_not_create_a_new_speaker(self):
        line = "А. Н. Бабин. Живопись из собрания И. П. Минаева (МАЭ РАН): опыт классификации"
        self.assertEqual(build.split_packed_zograf_lines([line]), [line])

    def test_initialled_coauthors_are_one_presentation(self):
        parsed = build.parse_zograf_talk_line(
            "М. Б. Демченко (Москва), М. Рамдхари (Маврикий). Индийские языки"
        )
        self.assertEqual(len(parsed[0]), 2)
        self.assertEqual(parsed[1], "Индийские языки")

    def test_initialled_coauthors_without_affiliation_are_one_presentation(self):
        parsed = build.parse_zograf_talk_line(
            "А. Ю. Курочкин, Д. А. Шереметьев. Тальварная рукоять и ее символика"
        )
        self.assertEqual(len(parsed[0]), 2)
        self.assertEqual(parsed[1], "Тальварная рукоять и ее символика")

    def test_initials_broken_over_html_lines_are_rejoined(self):
        lines = [
            "Е.П. Островская (СПб). Брахман в трактате.",
            "Н.В.",
            "Александрова (Москва). Чайтья в трех версиях.",
        ]
        merged = build.coalesce_zograf_talk_lines(lines, 2022)
        self.assertEqual(len(merged), 2)
        self.assertIn("Н.В. Александрова", merged[1])

    def test_session_heading_does_not_extend_previous_title(self):
        lines = [
            "\u0412. \u041c. \u0428\u0435\u043b\u043a\u043e\u0432\u0438\u0447 (\u0421\u041f\u0431). \u041c\u043e\u0434\u0435\u043b\u0438 \u0432\u0440\u0435\u043c\u0435\u043d\u0438.",
            "\u0414\u043d\u0435\u0432\u043d\u043e\u0435 \u0437\u0430\u0441\u0435\u0434\u0430\u043d\u0438\u0435, \u043d\u0430\u0447\u0430\u043b\u043e \u0432 14:30",
            "\u0410. \u0412. \u041f\u0430\u0440\u0438\u0431\u043e\u043a (\u0421\u041f\u0431). \u0418\u043d\u0438\u0439\u0441\u043a\u0438\u0435 \u0442\u0435\u043a\u0441\u0442\u044b.",
        ]
        merged = build.coalesce_zograf_talk_lines(lines, 2006)
        self.assertEqual(merged[0], lines[0])

    def test_zograf_source_update_date_is_preserved(self):
        self.assertEqual(build.extract_program_last_updated(2023, "zograf"), "2023-05-22")

    def test_birth_generation_anchors_are_explicit(self):
        self.assertEqual(publication_helpers.generation_cohort(1943)["code"], "1940s")
        self.assertEqual(publication_helpers.generation_cohort(2003)["code"], "2000s")

    def test_verified_biographical_variants_share_a_person_key(self):
        self.assertEqual(
            build.canonical_person_key(
                "\u0422. \u0422. \u0421\u043a\u043e\u0440\u043e\u0445\u043e\u0434\u043e\u0432\u0430"
            ),
            build.canonical_person_key(
                "\u0421\u043a\u043e\u0440\u043e\u0445\u043e\u0434\u043e\u0432\u0430 "
                "\u0422\u0430\u0442\u044c\u044f\u043d\u0430 \u0413\u0440\u0438\u0433\u043e\u0440\u044c\u0435\u0432\u043d\u0430"
            ),
        )

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
