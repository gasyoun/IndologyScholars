"""Build the Renou-classifier precision gold sample as an interactive HTML review sheet.

The Renou state/register layer matches presentation titles and INDOLOGY-L subject
lines with regular expressions. Several register patterns key on generic words
(`commentary` -> bhasya, `story|narrative|сюжет` -> katha, `poetry|verse` -> kavya,
`drama|theatre` -> natya), so match counts alone cannot support any claim about
scholarly attention until precision is measured per register.

This script draws a seeded, risk-stratified sample across both layers and emits a
self-contained voting sheet. Votes export to a decisions JSON consumed by
`score_renou_precision.py`.

Prior art. The org already has a Renou review sheet — `build_renou_pilot_sheet.py`
in SanskritLexicography/RussianTranslation — but it samples *lexicon headwords* by
DCS/BHS attestation (strata A-E), a different unit and a different question. Its
`{sheet_id, generated, decided, items:[{id, decision, note}]}` export contract is
reused here verbatim so one scorer can read either sheet. The Renou scheme itself
is defined in that repo's RENOU.md, which both IndologyScholars layers already cite
as `source_url`; the rule tables are currently duplicated (see H452).

Usage:
    python tools/build_renou_precision_sheet.py
"""

from __future__ import annotations

import csv
import html
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

SEED = 20260710
TARGET_CONFERENCE = 90
TARGET_ARCHIVE = 60

SHEET_ID = "indologyscholars-renou-precision_gold150"
SHEET_NAME = f"{SHEET_ID}_review.html"
DECISIONS_NAME = f"{SHEET_ID}_decisions.json"

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFERENCE_MATCHES = REPO_ROOT / "analytics_output" / "renou_presentation_matches.csv"
ARCHIVE_MATCHES = REPO_ROOT / "Indology" / "data" / "processed" / "renou_message_matches.csv"
OUTPUT_DIR = REPO_ROOT / "review"

SITE_BASE = "https://gasyoun.github.io/IndologyScholars/"

# Risk tier drives the sampling quota. HIGH strata are those whose regex keys on
# generic English/Russian vocabulary rather than on a Sanskrit title or proper name.
HIGH_RISK = {
    ("register", "bhasya"),   # commentary|commentator|коммент
    ("register", "katha"),    # story|stories|narrative|tale|сюжет|рассказ
    ("register", "kavya"),    # poetry|poetic|poem|verse|поэз|стих
    ("register", "natya"),    # drama|dramatic|theatre|theater|play|драм|театр
    ("state", "IV"),          # inherits kavya/natya/katha vocabulary
}
MED_RISK = {
    ("register", "epic"), ("register", "tantra"), ("register", "purana"),
    ("register", "sutra"), ("register", "vyakarana"), ("register", "smrti"),
    ("state", "II"), ("state", "III"),
}

QUOTA_CONFERENCE = {"high": 10, "med": 4, "low": 2}
QUOTA_ARCHIVE = {"high": 6, "med": 3, "low": 1}


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def risk_tier(axis: str, code: str) -> str:
    if (axis, code) in HIGH_RISK:
        return "high"
    if (axis, code) in MED_RISK:
        return "med"
    return "low"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def stratified_sample(
    rows: list[dict[str, str]],
    quota: dict[str, int],
    target: int,
    rng: random.Random,
) -> list[dict[str, str]]:
    """Draw `quota[tier]` rows per (axis, code) stratum, then trim/top-up to `target`."""
    strata: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        strata[(row["renou_axis"], row["renou_code"])].append(row)

    picked: list[dict[str, str]] = []
    leftovers: list[dict[str, str]] = []
    for key in sorted(strata):
        bucket = sorted(strata[key], key=stable_key)
        rng.shuffle(bucket)
        want = min(quota[risk_tier(*key)], len(bucket))
        picked.extend(bucket[:want])
        leftovers.extend(bucket[want:])

    if len(picked) > target:
        # Trim from the low-risk end first so the high-risk strata stay intact.
        picked.sort(key=lambda r: ({"high": 0, "med": 1, "low": 2}[risk_tier(r["renou_axis"], r["renou_code"])],))
        picked = picked[:target]
    elif len(picked) < target and leftovers:
        rng.shuffle(leftovers)
        picked.extend(leftovers[: target - len(picked)])

    picked.sort(key=stable_key)
    return picked


