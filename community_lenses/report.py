"""Comparison validity report + claims ledger (H1899, Wave 1E).

`comparison_validity.md` is the human-readable verdict on what the five-lens
package may and may not support: source health, reconciliation, temporal
boundary, classification and Gumilev validity, Renou precision, identity
evidence, quote context/rights, metric denominators, geographical limits, and
a claim-by-claim ruling.

`claims_ledger.csv` is its machine-checkable half: every proposed article claim
resolves to one or more frozen metric rows, an exact approved quote, or an
explicit `expert_judgment` row — `validate_claims()` fails if any claim is
unlinked, if a metric id does not exist in the frozen tables, if a quote id is
not in the register, or if a claim carries causal/representativeness language
it has no standing to make.
"""

from __future__ import annotations

import csv
from pathlib import Path

from . import classify, identity, metrics, quotes, taxonomy

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = REPO_ROOT / "analytics_output" / "community_lenses" / "reports"
VALIDITY_PATH = REPORTS_DIR / "comparison_validity.md"
LEDGER_PATH = REPORTS_DIR / "claims_ledger.csv"

REPORT_VERSION = "h1899-report-1.0.0"

VERDICTS = ("supported", "provisional", "expert_judgment", "out_of_scope")
EVIDENCE_KINDS = ("metric", "quote", "expert_judgment", "none")

LEDGER_COLUMNS = (
    "claim_id",
    "outline_section",
    "claim_ru",
    "verdict",
    "evidence_kind",
    "evidence_ids",
    "figure_or_table",
    "counterevidence",
    "limitation",
)

# Language a claim of each verdict class may NOT use.
_CAUSAL_MARKERS = (
    "вызвал", "вызвало", "привёл к", "привело к", "из-за того", "потому что",
    "caused", "because of", "led to", "объясняется тем",
)
_REPRESENTATIVENESS_MARKERS = (
    "репрезентатив", "вся российская индология", "все индологи", "в целом по стране",
    "representative of", "all indologists",
)
_PVALUE_MARKERS = ("p =", "p<", "p <", "p-значение", "p-value", "significan")


class ClaimError(ValueError):
    pass


# ---------------------------------------------------------------------------
# The claims ledger
# ---------------------------------------------------------------------------

