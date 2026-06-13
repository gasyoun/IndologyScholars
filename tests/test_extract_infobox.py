"""Regression test for scratch/expand_wikipedia_indologists.extract_infobox.

Real ru.wikipedia infobox rows carry class/style/scope attributes. The earlier
bare `<tr>` pattern matched only attribute-less rows, so it silently dropped
almost every real row. These tests pin that attributed rows are captured.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scratch"))

import expand_wikipedia_indologists as ex  # noqa: E402

INFOBOX = """
<table class="infobox vcard">
  <tr class="infobox-above"><th colspan="2">Иван Иванов</th></tr>
  <tr class="infobox-label-data">
    <th scope="row" class="infobox-label">Род деятельности</th>
    <td class="infobox-data">индолог, переводчик</td>
  </tr>
  <tr style="display:none"><th>Дата рождения</th><td>1920</td></tr>
  <tr><th>Альма-матер</th><td>ЛГУ</td></tr>
</table>
"""


def test_attributed_rows_are_extracted():
    info = ex.extract_infobox(INFOBOX)
    # rows with class / style / scope attributes must be captured, not dropped
    assert info.get("Род деятельности") == "индолог, переводчик"
    assert info.get("Дата рождения") == "1920"
    # a bare-attribute row still works too
    assert info.get("Альма-матер") == "ЛГУ"


def test_no_infobox_returns_empty():
    assert ex.extract_infobox("<p>no table here</p>") == {}
    assert ex.extract_infobox("") == {}