def stable_key(row: dict[str, str]) -> str:
    return f"{row.get('presentation_id') or row.get('archive_id')}|{row['rule_id']}"


def conference_item(row: dict[str, str]) -> dict[str, object]:
    public_path = (row.get("public_path") or "").strip()
    links = []
    if public_path:
        links.append({"label": "presentation page", "url": SITE_BASE + public_path})
    if row.get("source_url"):
        links.append({"label": "programme source", "url": row["source_url"]})
    title = row.get("title", "")
    term = row.get("matched_term", "")
    in_title = bool(term) and term.lower() in title.lower()
    return {
        "id": f"CONF:{row['presentation_id']}:{row['rule_id']}",
        "layer": "conference",
        "evidence": "matched in the title" if in_title else "matched a subject tag, not the title text",
        "axis": row["renou_axis"],
        "code": row["renou_code"],
        "label": row["renou_label"],
        "stratum": f"{row['renou_axis']}:{row['renou_code']}",
        "risk": risk_tier(row["renou_axis"], row["renou_code"]),
        "matched_term": row.get("matched_term", ""),
        "title": row.get("title", ""),
        "meta": f"{row.get('series','')} · {row.get('year','')}",
        "covers": "",
        "links": links,
        "default": None,
    }


def archive_item(row: dict[str, str]) -> dict[str, object]:
    links = []
    if row.get("archive_url"):
        links.append({"label": "list message", "url": row["archive_url"]})
    subject = row.get("clean_subject", "")
    term = row.get("matched_term", "")
    in_subject = bool(term) and term.lower() in subject.lower()
    return {
        "id": f"ARCH:{row['archive_id']}:{row['rule_id']}",
        "layer": "archive",
        "evidence": "matched in the subject line" if in_subject else "matched outside the subject text",
        "axis": row["renou_axis"],
        "code": row["renou_code"],
        "label": row["renou_label"],
        "stratum": f"{row['renou_axis']}:{row['renou_code']}",
        "risk": risk_tier(row["renou_axis"], row["renou_code"]),
        "matched_term": row.get("matched_term", ""),
        "title": row.get("clean_subject", ""),
        "meta": " · ".join(x for x in [row.get("normalized_author", ""), str(row.get("year", "")), row.get("primary_topic", "")] if x),
        "covers": row.get("renou_covers", ""),
        "links": links,
        "default": None,
    }


def build_items() -> list[dict[str, object]]:
    rng = random.Random(SEED)
    conf_rows = stratified_sample(read_rows(CONFERENCE_MATCHES), QUOTA_CONFERENCE, TARGET_CONFERENCE, rng)
    arch_rows = stratified_sample(read_rows(ARCHIVE_MATCHES), QUOTA_ARCHIVE, TARGET_ARCHIVE, rng)
    return [conference_item(r) for r in conf_rows] + [archive_item(r) for r in arch_rows]


def highlight(text: str, term: str) -> str:
    """Escape, then wrap the literal matched term so the reviewer sees why it fired."""
    escaped = html.escape(text or "")
    needle = html.escape(term or "")
    if not needle:
        return escaped
    lowered, low_needle = escaped.lower(), needle.lower()
    start = lowered.find(low_needle)
    if start < 0:
        return escaped
    end = start + len(needle)
    return f"{escaped[:start]}<mark>{escaped[start:end]}</mark>{escaped[end:]}"