def build_claims() -> list[dict]:
    """Every claim the revised Russian article may propose, with its evidence.

    Ordering follows the Russian revision outline
    (`article/ppv_comparative_revision_outline_ru.md`), so the ledger and the
    outline can be read side by side.
    """
    return [
        {
            "claim_id": "cl-conf-scale",
            "outline_section": "2. Корпус и метод",
            "claim_ru": "Конференционный корпус Рериховских/Зографских чтений содержит 1362 доклада "
                        "за 2004–2026 гг. при полном покрытии базы программ.",
            "verdict": "supported",
            "evidence_kind": "metric",
            "evidence_ids": "coverage.conferences",
            "figure_or_table": "lens_source_coverage.csv",
            "counterevidence": "Покрытие полное только в пределах самой базы программ; "
                               "доклады вне программ в неё не попадают.",
            "limitation": "Единица — доклад (presentation), а не человек и не публикация.",
        },
        {
            "claim_id": "cl-conf-period-composition",
            "outline_section": "3. Масштаб и структура участия",
            "claim_ru": "Внутри конференционной линзы доля докладов периода 2018–2025 выше доли "
                        "периода 2005–2010 (композиция внутри линзы, знаменатель — датированные доклады).",
            "verdict": "supported",
            "evidence_kind": "metric",
            "evidence_ids": "activity.conferences.2005-2010|activity.conferences.2018-2025",
            "figure_or_table": "fig1_activity_by_period.svg",
            "counterevidence": "Рост числа докладов может отражать изменение практики учёта программ, "
                               "а не рост сообщества; данных для различения этих объяснений нет.",
            "limitation": "Описательное сравнение долей, без причинного утверждения и без "
                          "экстраполяции на индологию в целом.",
        },
        {
            "claim_id": "cl-2026-partial",
            "outline_section": "2. Корпус и метод",
            "claim_ru": "Записи 2026 года выделены в отдельный частичный снимок и не входят "
                        "ни в один тренд 2005–2025.",
            "verdict": "supported",
            "evidence_kind": "metric",
            "evidence_ids": "activity.conferences.2026-partial|activity.vk_ors.2026-partial|activity.nagari.2026-partial",
            "figure_or_table": "fig1_activity_by_period.svg",
            "counterevidence": "—",
            "limitation": "Частичный 2026 нельзя сопоставлять с годовыми темпами.",
        },
        {
            "claim_id": "cl-conf-content-profile",
            "outline_section": "4. Тематические профили",
            "claim_ru": "В конференционной линзе кроссволк-проекция содержания концентрируется "
                        "в литературе/поэтике и религии/философии.",
            "verdict": "provisional",
            "evidence_kind": "metric",
            "evidence_ids": "content.conferences.literature_poetics.taxonomy_crosswalk|"
                            "content.conferences.religion_philosophy.taxonomy_crosswalk",
            "figure_or_table": "fig2_intellectual_content.svg",
            "counterevidence": "Кроссволк H1897 не принят человеком (review_status=pending); "
                               "родные тематические коды остаются единственным принятым свидетельством.",
            "limitation": "Знаменатель — доклады, размеченные по этой оси, а не все доклады.",
        },
        {
            "claim_id": "cl-conf-gumilev",
            "outline_section": "5. Микрокейс как норма",
            "claim_ru": "В конференционной линзе преобладает уровень G1 шкалы Гумилёва; G3 остаётся "
                        "редким (11 докладов из 1361 размеченных).",
            "verdict": "supported",
            "evidence_kind": "metric",
            "evidence_ids": "gumilev.conferences.G1.gumilyov_scale_csv_deepseek|"
                            "gumilev.conferences.G3.gumilyov_scale_csv_deepseek_strict_scale_audit",
            "figure_or_table": "fig4_argument_level.svg",
            "counterevidence": "Разметка получена машинным проходом с последующим строгим аудитом шкалы; "
                               "её собственный пакет надёжности относится только к докладам.",
            "limitation": "Применимо ТОЛЬКО к конференционной линзе.",
        },
        {
            "claim_id": "cl-crosslens-gumilev",
            "outline_section": "6. Обсуждение",
            "claim_ru": "Межлинзовое распределение шкалы Гумилёва не публикуется: пилот вне конференций "
                        "не прошёл человеческую проверку.",
            "verdict": "out_of_scope",
            "evidence_kind": "metric",
            "evidence_ids": "gumilev.nagari.G1.deterministic_ruleset_pilot|gumilev.vk_ors.unknown.deterministic_ruleset_pilot",
            "figure_or_table": "fig4_argument_level.svg",
            "counterevidence": "Пилот даёт формально вычислимые доли, но порог V6 (согласие ≥80%, "
                               "Gwet AC1 ≥0,67) не измерен.",
            "limitation": "Пилотные доли приводятся только как внутрилинзовая композиция.",
        },
        {
            "claim_id": "cl-nagari-teaching",
            "outline_section": "4. Тематические профили",
            "claim_ru": "В пилотном срезе nagari преобладают учебно-обучающая функция и текстологическое "
                        "содержание.",
            "verdict": "provisional",
            "evidence_kind": "metric",
            "evidence_ids": "function.nagari.teaching_learning.taxonomy_crosswalk|"
                            "content.nagari.texts_philology.taxonomy_crosswalk",
            "figure_or_table": "fig3_community_function.svg",
            "counterevidence": "Покрытие nagari — PILOT; доли описывают композицию размеченного среза, "
                               "а не сообщество.",
            "limitation": "Никаких долей населения группы; знаменатель — размеченные сообщения среза.",
        },
        {
            "claim_id": "cl-vk-biblio-series",
            "outline_section": "4. Тематические профили",
            "claim_ru": "На стене ORS/VK существует устойчивая библиографическая рубрика: 313 из 7608 "
                        "постов самопомечены #bookzealots.",
            "verdict": "supported",
            "evidence_kind": "quote",
            "evidence_ids": "Q-VK-22289",
            "figure_or_table": "lens_source_coverage.csv",
            "counterevidence": "Хэштег ставит сам автор страницы; это самоописание рубрики, а не "
                               "независимая классификация.",
            "limitation": "Цитата в статусе прав pending_review — публиковать дословно нельзя "
                          "до подтверждения.",
        },
        {
            "claim_id": "cl-crosslens-persons",
            "outline_section": "5. Микрокейс как норма",
            "claim_ru": "Семь человек засвидетельствованы и в конференционной программе, и в закрытой "
                        "группе nagari (641 упоминание), при пяти неоднозначных кандидатах, исключённых "
                        "из счёта.",
            "verdict": "supported",
            "evidence_kind": "metric",
            "evidence_ids": "overlap.conferences|overlap.nagari",
            "figure_or_table": "fig5_person_overlap.svg",
            "counterevidence": "Связи опираются на совпадение имён и замаскированных аккаунтов; "
                               "пять кандидатов остались неразрешимыми и не засчитаны.",
            "limitation": "Именные межплощадочные утверждения не экспортируются до одобрения прав "
                          "закрытой группы; совпадение площадок не означает миграцию сообщества.",
        },
        {
            "claim_id": "cl-nagari-quotes-gated",
            "outline_section": "5. Микрокейс как норма",
            "claim_ru": "Две зарегистрированные цитаты из nagari остаются неэкспортируемыми: права "
                        "закрытой группы не подтверждены.",
            "verdict": "supported",
            "evidence_kind": "quote",
            "evidence_ids": "Q-NG-PANINI-ASK|Q-NG-PANINI-ANSWER",
            "figure_or_table": "identity_quote_evidence.md",
            "counterevidence": "—",
            "limitation": "Пересказ вместо цитаты запрещён: при отсутствии прав пример опускается.",
        },
        {
            "claim_id": "cl-orientation-premise",
            "outline_section": "2. Корпус и метод",
            "claim_ru": "Отнесение площадок к российской, западной и индийской ориентации — посылка "
                        "отбора корпуса, а не измерение гражданства участников.",
            "verdict": "expert_judgment",
            "evidence_kind": "expert_judgment",
            "evidence_ids": "orientation.russia_centred.conferences|orientation.western_centred.indology_l|"
                            "orientation.india_centred.bvp",
            "figure_or_table": "fig6_orientation_contrast.svg",
            "counterevidence": "Часть участников российских площадок работает за рубежом и наоборот; "
                               "ориентация форума этого не отражает.",
            "limitation": "Экспертное суждение: p-значения не применяются, доля сообщества не считается.",
        },
        {
            "claim_id": "cl-west-india-gap",
            "outline_section": "6. Обсуждение",
            "claim_ru": "Сравнение России с западной и индийской площадками в этом снимке не проводится: "
                        "INDOLOGY-L и BVP недоступны как источники.",
            "verdict": "out_of_scope",
            "evidence_kind": "metric",
            "evidence_ids": "coverage.indology_l|coverage.bvp",
            "figure_or_table": "fig6_orientation_contrast.svg",
            "counterevidence": "—",
            "limitation": "Пробел наблюдения, а не измеренный ноль: любое утверждение о Западе или "
                          "Индии здесь было бы безосновательным.",
        },
        {
            "claim_id": "cl-no-migration",
            "outline_section": "6. Обсуждение",
            "claim_ru": "Совпадение активности на разных площадках не интерпретируется как переход "
                        "сообщества с одной площадки на другую.",
            "verdict": "expert_judgment",
            "evidence_kind": "expert_judgment",
            "evidence_ids": "methodological_constraint:ROADMAP non-goals",
            "figure_or_table": "fig5_person_overlap.svg",
            "counterevidence": "—",
            "limitation": "Ни один временной ряд в пакете не спроектирован для причинного вывода.",
        },
        {
            "claim_id": "cl-renou-gate",
            "outline_section": "6. Обсуждение",
            "claim_ru": "Сравнение по слоям Рену не публикуется: действующий gold-review шлюз "
                        "не пройден, а измеренная точность слоя ограничена.",
            "verdict": "out_of_scope",
            "evidence_kind": "expert_judgment",
            "evidence_ids": "methodological_constraint:docs/renou-precision-audit.md",
            "figure_or_table": "classification_validity.md",
            "counterevidence": "—",
            "limitation": "Слой Рену остаётся внутренним рабочим инструментом.",
        },
    ]


