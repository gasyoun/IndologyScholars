_Created: 22-07-2026 · Last updated: 22-07-2026_

# PLAN — fuller topic/entity breakdown for the nagari retrospective (2026)

**Goal.** Replace the surface-level 8-keyword-tag topic layer of the «Общество ревнителей
санскрита» retrospective ([live page](https://gasyoun.github.io/IndologyScholars/nagari/))
with a multi-layer breakdown: an expanded 2-level curated taxonomy, a domain **entity** layer
(texts / scholars / dictionaries / tools & places), offline-discovered latent topics folded
back into the taxonomy, a key-phrase layer replacing raw word frequency, thread-level topic
assignment, relationship views (co-occurrence, topic→authors, topic×entity), and a citable
dataset — while keeping the live pipeline **stdlib-only** and sending **no body outside the
machine**.

This is the cover/index of a layered plan authored via `/ask`. It carries every ruling and the
autonomy contract; the four layer docs carry the detail.

- **Roadmap** — [ROADMAP_nagari_topics_2026.md](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/docs/ROADMAP_nagari_topics_2026.md)
- **Architecture** — [ARCHITECTURE_nagari_topic_breakdown.md](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/docs/ARCHITECTURE_nagari_topic_breakdown.md)
- **Implementation** — [IMPLEMENTATION_nagari_topic_breakdown.md](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/docs/IMPLEMENTATION_nagari_topic_breakdown.md)
- **Verification** — [VERIFICATION_nagari_topic_breakdown.md](https://github.com/gasyoun/IndologyScholars/blob/main/nagari/docs/VERIFICATION_nagari_topic_breakdown.md)

## Decisions taken (the up-front interview)

| # | Fork | Ruling | Rationale |
|---|---|---|---|
| 1 | Which layers | **All four** — entities (E) + richer curated hierarchy (A) + latent topics (B/C) + key-phrases (G) | Owner wants a genuinely full breakdown, not one axis. |
| 2 | Output home | **Page + citable dataset** | Feeds the data-paper track already queued in `.ai_state.md`. |
| 3 | Granularity | **Thread + message** | Threads = "what was debated"; messages = volume. Both surfaced. |
| 4 | `разное` bucket | **Key measure** — audit + shrink to < 15 % | The catch-all's size is the objective proxy for "fuller". |
| 5 | Dependencies | **Hybrid** — live pipeline stdlib-only; topic-modeling / embeddings / lemmatization live in an offline layer whose *outputs* (static data files) the pipeline consumes | Keeps the project's stdlib + clean-machine-reproducible contract intact. |
| 6 | Body classification | **Local model / embeddings — no external export** (revised from an initial "DeepSeek" pick) | Same "by-body" quality; **no** private correspondence of 605 authors leaves the machine. |
| 7 | Body quotes on the public page | **Allowed, but human-gated** — built OFF by default; enabled only after `/publish-safety-check` + owner GO; **not** in the unattended run | Exposes 604 third parties' words from a closed list — a rights call, not an automatable one. |
| 8 | RU lemmatization | **Precompute a static form→lemma dict offline**; the stdlib pipeline reads it | Real lemmatization quality without deps in the critical path. |
| 9 | Taxonomy authority *(default, non-blocking)* | **Hybrid** — hand-expand the curated hierarchy; offline clustering finds gaps (esp. inside `разное`) that fold back in | Interpretable + stable, without missing latent themes. |
| 10 | Entity types *(default)* | **All four** — texts/corpora, scholars/authors, dictionaries/reference, tools+fonts+software+places/institutions | Reuse org name-lists; add the RU/IAST alias layer. |
| 11 | Phrase method *(default)* | **PMI / log-likelihood collocations + TF-IDF over subjects+bodies** (offline; aggregate phrases to page) | Surfaces multi-word themes the single-word list misses. |
| 12 | Relationship views *(default)* | topic co-occurrence, topic→authors, topic→representative subjects, topic×entity matrix (all count-/subject-level) | Aggregate-only → safe for the public page, so they stay in the unattended run. |

Defaults #9–#12 were applied (not interviewed to exhaustion, per the owner's "go") with the
marked recommendation and are logged here; any of them can be overridden before execution
without touching rulings #1–#8.

## Autonomy contract (governs the unattended build)

- **On ambiguity** — apply the marked default in this plan and log the choice to
  `nagari/.ai_state.md` Dev Notes. **Do not stall**; do not improvise beyond the plan's scope.
- **Stop conditions** — halt and report if: (a) `validate_publication.py` or `pytest` go red
  and are not fixable within scope; (b) any change would send a body/subject to an external
  API; (c) the misc bucket stays > 40 % after taxonomy expansion (taxonomy needs a human
  rethink); (d) the offline embedding model cannot be fetched **and** the misc-audit seed is
  also insufficient to build a ≥ 30-topic taxonomy.
- **Commit authority** — the wave-1 handoff authorizes commit → PR → merge (auto-merge +
  delete branch) for **all** layers **except** the two fenced items below.
- **The fence — the agent must NOT:** enable the quote surface (`SHOW_QUOTES` stays false);
  deploy/publish anywhere (Pages/samskrtam.ru) — that is a human `@DECIDE`; send any body or
  subject to an external API; extract attachment blobs (open rights `@DECIDE`); touch the raw
  dump or the ingest/redaction privacy layer; merge author identities; hand-edit any derived
  artifact (edit generators + rebuild).

## Autonomy-readiness gate — **PASS**

Every wave-1 deliverable has an architecture spec, ordered implementation steps, an acceptance
criterion, and a named risk. Zero blocking forks remain (rulings #1–#8 fixed; #9–#12 given
logged defaults). No rebuild-what-exists (prior-art verdicts recorded in ARCHITECTURE). The
autonomy contract covers the surfaced ambiguities. The two rights/privacy-laden actions are
fenced out of the unattended run into Wave 2.

## Execution

Handoff **H1518** ([Uprava/handoffs](https://github.com/gasyoun/Uprava/blob/main/handoffs/H1518-Sonnet_IndologyScholars_nagari-topic-breakdown_22.07.26.md)).
Start it in a fresh session with:

```
Read C:\Users\user\Documents\GitHub\IndologyScholars\nagari\docs\PLAN_nagari_topic_breakdown_2026.md and execute it.
```

Intended executor: **Sonnet 5** (`claude-sonnet-5`).

_Dr. Mārcis Gasūns_
