import csv
import sqlite3
import sys
from pathlib import Path

# Expose modular pipeline components in the orchestrator for full backward compatibility
from pipeline.schema import (
    SmartHTMLParser,
    extract_csv_from_md,
    extract_program_last_updated,
    init_db,
    populate_seeded_data,
    MD_PATH,
    CACHE_DIR,
)
from pipeline.biography import (
    normalize_person_name,
    load_person_id_overrides,
    load_person_aliases,
    canonical_person_key,
    person_id_for_key,
    get_or_create_person,
    BIOGRAPHICAL_DATA,
    DEGREE_DATA,
    PERSON_ID_MAP_PATH,
    PERSON_ALIAS_PATH,
)
from pipeline.parser import (
    clean_title,
    preprocess_line,
    canonical_id_text,
    stable_hash,
    stable_session_id,
    stable_presentation_id,
    infer_zograf_calendar_date,
    ensure_zograf_event_day_venue,
    split_packed_zograf_lines,
    parse_zograf_talk_line,
    is_zograf_structure_line,
    has_nonparticipant_affiliation,
    coalesce_zograf_talk_lines,
    read_program_text,
    split_coauthor_names,
    populate_zograf_talks,
    populate_roerich_talks,
    TALK_REGEX,
    TALK_REGEX_COAUTHORS,
    TALK_REGEX_TWO_AFFIL,
    TALK_REGEX_INITIALS_AFFIL,
    TALK_REGEX_TWO_AFFIL_INITIALS,
    TALK_REGEX_COAUTHORS_INITIALS,
    TALK_REGEX_COAUTHORS_NO_AFFIL,
    TALK_REGEX_NO_AFFIL,
    TALK_REGEX_ACADEMIC_NO_AFFIL,
    TALK_REGEX_LATIN_COAUTHORS,
    PACKED_AUTHOR_SIGNATURE,
    PACKED_INITIAL_AUTHOR_SIGNATURE,
    LATIN_SPEAKER_ALIASES,
)
from pipeline.verification import (
    verify_db,
    ingest_video_media,
)

DB_PATH = "conferences.db"
PRESENTATION_PERSON_EXCLUSIONS = Path("curation/presentation_person_exclusions.csv")

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass


def apply_presentation_person_exclusions(conn):
    if not PRESENTATION_PERSON_EXCLUSIONS.exists():
        return 0

    accepted_statuses = {"exclude", "excluded", "confirmed", "manual"}
    removed = 0
    with PRESENTATION_PERSON_EXCLUSIONS.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if (row.get("status") or "").strip().lower() not in accepted_statuses:
                continue
            presentation_id = (row.get("presentation_id") or "").strip()
            person_id = (row.get("person_id") or "").strip()
            role = (row.get("role") or "").strip()
            if not presentation_id or not person_id:
                continue

            params = [presentation_id, person_id]
            role_clause = ""
            if role:
                role_clause = " AND role = ?"
                params.append(role)
            cursor = conn.execute(
                f"""
                DELETE FROM presentation_person
                WHERE presentation_id = ? AND person_id = ?{role_clause}
                """,
                params,
            )
            removed += cursor.rowcount

    conn.commit()
    print(f"Applied presentation-person exclusions: {removed} rows removed.")
    return removed


def main():
    print(f"Opening Database connection to {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)

    print("Initializing Database tables...")
    init_db(conn)

    print("Populating seeded database tables from zograf-roerich-db.md...")
    populate_seeded_data(conn)

    print("Populating parsed Zograf Reading talks (2004-2026)...")
    populate_zograf_talks(conn)

    print("Populating parsed Roerich Reading talks (2007-2025)...")
    populate_roerich_talks(conn)

    print("Applying curated presentation-person exclusions...")
    apply_presentation_person_exclusions(conn)

    print("Ingesting YouTube video media from mapping CSV (if present)...")
    ingest_video_media(conn)

    print("Verifying database integrity and statistics...")
    verify_db(conn)

    conn.close()
    print("\nDatabase building and populating pipeline successfully completed!")


if __name__ == "__main__":
    main()