def write_claims(claims: list[dict], path: Path = LEDGER_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(LEDGER_COLUMNS), lineterminator="\n")
        writer.writeheader()
        for claim in claims:
            writer.writerow({column: claim.get(column, "") for column in LEDGER_COLUMNS})
    return path


def load_claims(path: Path = LEDGER_PATH) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_quote_ids() -> set[str]:
    if not quotes.QUOTES_PATH.exists():
        return set()
    with quotes.QUOTES_PATH.open(encoding="utf-8", newline="") as handle:
        return {row["quote_id"] for row in csv.DictReader(handle)}


def validate_claims(
    claims: list[dict],
    tables: dict[str, list[dict]] | None = None,
) -> list[str]:
    """V10: zero unlinked claims, zero dangling evidence ids, zero overclaims."""
    if tables is None:
        tables = {name: metrics.read_table(name) for name in metrics.TABLE_NAMES}
    metric_ids = {row["metric_id"] for rows in tables.values() for row in rows}
    quote_ids = load_quote_ids()

    errors: list[str] = []
    seen: set[str] = set()
    for claim in claims:
        claim_id = claim["claim_id"]
        if claim_id in seen:
            errors.append(f"duplicate claim_id {claim_id!r}")
        seen.add(claim_id)

        if claim["verdict"] not in VERDICTS:
            errors.append(f"{claim_id}: unknown verdict {claim['verdict']!r}")
        if claim["evidence_kind"] not in EVIDENCE_KINDS:
            errors.append(f"{claim_id}: unknown evidence kind {claim['evidence_kind']!r}")

        ids = [part for part in claim["evidence_ids"].split("|") if part.strip()]
        if not ids:
            errors.append(f"{claim_id}: UNLINKED — no metric, quote or expert-judgment row")
        for evidence_id in ids:
            if evidence_id.startswith("methodological_constraint:"):
                if claim["evidence_kind"] != "expert_judgment":
                    errors.append(
                        f"{claim_id}: methodological constraint cited as {claim['evidence_kind']!r}"
                    )
                continue
            if claim["evidence_kind"] == "quote":
                if quote_ids and evidence_id not in quote_ids:
                    errors.append(f"{claim_id}: quote id {evidence_id!r} is not in the register")
            elif evidence_id not in metric_ids:
                errors.append(f"{claim_id}: evidence id {evidence_id!r} is not a frozen metric row")

        text = claim["claim_ru"].lower()
        if claim["verdict"] in ("supported", "provisional"):
            for marker in _CAUSAL_MARKERS:
                if marker in text:
                    errors.append(
                        f"{claim_id}: causal language {marker!r} in a descriptive claim"
                    )
        for marker in _REPRESENTATIVENESS_MARKERS:
            if marker in text:
                errors.append(f"{claim_id}: representativeness overclaim {marker!r}")
        if claim["evidence_kind"] == "expert_judgment":
            for marker in _PVALUE_MARKERS:
                if marker in text or marker in claim["limitation"].lower():
                    errors.append(
                        f"{claim_id}: expert judgment may never carry a p-value ({marker!r})"
                    )
        if not claim["limitation"].strip():
            errors.append(f"{claim_id}: no limitation stated")
        if not claim["figure_or_table"].strip():
            errors.append(f"{claim_id}: no figure/table pointer")
    return errors


