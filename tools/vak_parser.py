"""Parser for the VAK (Higher Attestation Commission) peer-reviewed journal list.

The official list is published as an Excel (.xlsx) file at:
  https://vak.minobrnauki.gov.ru/documents#tab=_tab:ref~

Download the latest .xlsx manually (look for "Перечень рецензируемых научных изданий"),
then run:

  python tools/vak_parser.py path/to/perechen_vak.xlsx

Outputs:
  analytics_output/vak_journals.csv     — all journals with full metadata
  analytics_output/vak_journals_philology.csv — filtered to philology (5.9.x)
  editors/<journal_slug>.md            — one editor profile per top journal

Requirements: pip install openpyxl
"""

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDITORS_DIR = ROOT / "editors"
ANALYTICS_OUT = ROOT / "analytics_output"

# Philology specialty codes (5.9.x according to new VAK nomenclature)
# Also catch old codes (10.01.x) for backward compatibility
PHILOLOGY_CODES = re.compile(
    r"5\.9\.\d+|10\.01\.\d+|10\.02\.\d+"
)

# Journal titles of particular interest for Indology/Oriental studies
INDOLOGY_KEYWORDS = [
    "восток", "oriental", "india", "инди", "азия", "asia",
    "восточн", "письменн", "памятник", "санскрит", "sanskrit",
    "филолог", "philolog", "лингвист", "linguist",
]


def normalize_slug(name: str) -> str:
    """Create a filesystem-safe slug from a journal name."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-zа-яё0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:80]


def parse_vak_xlsx(xlsx_path: str) -> list[dict]:
    """Parse the VAK Excel file and return a list of journal dicts."""
    try:
        from openpyxl import load_workbook
    except ImportError:
        sys.exit("Please install openpyxl: pip install openpyxl")

    wb = load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active

    journals = []
    headers = None

    for row in ws.iter_rows(values_only=True):
        # Skip empty rows
        if not any(row):
            continue

        # Detect header row — typical columns include:
        # №, Название, ISSN, Специальность, Дата включения, etc.
        row_values = [str(c).strip() if c else "" for c in row]

        if headers is None:
            # Heuristic: header row has "Название" or "ISSN" or "№"
            if any("назван" in c.lower() or "issn" in c.lower() or c == "№" for c in row_values):
                headers = row_values
                continue
            # If first meaningful row doesn't look like a header, use column indices
            if len(row_values) >= 3:
                headers = [f"col_{i}" for i in range(len(row_values))]
                # Try to re-label known columns
                for i, v in enumerate(row_values):
                    vl = v.lower()
                    if "issn" in vl:
                        headers[i] = "issn"
                    elif "назван" in vl or "наименован" in vl:
                        headers[i] = "title"
                    elif "специальн" in vl or "научн" in vl:
                        headers[i] = "specialty"
                    elif "дата" in vl:
                        headers[i] = "date_included"
                    elif v == "№":
                        headers[i] = "number"
                # If this IS a header row, skip it
                if any("issn" in c.lower() for c in headers):
                    continue
        else:
            # Build journal dict from headers
            journal = {}
            for i, h in enumerate(headers):
                if i < len(row_values):
                    journal[h] = row_values[i]
                else:
                    journal[h] = ""

            # Try to identify key fields even with generic column names
            title = journal.get("title") or journal.get("название") or journal.get("col_1", "")
            issn = journal.get("issn") or journal.get("col_2", "")
            specialty = journal.get("specialty") or journal.get("специальность") or journal.get("col_3", "")

            # Skip rows without a title
            if not title or len(title) < 3:
                continue

            journals.append({
                "title": title,
                "issn": issn,
                "specialty": specialty,
                "raw": journal,
            })

    wb.close()
    return journals


def is_philology(specialty: str) -> bool:
    """Check if a specialty string contains philology codes."""
    return bool(PHILOLOGY_CODES.search(specialty))


def is_indology_relevant(title: str, specialty: str) -> bool:
    """Check if a journal is of particular relevance to Indology/Oriental studies."""
    combined = f"{title} {specialty}".lower()
    for kw in INDOLOGY_KEYWORDS:
        if kw in combined:
            return True
    return False


def generate_editor_profile(journal: dict) -> str:
    """Generate a Markdown editor profile for a journal."""
    slug = normalize_slug(journal["title"])
    title = journal["title"]
    issn = journal.get("issn", "")
    specialty = journal.get("specialty", "")

    profile = f"""# {title}

- **ISSN:** {issn}
- **Специальности ВАК:** {specialty}
- **Профиль:** [добавить ссылку на сайт журнала]
- **Статус в перечне ВАК:** включён

## Редакционная коллегия

<!-- Заполнить вручную: главный редактор, члены редколлегии, аффилиации -->

## Профиль публикаций

<!-- Типичные темы, языки, объём статей, частота выпусков -->

## Заметки для подачи

<!-- Особые требования, опыт подачи, сроки рецензирования -->

## Контакты

<!-- E-mail редакции, адрес для отправки рукописей -->
"""
    return profile


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    xlsx_path = sys.argv[1]
    if not Path(xlsx_path).exists():
        sys.exit(f"File not found: {xlsx_path}")

    print(f"Parsing {xlsx_path}...")
    journals = parse_vak_xlsx(xlsx_path)

    if not journals:
        print("No journals parsed. Check Excel format — expected columns: "
              "№, Название, ISSN, Специальность, etc.")
        sys.exit(1)

    print(f"Parsed {len(journals)} journals total")

    # Filter to philology
    phil_journals = [j for j in journals if is_philology(j["specialty"])]
    print(f"Philology journals (5.9.x / 10.01.x): {len(phil_journals)}")

    # Identify Indology-relevant journals
    indo_journals = [j for j in phil_journals if is_indology_relevant(j["title"], j["specialty"])]
    print(f"Indology/Oriental-relevant journals: {len(indo_journals)}")
    for j in indo_journals:
        print(f"  - {j['title']} [{j.get('issn', '')}]")

    # Write CSVs
    ANALYTICS_OUT.mkdir(parents=True, exist_ok=True)

    # All journals
    with open(ANALYTICS_OUT / "vak_journals.csv", "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["title", "issn", "specialty"])
        writer.writeheader()
        for j in journals:
            writer.writerow({"title": j["title"], "issn": j["issn"], "specialty": j["specialty"]})

    # Philology only
    with open(ANALYTICS_OUT / "vak_journals_philology.csv", "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["title", "issn", "specialty"])
        writer.writeheader()
        for j in phil_journals:
            writer.writerow({"title": j["title"], "issn": j["issn"], "specialty": j["specialty"]})

    # Generate editor profiles for top philology journals
    EDITORS_DIR.mkdir(parents=True, exist_ok=True)
    profile_count = 0
    for j in phil_journals:
        slug = normalize_slug(j["title"])
        profile_path = EDITORS_DIR / f"{slug}.md"
        profile_text = generate_editor_profile(j)
        profile_path.write_text(profile_text, encoding="utf-8")
        profile_count += 1

    print(f"\nOutputs:")
    print(f"  {ANALYTICS_OUT / 'vak_journals.csv'}")
    print(f"  {ANALYTICS_OUT / 'vak_journals_philology.csv'}")
    print(f"  {EDITORS_DIR}/*.md ({profile_count} profiles)")

    # Show top philology journals
    print(f"\nAll philology journals:")
    for j in phil_journals:
        print(f"  {j['title'][:70]:70s}  ISSN: {j.get('issn', 'N/A')}")


if __name__ == "__main__":
    main()
