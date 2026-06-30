"""Generate static search and browse indexes for the INDOLOGY atlas."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, low_memory=False).fillna("") if path.exists() else pd.DataFrame()


def write_json(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def records(frame: pd.DataFrame) -> list[dict[str, object]]:
    return frame.fillna("").to_dict(orient="records")


def build_thread_search(processed_dir: Path) -> pd.DataFrame:
    threads = read_csv(processed_dir / "thread_explorer_index.csv")
    curated = read_csv(processed_dir / "curated_case_studies.csv")
    if threads.empty:
        return pd.DataFrame()
    if not curated.empty:
        curated_columns = [
            col
            for col in ["thread_root_id", "curation_status", "review_track", "suggested_track", "case_type", "short_title", "public_note"]
            if col in curated.columns
        ]
        threads = threads.merge(
            curated[curated_columns],
            on="thread_root_id",
            how="left",
        )
    else:
        threads["curation_status"] = "candidate"
        threads["review_track"] = ""
        threads["suggested_track"] = ""
        threads["case_type"] = ""
        threads["short_title"] = ""
        threads["public_note"] = ""
    threads["curation_status"] = threads["curation_status"].replace("", "candidate")
    if "suggested_track_basis" in curated.columns and "suggested_track_basis" not in threads.columns:
        threads = threads.merge(curated[["thread_root_id", "suggested_track_basis"]], on="thread_root_id", how="left")
    for column in ["review_track", "suggested_track", "suggested_track_basis", "case_type", "short_title", "public_note"]:
        if column not in threads.columns:
            threads[column] = ""
    threads["local_page"] = threads["page_path"]
    return threads[
        [
            "thread_root_id",
            "subject",
            "year",
            "primary_topic",
            "list_function",
            "message_count",
            "author_count",
            "reply_count",
            "case_score",
            "curation_status",
            "review_track",
            "suggested_track",
            "suggested_track_basis",
            "case_type",
            "local_page",
            "first_url",
            "evidence",
            "public_note",
        ]
    ]


def build_author_search(processed_dir: Path) -> pd.DataFrame:
    people = read_csv(processed_dir / "atlas_people_summary.csv")
    if people.empty:
        return pd.DataFrame()
    return people[
        [
            "normalized_author",
            "message_count",
            "thread_count",
            "first_year",
            "last_year",
            "top_topic",
            "top_list_function",
            "resolved_replies_sent",
            "resolved_replies_received",
            "author_status",
        ]
    ]


def build_topic_search(processed_dir: Path) -> pd.DataFrame:
    topics = read_csv(processed_dir / "atlas_topic_profiles.csv")
    if topics.empty:
        return pd.DataFrame()
    return topics[
        [
            "topic",
            "message_count",
            "thread_count",
            "author_count",
            "first_year",
            "last_year",
            "median_thread_length",
            "top_list_function",
        ]
    ]


def build_message_sample(processed_dir: Path, per_year: int = 60, top_recent: int = 2000) -> pd.DataFrame:
    messages = read_csv(processed_dir / "messages_clean.csv")
    if messages.empty:
        return pd.DataFrame()
    messages["thread_length_int"] = pd.to_numeric(messages["thread_length"], errors="coerce").fillna(1)
    messages["year_int"] = pd.to_numeric(messages["year"], errors="coerce")
    candidate = messages[
        (messages["thread_length_int"] >= 5)
        | (messages["list_function"].str.contains("request|help|digital|philological|debate|memorial", case=False, regex=True))
    ].copy()
    sampled = candidate.groupby("year_int", dropna=True).head(per_year)
    recent = messages.sort_values(["year_int", "archive_month", "archive_id"], ascending=False).head(top_recent)
    sample = pd.concat([sampled, recent], ignore_index=True).drop_duplicates("archive_id")
    return sample[
        [
            "archive_id",
            "date",
            "normalized_author",
            "clean_subject",
            "primary_topic",
            "list_function",
            "thread_root_id",
            "archive_url",
        ]
    ].rename(
        columns={
            "normalized_author": "author",
            "clean_subject": "subject",
            "primary_topic": "topic",
        }
    )


def write_search_html(output_dir: Path) -> Path:
    dashboard_dir = output_dir / "dashboard"
    path = dashboard_dir / "search.html"
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Search · INDOLOGY Guided Archive Atlas</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, sans-serif; margin: 0; color: #202124; background: #fafafa; line-height: 1.5; }
    main { max-width: 1180px; margin: 0 auto; padding: 28px 20px 56px; }
    h1 { font-size: 32px; margin-bottom: 8px; }
    h2 { margin-top: 32px; border-top: 1px solid #ddd; padding-top: 20px; }
    label { display: block; font-size: 13px; font-weight: 650; margin-bottom: 4px; }
    input, select { width: 100%; box-sizing: border-box; padding: 8px; border: 1px solid #bbb; border-radius: 6px; background: white; }
    a { color: #245f73; }
    .controls { display: grid; grid-template-columns: 2fr repeat(4, minmax(140px, 1fr)); gap: 12px; margin: 20px 0; align-items: end; }
    .note { color: #555; max-width: 860px; }
    .pill { display: inline-block; padding: 2px 7px; border-radius: 999px; border: 1px solid #ccd; background: #eef3f1; font-size: 12px; }
    button { margin: 0 6px 8px 0; padding: 5px 8px; border: 1px solid #c4cfcc; border-radius: 6px; background: white; color: #245f73; cursor: pointer; }
    button:hover { background: #eef3f1; }
    table.data { width: 100%; border-collapse: collapse; background: white; font-size: 13px; margin: 12px 0 20px; }
    table.data th, table.data td { border: 1px solid #ddd; padding: 6px 8px; vertical-align: top; }
    table.data th { background: #eef3f1; text-align: left; }
    @media (max-width: 850px) { .controls { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
<main>
  <p><a href="index.html">Back to guided atlas</a> · <a href="curated.html">Curated case workflow</a></p>
  <h1>Search And Browse</h1>
  <p class="note">Static metadata search for the INDOLOGY archive atlas. Case-study rows are candidates unless manually curated; person-level fields use conservative normalized author labels.</p>
  <section class="controls">
    <div><label for="q">Search</label><input id="q" type="search" placeholder="Pāṇini, PDF, Unicode, Witzel, Veda..."></div>
    <div><label for="kind">Kind</label><select id="kind"><option value="threads">Threads</option><option value="authors">Authors</option><option value="topics">Topics</option><option value="messages">Message sample</option></select></div>
    <div><label for="topic">Topic</label><select id="topic"><option value="">Any topic</option></select></div>
    <div><label for="func">List function</label><select id="func"><option value="">Any function</option></select></div>
    <div><label for="year">Year</label><select id="year"><option value="">Any year</option></select></div>
  </section>
  <div id="summary" class="note"></div>
  <div id="browse"></div>
  <div id="results"></div>
</main>
<script>
const state = { threads: [], authors: [], topics: [], messages: [] };
const fields = {
  threads: ["subject", "year", "primary_topic", "list_function", "message_count", "author_count", "reply_count", "curation_status", "review_track", "suggested_track", "suggested_track_basis", "case_type", "local_page", "first_url"],
  authors: ["normalized_author", "message_count", "thread_count", "first_year", "last_year", "top_topic", "top_list_function", "author_status"],
  topics: ["topic", "message_count", "thread_count", "author_count", "first_year", "last_year", "top_list_function"],
  messages: ["date", "author", "subject", "topic", "list_function", "archive_url"]
};
function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[ch]));
}
function textOf(row) { return Object.values(row).join(" ").toLowerCase(); }
function match(row, q) { return !q || textOf(row).includes(q); }
function val(row, names) { for (const name of names) if (row[name]) return row[name]; return ""; }
function link(url, label="open") { return url ? `<a href="${escapeHtml(url)}">${escapeHtml(label)}</a>` : ""; }
function countValues(rows, getter) {
  const counts = new Map();
  for (const row of rows) {
    const value = getter(row);
    if (value) counts.set(value, (counts.get(value) || 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 12);
}
function browseButton(label, kind, field, value) {
  return `<button type="button" data-kind="${escapeHtml(kind)}" data-field="${escapeHtml(field)}" data-value="${escapeHtml(value)}">${escapeHtml(label)}</button>`;
}
function renderBrowse() {
  const threadRows = state.threads;
  const authorRows = state.authors;
  const topicRows = countValues([...state.threads, ...state.messages], row => val(row, ["primary_topic", "topic"]));
  const funcRows = countValues([...state.threads, ...state.messages], row => row.list_function || "");
  const yearRows = countValues([...state.threads, ...state.messages], row => row.year || (row.date || "").slice(0,4));
  const authorTop = authorRows.slice(0, 12).map(row => [row.normalized_author, row.message_count]);
  const caseTypes = countValues(threadRows, row => row.case_type || row.curation_status || "candidate");
  const block = (title, rows, kind, field) => `<section><h2>${escapeHtml(title)}</h2><p>${rows.map(([value, count]) => browseButton(`${value} (${count})`, kind, field, value)).join(" ")}</p></section>`;
  document.getElementById("browse").innerHTML = [
    block("Browse By Topic", topicRows, "threads", "topic"),
    block("Browse By Year", yearRows, "threads", "year"),
    block("Browse By List Function", funcRows, "threads", "func"),
    block("Browse By Author", authorTop, "authors", "q"),
    block("Browse By Candidate Type", caseTypes, "threads", "q")
  ].join("");
}
function populateFilters() {
  const topics = new Set(), funcs = new Set(), years = new Set();
  for (const row of [...state.threads, ...state.messages]) {
    const topic = val(row, ["primary_topic", "topic"]);
    const func = row.list_function || "";
    const year = row.year || (row.date || "").slice(0,4);
    if (topic) topics.add(topic);
    if (func) funcs.add(func);
    if (year) years.add(year);
  }
  for (const [id, values] of [["topic", topics], ["func", funcs], ["year", years]]) {
    const el = document.getElementById(id);
    [...values].sort().forEach(value => {
      const opt = document.createElement("option");
      opt.value = value; opt.textContent = value; el.appendChild(opt);
    });
  }
}
function filterRows(kind) {
  const q = document.getElementById("q").value.trim().toLowerCase();
  const topic = document.getElementById("topic").value;
  const func = document.getElementById("func").value;
  const year = document.getElementById("year").value;
  return state[kind].filter(row => {
    const rowTopic = val(row, ["primary_topic", "topic", "top_topic"]);
    const rowFunc = val(row, ["list_function", "top_list_function"]);
    const rowYear = row.year || row.first_year || (row.date || "").slice(0,4);
    return match(row, q) && (!topic || rowTopic === topic) && (!func || rowFunc === func) && (!year || rowYear === year);
  });
}
function renderCell(row, field) {
  if (field === "local_page") return link(row[field], "thread");
  if (field === "first_url" || field === "archive_url") return link(row[field], "archive");
  if (field === "curation_status") return `<span class="pill">${escapeHtml(row[field] || "candidate")}</span>`;
  return escapeHtml(row[field] || "");
}
function render() {
  const kind = document.getElementById("kind").value;
  const rows = filterRows(kind).slice(0, 200);
  document.getElementById("summary").textContent = `${rows.length} shown, ${filterRows(kind).length} matched.`;
  const cols = fields[kind];
  const body = rows.map(row => `<tr>${cols.map(col => `<td>${renderCell(row, col)}</td>`).join("")}</tr>`).join("");
  document.getElementById("results").innerHTML = `<table class="data"><thead><tr>${cols.map(col => `<th>${col}</th>`).join("")}</tr></thead><tbody>${body}</tbody></table>`;
}
document.getElementById("browse").addEventListener("click", event => {
  if (event.target.tagName !== "BUTTON") return;
  const { kind, field, value } = event.target.dataset;
  document.getElementById("kind").value = kind;
  if (field === "topic") document.getElementById("topic").value = value;
  if (field === "func") document.getElementById("func").value = value;
  if (field === "year") document.getElementById("year").value = value;
  if (field === "q") document.getElementById("q").value = value;
  render();
});
async function load() {
  const [threads, authors, topics, messages] = await Promise.all([
    fetch("../data/processed/search_threads.json").then(r => r.json()),
    fetch("../data/processed/search_authors.json").then(r => r.json()),
    fetch("../data/processed/search_topics.json").then(r => r.json()),
    fetch("../data/processed/search_messages_sample.json").then(r => r.json())
  ]);
  Object.assign(state, {threads, authors, topics, messages});
  populateFilters();
  renderBrowse();
  render();
}
for (const id of ["q", "kind", "topic", "func", "year"]) document.addEventListener("input", e => { if (e.target.id === id) render(); });
document.addEventListener("change", render);
load();
</script>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")
    return path


def run_search(output_dir: Path) -> dict[str, object]:
    processed_dir = output_dir / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "dashboard").mkdir(parents=True, exist_ok=True)
    threads = build_thread_search(processed_dir)
    authors = build_author_search(processed_dir)
    topics = build_topic_search(processed_dir)
    messages = build_message_sample(processed_dir)
    write_json(processed_dir / "search_threads.json", records(threads))
    write_json(processed_dir / "search_authors.json", records(authors))
    write_json(processed_dir / "search_topics.json", records(topics))
    write_json(processed_dir / "search_messages_sample.json", records(messages))
    search_page = write_search_html(output_dir)
    return {
        "threads": len(threads),
        "authors": len(authors),
        "topics": len(topics),
        "messages": len(messages),
        "search_page": search_page,
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    return parser


def main(argv: list[str] | None = None) -> None:
    configure_stdio()
    args = build_arg_parser().parse_args(argv)
    print(run_search(args.output_dir))


if __name__ == "__main__":
    main()