def render_item(index: int, item: dict[str, object]) -> str:
    links = "".join(
        f'<a href="{html.escape(l["url"])}" target="_blank" rel="noopener">{html.escape(l["label"])}</a>'
        for l in item["links"]
    )
    covers = f'<div class="covers">Renou covers: {html.escape(item["covers"])}</div>' if item["covers"] else ""
    return f"""
<article class="item" data-id="{html.escape(item['id'])}" data-risk="{item['risk']}" data-layer="{item['layer']}" data-stratum="{html.escape(item['stratum'])}">
  <div class="head">
    <span class="num">{index}</span>
    <span class="badge badge-{item['layer']}">{item['layer']}</span>
    <span class="badge badge-{item['risk']}">{item['risk']} risk</span>
    <span class="assign">{html.escape(item['axis'])} <strong>{html.escape(item['code'])}</strong> — {html.escape(item['label'])}</span>
  </div>
  <p class="title">{highlight(str(item['title']), str(item['matched_term']))}</p>
  <div class="meta">{html.escape(str(item['meta']))}</div>
  <div class="term">fired on <code>{html.escape(str(item['matched_term']))}</code> — {html.escape(str(item['evidence']))}</div>
  {covers}
  <div class="links">{links}</div>
  <div class="vote">
    <button class="btn approve" data-v="correct">✅ correct <kbd>a</kbd></button>
    <button class="btn reject"  data-v="incorrect">❌ incorrect <kbd>r</kbd></button>
    <button class="btn defer"   data-v="unsure">⏸ unsure <kbd>d</kbd></button>
    <input class="note" type="text" placeholder="note (optional) — e.g. correct register but wrong état" />
  </div>
</article>"""


CSS = """
:root{--bg:#fbfaf7;--fg:#1f1d1a;--mut:#6b6560;--line:#e2ddd5;--card:#fff;
--ok:#1a7f4b;--no:#b02a2a;--df:#8a6d1f;--hi:#fce8c8;}
@media(prefers-color-scheme:dark){:root{--bg:#161513;--fg:#ece8e1;--mut:#9a938b;--line:#332f2b;--card:#1f1d1a;--hi:#4a3a1c;}}
*{box-sizing:border-box}
body{margin:0;font:16px/1.55 -apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--fg);}
header{position:sticky;top:0;z-index:9;background:var(--card);border-bottom:1px solid var(--line);padding:14px 20px;}
h1{margin:0 0 4px;font-size:19px;}
.sub{color:var(--mut);font-size:13px;}
.tally{display:flex;gap:14px;margin-top:8px;font-size:13px;flex-wrap:wrap;align-items:center}
.tally b{font-variant-numeric:tabular-nums}
.bar{height:5px;background:var(--line);border-radius:3px;overflow:hidden;flex:1;min-width:120px}
.bar>i{display:block;height:100%;background:var(--ok);width:0}
main{max-width:900px;margin:0 auto;padding:20px;}
.item{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin-bottom:14px;}
.item.voted{opacity:.5}
.head{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:6px}
.num{color:var(--mut);font-size:12px;font-variant-numeric:tabular-nums;min-width:28px}
.badge{font-size:11px;text-transform:uppercase;letter-spacing:.04em;padding:2px 7px;border-radius:20px;border:1px solid var(--line);color:var(--mut)}
.badge-high{background:#fdecec;color:#b02a2a;border-color:#f3c9c9}
.badge-med{background:#fdf6e3;color:#8a6d1f;border-color:#eedeb8}
@media(prefers-color-scheme:dark){.badge-high{background:#3a1f1f;border-color:#5a2e2e}.badge-med{background:#3a301a;border-color:#5a4a2a}}
.assign{margin-left:auto;font-size:13px;color:var(--mut)}
.title{margin:4px 0;font-size:17px;font-weight:500}
mark{background:var(--hi);color:inherit;padding:0 2px;border-radius:2px}
.meta,.covers{color:var(--mut);font-size:13px}
.term{font-size:12px;color:var(--mut);margin-top:4px}
code{background:var(--bg);padding:1px 5px;border-radius:4px;border:1px solid var(--line)}
.links{margin:8px 0 4px;display:flex;gap:12px;flex-wrap:wrap}
.links a{color:#2f6fb0;font-size:13px}
.vote{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;align-items:center}
.btn{cursor:pointer;border:1px solid var(--line);background:var(--bg);color:var(--fg);border-radius:7px;padding:6px 11px;font-size:14px}
.btn:hover{border-color:var(--mut)}
.btn.on.approve{background:var(--ok);color:#fff;border-color:var(--ok)}
.btn.on.reject{background:var(--no);color:#fff;border-color:var(--no)}
.btn.on.defer{background:var(--df);color:#fff;border-color:var(--df)}
kbd{font-size:10px;opacity:.55;border:1px solid currentColor;border-radius:3px;padding:0 3px;margin-left:4px}
.note{flex:1;min-width:180px;padding:6px 9px;border:1px solid var(--line);border-radius:7px;background:var(--bg);color:var(--fg)}
.item.cur{outline:2px solid #2f6fb0;outline-offset:2px}
.dl{cursor:pointer;background:var(--fg);color:var(--bg);border:0;border-radius:7px;padding:7px 13px;font-size:13px;font-weight:600}
.filters{margin-top:8px;font-size:13px;color:var(--mut)}
.filters button{cursor:pointer;background:none;border:1px solid var(--line);border-radius:20px;padding:3px 10px;margin-right:5px;color:var(--mut);font-size:12px}
.filters button.on{background:var(--fg);color:var(--bg);border-color:var(--fg)}
"""