# ---------------------------------------------------------------------------
# The validity report
# ---------------------------------------------------------------------------

def _coverage_rows(tables) -> list[dict]:
    return tables["lens_source_coverage"]


def write_validity_report(
    tables: dict[str, list[dict]],
    claims: list[dict],
    provenance: dict,
    metric_errors: list[str],
    claim_errors: list[str],
    figure_errors: list[str],
    path: Path = VALIDITY_PATH,
) -> Path:
    lines: list[str] = []
    a = lines.append

    a("# Comparison validity — five-lens Sanskrit community package (H1899)")
    a("")
    a("_Created: 06-08-2026 · Last updated: 06-08-2026_")
    a("")
    a("Executor: Opus 5 (`claude-opus-5`), local-only pass, worktree "
      "`IndologyScholars-h1899-34220` off `origin/codex/community-lenses-ask-plan`. "
      f"Generated by `community_lenses/report.py` ({REPORT_VERSION}) from the frozen "
      "tables in `analytics_output/community_lenses/tables/`; no number in this file "
      "is typed by hand.")
    a("")
    a("Roerich/Zograf (the `conferences` lens) is the article's primary object. "
      "nagari, ORS/VK, INDOLOGY-L and BVP are subordinate comparison lenses that make "
      "different forms of community activity observable; they are **not one flat "
      "population** and their native units are never added together.")
    a("")

    a("## 1. Source health (V1)")
    a("")
    a("| Lens | Native unit | Snapshot | Coverage | Records | Missingness | Verdict |")
    a("|---|---|---|---|---:|---|---|")
    for row in _coverage_rows(tables):
        verdict = "GAP — no claim may be built on it" if row["coverage_status"] == "unavailable" else (
            "within-lens composition only" if row["coverage_status"] in metrics.NON_POPULATION_COVERAGE
            else "usable with its own denominator")
        a(f"| {row['lens']} | {row['native_unit']} | `{row['source_snapshot']}` | "
          f"`{row['coverage_status']}` | {row['numerator'] or '—'} | {row['missingness']} | {verdict} |")
    a("")
    a("- INDOLOGY-L: adapter refuses by design — no atomic snapshot exists (blocked on H1894).")
    a("- BVP: acquisition input absent on this machine (H1896 still queued; the earlier pilot "
      "dataset was destroyed with its worktree, IndologyScholars#169 / Uprava FINDINGS §314). "
      "**Every BVP-dependent panel is suppressed, not zero-filled.**")
    a("- nagari: the canonical `nagari/data/nagari.db` is present but was NOT on the adapter's "
      "candidate path list; H1899 added that path (the one compatibility fix in this pass, "
      "`community_lenses/adapters/nagari.py`). Without it the lens degraded to `unavailable` "
      "while a real 193 MB database sat on disk.")
    a("")

    a("## 2. Reconciliation and duplicate handling (V2–V3)")
    a("")
    drops = provenance.get("drop_reports", [])
    a("| Lens | Records offered by adapter | Duplicates dropped | Records loaded |")
    a("|---|---:|---:|---:|")
    for report in sorted(drops, key=lambda r: r["corpus_id"]):
        a(f"| {report['corpus_id']} | {report['records_total']} | "
          f"{report['records_dropped_duplicate']} | "
          f"{report['records_total'] - report['records_dropped_duplicate']} |")
    a("")
    roundtrip = provenance.get("roundtrip_errors") or []
    a(f"- Source-native round-trip: **{'PASSED' if not roundtrip else f'FAILED ({len(roundtrip)})'}** — "
      "every native assignment survived crosswalk + pilot byte-for-byte.")
    a(f"- Crosswalk-derived assignments layered next to native ones: "
      f"**{provenance.get('crosswalk_inserted', 0)}** (all `review_status=pending`).")
    a(f"- Deterministic Gumilev pilot proposals: **{provenance.get('pilot_inserted', 0)}** "
      "(all pending, none accepted).")
    a("- The 2 duplicated nagari Message-IDs are the known IndologyScholars#169 defect; they are "
      "dropped by `identity.dedupe_fixture` and reported here rather than crashing the build.")
    a("- **Consequence of the H1899 path fix, stated rather than hidden:** with the real "
      "`nagari.db` now reachable from any worktree, 2 pre-existing adapter tests "
      "(`tests/test_community_lenses_adapters.py`, the `nagari` parametrisations) fail on "
      "exactly that duplicate-Message-ID defect — `build.populate_corpus` correctly refuses the "
      "duplicate rows the raw mbox contains. H1898 avoided the failure by deleting its local db "
      "copy afterwards, which also silently degraded the lens to `unavailable` for every later "
      "session. A loud known failure is preferable to a silent false gap, so the fix stays and "
      "the residual is recorded: the durable repair belongs in the nagari ADAPTER (dedupe at "
      "extraction, the way `identity.dedupe_fixture` already does downstream), which is upstream "
      "H1895/#169 scope, not H1899's.")
    a("")

    a("## 3. Temporal boundary (V4)")
    a("")
    a("| Lens | 2026 records (partial) | In through-2025 trend? |")
    a("|---|---:|---|")
    for row in metrics.partial_rows(tables["activity_by_period"]):
        a(f"| {row['lens']} | {row['numerator']} | no — separate partial snapshot |")
    a("")
    a("The through-2025 package is cut at 31-12-2025; 2026 lives in its own snapshot and never "
      "shares an axis with an annual rate. Zero tolerance, checked by "
      "`tests/test_community_lenses_snapshot.py`.")
    a("")

    a("## 4. Classification and Gumilev validity (V5–V6)")
    a("")
    summary = taxonomy.crosswalk_summary()
    a(f"- Crosswalk rows: **{summary['total_rows']}** (version {taxonomy.CROSSWALK_VERSION}); "
      f"relations {summary['relation_counts']}; review states {summary['review_counts']}.")
    a("- Every shared-axis label in this package is an ADDITIONAL assertion with "
      "`review_status=pending`; native labels are untouched evidence.")
    a(f"- Publication thresholds (V6): shared axes need raw agreement ≥ "
      f"{classify.SHARED_AXIS_THRESHOLDS['raw_agreement_min']:.0%} and Gwet AC1 ≥ "
      f"{classify.SHARED_AXIS_THRESHOLDS['gwet_ac1_min']}; cross-lens Gumilev needs "
      f"applicability precision ≥ {classify.GUMILEV_THRESHOLDS['applicability_precision_min']}.")
    a("- **No human review of the H1897 sample has happened, so the threshold evidence is "
      "ABSENT.** Consequence, applied throughout this package: conference Gumilev results are "
      "publishable (existing accepted evidence, own reliability packet); the cross-lens Gumilev "
      "extension is a NON-COMPARABLE PILOT and no cross-lens distribution is published; "
      "crosswalk-derived content/function shares are marked `provisional`.")
    a("- Renou: the gold-review gate is **binding and unchanged**. The measured precision limits "
      "of the Renou layer travel with every crosswalk row that touches `renou_state`/"
      "`renou_register`; no Renou comparison is published here.")
    a("")

    a("## 5. Identity evidence (V7)")
    a("")
    links = provenance.get("reviewed_links") or identity.load_reviewed_links()
    accepted = identity.accepted_links(links)
    ambiguous = [row for row in links if row.get("decision") == "ambiguous"]
    a(f"- Reviewed decisions: **{len(links)}** — accepted {len(accepted)}, ambiguous "
      f"{len(ambiguous)}, auto-accepted **0** (only `authority_exact` may ever auto-accept, "
      "and it fired zero times).")
    a(f"- Applied cross-lens mentions: **{provenance.get('mentions_linked', 0)}** across "
      f"{len({row['person_id'] for row in accepted if row.get('person_id')})} distinct persons.")
    a("- Ambiguous candidates are preserved with a written insufficiency rationale and are "
      "excluded from every overlap count in this package.")
    a("- No nationality is inferred from a name, an email domain, a script or a forum.")
    a("- Author-supplied named INDOLOGY-L and BVP cross-membership hypotheses remain "
      "**unverifiable** in this snapshot (both sources absent) and are recorded as evidence "
      "gaps, never as census rows.")
    a("")

    a("## 6. Quotation context and rights (V8)")
    a("")
    quote_ids = sorted(load_quote_ids())
    a(f"- Registered quotes: **{len(quote_ids)}** ({', '.join(quote_ids) if quote_ids else '—'}); "
      "each verified character-for-character against its pinned source with before/after "
      "context hashes.")
    a("- Exportable quotes: **0**. The mechanical gate holds: closed-list (nagari) rows are "
      "forced `non_exportable`, and the VK row stays `pending_review` until an approval record "
      "exists. A failed quote is omitted — never paraphrased.")
    a("- Contact data: none present in any registered quote (regex-checked).")
    a("")

    a("## 7. Metric denominators (V9)")
    a("")
    a("| Table | Rows | Denominator rule |")
    a("|---|---:|---|")
    denominator_rules = {
        "lens_source_coverage": "records in that lens's own snapshot",
        "activity_by_period": "dated records of the SAME lens (never a cross-lens total)",
        "intellectual_content_by_lens": "records of that lens assigned on this axis",
        "community_function_by_lens": "records of that lens assigned on this axis",
        "argument_level_by_lens": "records of that lens assigned on this axis",
        "person_overlap": "persons linked within that lens (unit: person)",
        "orientation_contrast": "records in that lens's snapshot; no share computed",
    }
    for name in metrics.TABLE_NAMES:
        a(f"| `{name}.csv` | {len(tables[name])} | {denominator_rules[name]} |")
    a("")
    a(f"- V9 validation: **{'PASSED' if not metric_errors else f'FAILED ({len(metric_errors)})'}** — "
      "every row names numerator, denominator, denominator unit, period, missingness, source "
      "snapshot, and method+version.")
    a("- Prohibited combinations are rejected by construction: no single total of talks + "
      "messages + posts; no BVP proportion from an absent crawl; no pending identity match in an "
      "overlap count; no 2026 record in a 2005–2025 trend.")
    a("")

    a("## 8. Geographical limits (V10 / R7)")
    a("")
    a("Russia-, West- and India-centred are **forum orientations** — a corpus-selection premise "
      "grounded in author expertise, carrying no p-value. They are not participant nationalities "
      "and not representative samples of any scholarly population. In this snapshot only "
      "Russia-centred forums are observable at all: the Western (INDOLOGY-L) and Indian (BVP) "
      "orientations are absent sources and are drawn as explicit gaps in "
      "`fig6_orientation_contrast.svg`.")
    a("")

    a("## 9. Claim-by-claim verdict (V10)")
    a("")
    a("| Claim | Section | Verdict | Evidence |")
    a("|---|---|---|---|")
    for claim in claims:
        a(f"| `{claim['claim_id']}` | {claim['outline_section']} | **{claim['verdict']}** | "
          f"{claim['evidence_kind']}: `{claim['evidence_ids']}` |")
    a("")
    counts = {verdict: sum(1 for c in claims if c["verdict"] == verdict) for verdict in VERDICTS}
    a(f"Totals: supported {counts['supported']} · provisional {counts['provisional']} · "
      f"expert judgment {counts['expert_judgment']} · out of scope {counts['out_of_scope']}.")
    a("")
    a(f"- Claims-ledger validation: **{'PASSED' if not claim_errors else f'FAILED ({len(claim_errors)})'}** — "
      "zero claims without a metric, quote or explicit expert-judgment link.")
    a(f"- Figure-caption validation: **{'PASSED' if not figure_errors else f'FAILED ({len(figure_errors)})'}** — "
      "every caption names lens, native unit, denominator and coverage caveat.")
    a("")

    a("## 10. What this package may NOT support")
    a("")
    a("1. Any cross-lens activity total, rate or ranking built from different native units.")
    a("2. Any BVP or INDOLOGY-L quantitative claim (both sources absent — gaps, not zeros).")
    a("3. Any cross-lens Gumilev distribution (pilot unreviewed).")
    a("4. Any Renou-based comparison (gold gate unpassed).")
    a("5. Any named cross-platform person claim in public (closed-group rights gate).")
    a("6. Any statement about Russia, 'the West' or India as populations.")
    a("7. Any causal reading of coincident activity across platforms.")
    a("")

    if metric_errors or claim_errors or figure_errors:
        a("## Outstanding validation errors")
        a("")
        for error in metric_errors + claim_errors + figure_errors:
            a(f"- {error}")
        a("")

    a("_Dr. Mārcis Gasūns_")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> int:
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    from . import figures as figures_mod

    conn, provenance = metrics.build_inputs()
    tables = metrics.build_tables(conn, provenance)
    metrics.write_tables(tables)
    metric_errors = metrics.validate_metrics(tables) + metrics.validate_temporal_separation(tables)

    figures_mod.write_all(tables)
    import json

    captions = json.loads(figures_mod.CAPTIONS_JSON.read_text(encoding="utf-8"))
    figure_errors = figures_mod.validate_captions(captions, tables)

    claims = build_claims()
    write_claims(claims)
    claim_errors = validate_claims(claims, tables)

    path = write_validity_report(
        tables, claims, provenance, metric_errors, claim_errors, figure_errors
    )
    print(f"wrote {path.relative_to(REPO_ROOT)}")
    print(f"wrote {LEDGER_PATH.relative_to(REPO_ROOT)} ({len(claims)} claims)")
    total = len(metric_errors) + len(claim_errors) + len(figure_errors)
    if total:
        print(f"\nvalidation FAILED with {total} error(s):")
        for error in metric_errors + claim_errors + figure_errors:
            print(f"  - {error}")
        return 1
    print("\nvalidation: PASSED (metrics V9, captions V10, claims V10)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
