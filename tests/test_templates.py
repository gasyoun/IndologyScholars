import unittest
import jinja2
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class TemplateTests(unittest.TestCase):
    def test_presentation_detail_template_renders(self):
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(ROOT / "templates")))
        template = env.get_template("presentation_detail.html")
        
        talk = {
            "title": "Тестовый доклад",
            "year": 2026,
            "is_online": True,
        }
        
        html = template.render(
            talk=talk,
            videos=[],
            scholar_links_html="Иванов И.И.",
            conference_href="conferences/zograf-2026.html",
            series_label="Зографские чтения",
            depth="../",
            theme_path="themes/linguistics.html",
            theme_label="Лингвистика и филология",
            g_level=1,
            g_meta_ru="Микро",
            pid="PRES_test",
            affiliation="СПбГУ",
            affiliation_note="Из программы",
            review_reason="Проверен экспертом",
            meso_links=[],
            city_html="",
            video_links=[],
            source_url="https://example.org",
            source_updated_text="обновлено вчера",
            title_note="Слегка исправлено"
        )
        
        self.assertIn("Тестовый доклад", html)
        self.assertIn("Иванов И.И.", html)
        self.assertIn("СПбГУ", html)
        self.assertIn("Проверен экспертом", html)
        self.assertIn("Онлайн", html)

    def test_scholar_detail_template_renders(self):
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(ROOT / "templates")))
        template = env.get_template("scholar_detail.html")
        
        scholar = {
            "id": "PERS_test",
            "name": "Иванов Иван Иванович",
            "total_talks": 5,
        }
        
        html = template.render(
            scholar=scholar,
            ru_heading="Иванов Иван Иванович",
            en_heading="Ivanov Ivan Ivanovich",
            format_degree_html="К.и.н.",
            description="Известный исследователь",
            profile_note_html="Профиль",
            total_talks=5,
            archive_records_label="5 записей в архиве",
            activity_span="2020-2026",
            activity_label="годы участия",
            theme_path="themes/history.html",
            profile_label="История",
            series_html="Площадки",
            generation_html="Поколение",
            affiliation_chips="СПбГУ",
            affiliation_notes="Примечания",
            city_chips="Санкт-Петербург",
            status=["исследователь"],
            external_links=["orcid"],
            context_block="Контекст",
            talk_cards=["Карточка доклада"],
            related_html="Связанные авторы"
        )
        
        self.assertIn("Иванов Иван Иванович", html)
        self.assertIn("Ivanov Ivan Ivanovich", html)
        self.assertIn("К.и.н.", html)
        self.assertIn("Известный исследователь", html)
        self.assertIn("5 записей в архиве", html)
        self.assertIn("СПбГУ", html)

if __name__ == "__main__":
    unittest.main()