JS = """
const SHEET_ID = "__SHEET_ID__", DECISIONS_NAME = "__DECISIONS_NAME__", GENERATED = "__GENERATED__";
const KEY = "renou-precision:" + SHEET_ID;
const state = JSON.parse(localStorage.getItem(KEY) || "{}");
const items = [...document.querySelectorAll(".item")];
let cur = 0;

function save(){ localStorage.setItem(KEY, JSON.stringify(state)); }

function paint(el){
  const id = el.dataset.id, s = state[id] || {};
  el.querySelectorAll(".btn").forEach(b => b.classList.toggle("on", b.dataset.v === s.decision));
  el.classList.toggle("voted", !!s.decision);
  const n = el.querySelector(".note");
  if (document.activeElement !== n) n.value = s.note || "";
}

function tally(){
  const v = {correct:0, incorrect:0, unsure:0};
  Object.values(state).forEach(s => { if (s.decision) v[s.decision]++; });
  const done = v.correct + v.incorrect + v.unsure, total = items.length;
  document.getElementById("t-ok").textContent = v.correct;
  document.getElementById("t-no").textContent = v.incorrect;
  document.getElementById("t-df").textContent = v.unsure;
  document.getElementById("t-left").textContent = total - done;
  document.getElementById("t-bar").style.width = (100 * done / total) + "%";
  const judged = v.correct + v.incorrect;
  document.getElementById("t-prec").textContent = judged ? (100 * v.correct / judged).toFixed(1) + "%" : "—";
}

function vote(el, decision){
  const id = el.dataset.id;
  const s = state[id] || {};
  s.decision = (s.decision === decision) ? null : decision;
  state[id] = s; save(); paint(el); tally();
}

items.forEach((el, i) => {
  paint(el);
  el.querySelectorAll(".btn").forEach(b => b.onclick = () => { cur = i; focus(); vote(el, b.dataset.v); });
  el.querySelector(".note").oninput = e => {
    const s = state[el.dataset.id] || {}; s.note = e.target.value; state[el.dataset.id] = s; save();
  };
});

function focus(){ items.forEach(e => e.classList.remove("cur")); const e = items[cur]; if(!e) return;
  e.classList.add("cur"); e.scrollIntoView({block:"center", behavior:"smooth"}); }

document.addEventListener("keydown", e => {
  if (e.target.tagName === "INPUT") return;
  const map = {a:"correct", r:"incorrect", d:"unsure"};
  if (map[e.key]) { vote(items[cur], map[e.key]); if (cur < items.length - 1) { cur++; focus(); } e.preventDefault(); }
  if (e.key === "ArrowDown" || e.key === "j") { cur = Math.min(cur + 1, items.length - 1); focus(); e.preventDefault(); }
  if (e.key === "ArrowUp"   || e.key === "k") { cur = Math.max(cur - 1, 0); focus(); e.preventDefault(); }
});

document.querySelectorAll(".filters button").forEach(b => b.onclick = () => {
  document.querySelectorAll(".filters button").forEach(x => x.classList.remove("on"));
  b.classList.add("on");
  const f = b.dataset.f;
  items.forEach(el => {
    const show = f === "all" || el.dataset.risk === f || el.dataset.layer === f
              || (f === "todo" && !(state[el.dataset.id] || {}).decision);
    el.style.display = show ? "" : "none";
  });
});

document.getElementById("dl").onclick = () => {
  const payload = {
    sheet_id: SHEET_ID,
    generated: GENERATED,
    decided: new Date().toISOString(),
    items: items.map(el => {
      const s = state[el.dataset.id] || {};
      return { id: el.dataset.id, layer: el.dataset.layer, stratum: el.dataset.stratum,
               risk: el.dataset.risk, decision: s.decision || null, note: s.note || "" };
    })
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], {type:"application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.setAttribute("download", DECISIONS_NAME);
  a.click(); URL.revokeObjectURL(a.href);
};

tally(); focus();
"""


