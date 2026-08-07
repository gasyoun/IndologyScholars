# Classification validity — shared axes, crosswalk, and Gumilev pilot (H1897)

_Created: 31-07-2026 · Last updated: 31-07-2026_

Produced by `community_lenses/classify.py` (H1897, Fable 5 `claude-fable-5`); deterministic, no RNG. Native classification is immutable evidence: every shared assignment below is an ADDITIONAL assertion with `review_status=pending`.

## Scheme and label inventory

| Scheme | Kind | Coverage | Distinct labels |
|---|---|---|---|
| `argument_level` | shared Gumilev argument-level scale (canonical field argument_level; gumilyov_level is a legacy alias) | available | 5 |
| `bvp_native` | source-native taxonomy (BVP native categories) | unavailable | 0 |
| `community_function` | shared axis (what the item does in its medium) | available | 17 |
| `conferences_meso` | source-native controlled taxonomy (meso codes) | available | 53 |
| `conferences_theme_l1` | source-native controlled taxonomy (disciplinary rubric) | available | 6 |
| `conferences_theme_l2` | source-native controlled taxonomy (period axis) | available | 7 |
| `conferences_theme_l3` | source-native controlled taxonomy (evidence-medium axis) | available | 6 |
| `conferences_theme_l4` | source-native controlled taxonomy (mode axis) | available | 3 |
| `indology_l_atlas_function` | source-native taxonomy (INDOLOGY-L Atlas list functions) | unavailable | 0 |
| `indology_l_atlas_topic` | source-native taxonomy (INDOLOGY-L Atlas topic profiles) | unavailable | 0 |
| `intellectual_content` | shared axis (what the item is about) | available | 12 |
| `nagari_native_taxonomy` | source-native controlled taxonomy | available | 11 |
| `native_topic` | per-source namespace codebook | available | 7 |
| `renou_register` | independent historical-linguistic scheme (Renou register) | available | 21 |
| `renou_state` | independent historical-linguistic scheme (Renou état) | available | 7 |
| `shared_topic` | superseded shared content axis (H1893 predecessor of intellectual_content) | available | 11 |

Frozen before crosswalking; provenance per scheme is recorded in `community_lenses/taxonomy.py` `SCHEME_INVENTORY`.

## Crosswalk

- Total rows: **156** (version 1.0.0, all rows carry relation, rationale, evidence count, review state, and version).
- Relation counts: {'broad': 2, 'exact': 18, 'narrow': 53, 'related': 60, 'unmapped': 23}
- Review-state counts: {'pending': 156} — every mapping is an adjudicated PROPOSAL awaiting human review; nothing is auto-accepted.
- Rows per source scheme: {'conferences_meso': 69, 'conferences_theme_l1': 7, 'conferences_theme_l2': 7, 'conferences_theme_l3': 6, 'conferences_theme_l4': 3, 'nagari_native_taxonomy': 15, 'native_topic': 7, 'renou_register': 23, 'renou_state': 8, 'shared_topic': 11}
- Explicit `unmapped` adjudications: 23 labels (each with a written rationale; see the CSV).
- Contract validation: **clean**.

## Source-native round-trip

**PASSED** — every source-native assignment (record, scheme, label, value, method, review state) survived crosswalk application and the pilot byte-for-byte; shared assignments were layered next to them (1158 crosswalk-derived rows inserted).

## Lens coverage at classification time

| Lens | Coverage status | Records |
|---|---|---|
| bvp | partial | 156 |
| conferences | complete | 1362 |
| indology_l | unavailable | 1 |
| nagari | pilot | 300 |
| vk_ors | complete | 7608 |

- INDOLOGY-L: adapter unavailable (blocked on H1894); its Atlas topic/function schemes are declared in the inventory with crosswalk coverage `unavailable` — no labels were invented from planning prose.
- BVP: partial acquisition; no native category scheme observed, so `bvp_native` remains a reserved namespace. All BVP percentages downstream must carry explicit denominators (partial coverage limits classification claims).
- nagari: pilot slice; shared-axis label shares from this lens are pilot-denominator only.

## Gumilev argument-level pilot

Existing conference `argument_level` is canonical accepted evidence (distribution: {'G1': 1145, 'G2': 205, 'G3': 11}); `gumilyov_level` is a legacy alias, not a second scale, and was not re-proposed.

Pilot lenses (nagari, vk_ors, bvp): deterministic ruleset `h1897-argument-rules-1.0.0` proposed 8064 labels, all `review_status=pending`:

| Proposed level | Count |
|---|---|
| G1 | 131 |
| G2 | 0 |
| G3 | 1 |
| not_applicable | 7 |
| unknown | 7925 |

Announcements, bare links, greetings, and bibliography-only requests are `not_applicable` by rule (checked before any G rule, so none can be forced into G1); undecidable applicability is `unknown`.

## Review sample design

- File: `analytics_output/community_lenses/review/classification_sample.csv` (115 rows).
- Deterministic: candidate ordering and selection use SHA-256 of `record_id`; re-running on the same snapshot reproduces the identical sample.
- Strata: every proposed G3 (all of them), a G2 oversample (cap 60), an ambiguous `unknown`/`not_applicable` boundary sample per pilot lens (15 each), then per-lens floors {'conferences': 40, 'vk_ors': 40, 'nagari': 20, 'bvp': 10} stratified by period × native-class presence × proposed level.
- Selected per lens: {'bvp': 15, 'conferences': 40, 'nagari': 20, 'vk_ors': 40}
- Selected per stratum family: {'floor': 69, 'pilot': 46}

## Decision thresholds and gate status

Shared axes (VERIFICATION V6): raw agreement >= 80%, Gwet AC1 >= 0.7, no article-critical label below 0.7 precision. Cross-lens Gumilev: applicability precision >= 0.9, raw level agreement >= 80%, Gwet AC1 >= 0.67, every accepted G3 reviewed.

**Threshold evidence is ABSENT: no human review of this sample has happened yet, so the cross-lens Gumilev extension is a NON-COMPARABLE PILOT and no cross-lens Gumilev distribution may be published.** Conference Gumilev results (with their existing reliability packet) remain the only publishable argument-level evidence.

**Renou gate: BINDING and unchanged.** The Renou layer's measured precision limitations (`docs/renou-precision-audit.md`: title-regex method, unanchored Cyrillic substrings, 57.3% conference / 10.0% archive coverage) travel with every crosswalk row that touches `renou_state`/`renou_register`; a classification suggestion is not an accepted assignment, and the existing gold-review gate is unmodified by H1897.

No model-only score counts as human validation; a crosswalk or pilot proposal can only become `accepted` through a recorded reviewer decision (`validate_crosswalk` enforces a `reviewer:` note for any accepted row).

_Dr. Mārcis Gasūns_
