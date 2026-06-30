"""Run the INDOLOGY archive harvest, analysis, and validation pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from indology_archive_research.analysis import save_tables, plot_figures
from indology_archive_research.atlas import run_atlas
from indology_archive_research.cleaning import run_cleaning
from indology_archive_research.curation import run_curation
from indology_archive_research.publication import run_publication
from indology_archive_research.public_metadata import run_public_metadata
from indology_archive_research.reply_network import run_reply_network
from indology_archive_research.review_import import import_review_notes, seed_first_review_notes
from indology_archive_research.scrape import harvest_archive
from indology_archive_research.search import run_search
from indology_archive_research.thread_explorer import run_thread_explorer
from indology_archive_research.validate import write_report


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    parser.add_argument("--start-year", type=int, default=1990)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification.")
    parser.add_argument("--delay", type=float, default=0.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--skip-scrape", action="store_true")
    parser.add_argument("--skip-figures", action="store_true")
    parser.add_argument("--skip-cleaning", action="store_true")
    parser.add_argument("--skip-reply-network", action="store_true")
    parser.add_argument("--skip-atlas", action="store_true")
    parser.add_argument("--skip-thread-explorer", action="store_true")
    parser.add_argument("--skip-curation", action="store_true")
    parser.add_argument("--seed-review-notes", action="store_true")
    parser.add_argument("--import-review-notes", action="store_true")
    parser.add_argument("--review-notes-path", type=Path)
    parser.add_argument("--review-import-dry-run", action="store_true")
    parser.add_argument("--review-import-force", action="store_true")
    parser.add_argument("--skip-search", action="store_true")
    parser.add_argument("--skip-public-metadata", action="store_true")
    parser.add_argument("--skip-publication", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    configure_stdio()
    args = build_arg_parser().parse_args(argv)
    if not args.skip_scrape:
        harvest_archive(args.output_dir, args.start_year, args.end_year, args.insecure, args.delay, args.retries)
    tables = save_tables(args.output_dir)
    if not args.skip_figures:
        plot_figures(args.output_dir, tables)
    if not args.skip_cleaning:
        run_cleaning(args.output_dir)
    if not args.skip_reply_network:
        run_reply_network(args.output_dir)
    if not args.skip_atlas:
        run_atlas(args.output_dir)
    if not args.skip_thread_explorer:
        run_thread_explorer(args.output_dir)
    if not args.skip_curation:
        run_curation(args.output_dir)
    if args.seed_review_notes:
        seed_first_review_notes(args.output_dir)
    if args.import_review_notes:
        import_review_notes(
            args.output_dir,
            notes_path=args.review_notes_path,
            dry_run=args.review_import_dry_run,
            force=args.review_import_force,
        )
        if not args.skip_curation:
            run_curation(args.output_dir)
    if not args.skip_search:
        run_search(args.output_dir)
    if not args.skip_publication:
        run_publication(args.output_dir)
    if not args.skip_public_metadata:
        run_public_metadata(args.output_dir)
        if not args.skip_publication:
            run_publication(args.output_dir)
    report_path = write_report(args.output_dir)
    print(f"wrote validation report: {report_path}")


if __name__ == "__main__":
    main()