def render_sheet(items: list[dict[str, object]], generated: str) -> str:
    body = "\n".join(render_item(i + 1, it) for i, it in enumerate(items))
    n_conf = sum(1 for i in items if i["layer"] == "conference")
    n_arch = len(items) - n_conf
    n_high = sum(1 for i in items if i["risk"] == "high")
    js = JS.replace("__SHEET_ID__", SHEET_ID).replace("__DECISIONS_NAME__", DECISIONS_NAME).replace("__GENERATED__", generated)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Renou classifier precision — gold sample</title>
<style>{CSS}</style></head><body>
<header>
  <h1>Renou classifier — precision gold sample</h1>
  <div class="sub">{len(items)} stratified matches · {n_conf} conference presentations · {n_arch} INDOLOGY-L messages · {n_high} high-risk · generated {generated}</div>
  <div class="sub">For each item: did the Renou <strong>état/register</strong> assignment correctly describe what the item is <em>about</em>? Judge the assignment, not the title.</div>
  <div class="tally">
    <span>✅ <b id="t-ok">0</b></span><span>❌ <b id="t-no">0</b></span><span>⏸ <b id="t-df">0</b></span>
    <span>left <b id="t-left">0</b></span><span>running precision <b id="t-prec">—</b></span>
    <span class="bar"><i id="t-bar"></i></span>
    <button class="dl" id="dl">Download {DECISIONS_NAME}</button>
  </div>
  <div class="filters">
    <button data-f="all" class="on">all</button><button data-f="todo">unvoted</button>
    <button data-f="high">high risk</button><button data-f="med">med risk</button>
    <button data-f="conference">conference</button><button data-f="archive">archive</button>
  </div>
</header>
<main>{body}</main>
<script>{js}</script>
</body></html>"""


def main() -> None:
    configure_stdio()
    generated = "2026-07-10"
    items = build_items()
    OUTPUT_DIR.mkdir(exist_ok=True)
    sheet_path = OUTPUT_DIR / SHEET_NAME
    sheet_path.write_text(render_sheet(items, generated), encoding="utf-8")

    manifest = OUTPUT_DIR / f"{SHEET_ID}_items.json"
    manifest.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    by_risk: dict[str, int] = defaultdict(int)
    by_stratum: dict[str, int] = defaultdict(int)
    for item in items:
        by_risk[str(item["risk"])] += 1
        by_stratum[str(item["stratum"])] += 1

    print(f"sheet    : {sheet_path}")
    print(f"manifest : {manifest}")
    print(f"items    : {len(items)}  (seed {SEED}, deterministic)")
    print("by risk  : " + ", ".join(f"{k}={v}" for k, v in sorted(by_risk.items())))
    print("strata   : " + str(len(by_stratum)))
    for stratum, count in sorted(by_stratum.items(), key=lambda kv: -kv[1]):
        print(f"   {stratum:<20} {count}")


if __name__ == "__main__":
    main()
