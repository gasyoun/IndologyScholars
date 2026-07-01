# INDOLOGY-L as Scholarly Infrastructure, 1990-2026

This report reads the INDOLOGY mailing-list archive as a long-running scholarly infrastructure: a reference desk, announcement board, technical support forum, bibliographic exchange, and conversation network. The summaries below are generated from public archive metadata and should be read as guides to further close reading, not as final social rankings.

## Coverage

- Months: 426
- Messages: 62,112
- Threads: 24,033
- Raw author strings: 3,283
- Author strings needing review: 888
- Directed reply rows: 42,741
- Resolved directed replies: 37,095
- Aggregated directed reply edges: 20,782

## Method Notes

- Author normalization is conservative: exact display-name groups are confirmed, email-like and short labels are retained for review.
- `network_edges.csv` is an undirected co-participation network, not a reply network.
- `reply_edges.csv` is the stricter directed network and records confidence for each edge.
- `atlas_list_functions.csv` assigns readable list-function categories from subject-line patterns; uncategorized messages fall back to `general discussion`.
- `case_study_candidates.csv` ranks threads for human review by thread length, author count, reply density, topic variety, and request/resolution/debate language.
- `thread_explorer_index.csv` links selected candidates to local static thread pages. These pages use metadata and subject lines only.
- `curated_case_studies.csv` is seeded with `candidate` status for manual review; generated candidates are not a curated canon.
- `case_review_queue.csv` supports English-only review across two tracks: philological substance and infrastructure history.
- Named network summaries describe public reply and co-participation evidence, not influence, prestige, or importance.
- `human_review_index.csv` combines review needs across author normalization, case studies, parse quirks, noisy subjects, and reply evidence.
- `interpretive_guardrails.csv` and `reports/interpretive_guardrails.md` state which public claims are supported and which overclaims should be avoided.
- `renou_messages.csv` adds a sparse Renou state/register subject-line crosswalk from `RENOU.md`; unmatched rows mean not classified by this layer, not irrelevant to Renou.
- Count mismatches are documented in `count_mismatch_audit.csv`; extra mbox rows are preserved in `skipped_mbox_rows.csv`.

## What Changed Over Time?

| decade | messages | threads | max_yearly_authors |
| --- | --- | --- | --- |
| 1990s | 19692 | 7745 | 536 |
| 2000s | 14212 | 5326 | 480 |
| 2010s | 17710 | 6873 | 309 |
| 2020s | 10498 | 4089 | 317 |

## What Was Discussed?

| topic | messages | threads | authors | top_list_function |
| --- | --- | --- | --- | --- |
| General scholarly discussion | 45544 | 17531 | 2794 | general discussion |
| Announcements and events | 2792 | 2436 | 791 | announcement/event |
| Bibliographic requests | 2592 | 1464 | 696 | bibliographic request |
| History and culture | 2587 | 1579 | 856 | general discussion |
| Digital resources and tools | 2447 | 1436 | 645 | digital resource/tool |
| Texts and philology | 1953 | 1038 | 621 | philological discussion |
| Veda and ritual | 1394 | 783 | 490 | general discussion |
| Grammar and linguistics | 1001 | 463 | 347 | philological discussion |
| Manuscripts and epigraphy | 991 | 462 | 344 | general discussion |
| Buddhism and Jainism | 507 | 340 | 262 | general discussion |

## Renou State/Register Layer

This sparse layer adapts the Louis Renou state and register axes documented in `RENOU.md` to INDOLOGY-L subject lines. It is a finding aid for discussions that clearly mention Vedic, Pāṇinian, epic, classical, Buddhist/Jaina, or register-specific material. It is not dictionary headword tagging and should not be read as a complete classification of all messages.

| scope | total_rows | matched_rows | matched_percent | source_url |
| --- | --- | --- | --- | --- |
| messages | 62112 | 6217 | 10.01 | https://github.com/gasyoun/SanskritLexicography/blob/master/RussianTranslation/RENOU.md |
| threads | 24033 | 3309 | 13.77 | https://github.com/gasyoun/SanskritLexicography/blob/master/RussianTranslation/RENOU.md |

| renou_code | renou_label | message_count | thread_count |
| --- | --- | --- | --- |
| I | Vedic | 1528 | 881 |
| III | Epic & prolongements | 1213 | 662 |
| V | Buddhist / Jaina | 753 | 534 |
| II | Pāṇinian | 724 | 366 |
| IV | Classical | 324 | 181 |

| renou_code | renou_label | message_count | thread_count |
| --- | --- | --- | --- |
| vyakarana | Vyākaraṇa | 649 | 325 |
| epic | Epic | 563 | 340 |
| rgveda | Ṛgveda | 523 | 285 |
| kavya | Kāvya | 518 | 258 |
| jaina | Jaina | 365 | 290 |
| epig | Epigraphic | 355 | 209 |
| bhasya | Bhāṣya | 293 | 154 |
| tantra | Tantra | 211 | 122 |
| katha | Kathā | 174 | 115 |
| purana | Purāṇa | 158 | 90 |
| upanisad | Upaniṣad | 144 | 79 |
| natya | Nāṭya | 124 | 73 |

| thread_root_id | thread_subject | renou_states | renou_registers | matched_message_count | confidence | first_url |
| --- | --- | --- | --- | --- | --- | --- |
| 000009 | forwarded message: seeking Mahabharata e-text. | III | epic | 1 | subject_pattern | https://list.indology.info/pipermail/indology/1990-November/000009.html |
| 000116 | Vedic dates | I |  | 2 | subject_pattern | https://list.indology.info/pipermail/indology/1991-August/000116.html |
| 000167 | need info about grammar book | II | vyakarana | 1 | subject_pattern | https://list.indology.info/pipermail/indology/1991-November/000167.html |
| 000192 | 5.0679 Qs: Pali E-Texts; COMPress; Bergen Libraries... (5/109) | V |  | 1 | subject_pattern | https://list.indology.info/pipermail/indology/1992-February/000192.html |
| 000193 | 5.0679 Qs: Pali E-Texts; COMPress; Bergen Libraries... (5/109 | V |  | 1 | subject_pattern | https://list.indology.info/pipermail/indology/1992-February/000193.html |
| 000200 | help on Mahabharata passage | III | epic | 3 | subject_pattern | https://list.indology.info/pipermail/indology/1992-March/000200.html |
| 000206 | Mahabharata 5.172.20 follow-up | III | epic | 2 | subject_pattern | https://list.indology.info/pipermail/indology/1992-March/000206.html |
| 000255 | National scandal: Ganesha being sold as a "monster"! |  | epig | 1 | subject_pattern | https://list.indology.info/pipermail/indology/1992-June/000255.html |
| 000265 | Chaulukya period inscriptions |  | epig | 2 | subject_pattern | https://list.indology.info/pipermail/indology/1992-June/000265.html |
| 000323 | Harivamsa Translation | III | epic | 2 | subject_pattern | https://list.indology.info/pipermail/indology/1992-September/000323.html |
| 000324 | Surgery | III | epic | 2 | subject_pattern | https://list.indology.info/pipermail/indology/1992-September/000324.html |
| 000336 | Harivamsa Translation | III | epic | 1 | subject_pattern | https://list.indology.info/pipermail/indology/1992-September/000336.html |

## What Work Did The List Do?

| list_function | messages |
| --- | --- |
| general discussion | 47824 |
| identification/help request | 3280 |
| philological discussion | 3126 |
| digital resource/tool | 2420 |
| announcement/event | 2262 |
| bibliographic request | 1362 |
| job/position | 892 |
| debate/controversy | 481 |
| obituary/memorial | 195 |
| list administration | 194 |

## Who Participated?

| normalized_author | message_count | thread_count | first_year | last_year | top_list_function | author_status |
| --- | --- | --- | --- | --- | --- | --- |
| Dominik Wujastyk | 3413 | 2766 | 1990 | 2026 | general discussion | confirmed |
| Madhav Deshpande | 1888 | 1107 | 1994 | 2026 | general discussion | confirmed |
| N. Ganesan | 1126 | 608 | 1997 | 2001 | general discussion | confirmed |
| Harry Spier | 1044 | 647 | 1999 | 2026 | general discussion | confirmed |
| Nagaraj Paturi | 832 | 401 | 2014 | 2026 | general discussion | confirmed |
| Matthew Kapstein | 805 | 578 | 2001 | 2026 | general discussion | confirmed |
| Lars Martin Fosse | 784 | 490 | 1992 | 2016 | general discussion | confirmed |
| Sudalaimuthu Palaniappan | 782 | 513 | 1997 | 2026 | general discussion | confirmed |
| Allen W Thrasher | 603 | 492 | 1997 | 2010 | general discussion | confirmed |
| Jonathan Silk | 600 | 487 | 1997 | 2026 | general discussion | confirmed |
| Vidyasankar Sundaresan | 574 | 343 | 1995 | 2001 | general discussion | confirmed |
| Jan E.M. Houben | 559 | 437 | 1997 | 2026 | general discussion | confirmed |
| Christophe Vielle | 553 | 444 | 2002 | 2026 | general discussion | confirmed |
| Dipak Bhattacharya | 549 | 398 | 2008 | 2018 | general discussion | confirmed |
| Arlo Griffiths | 516 | 442 | 1998 | 2026 | general discussion | confirmed |

## Who Replied To Whom?

| confidence | reply_rows | resolved_rows | share |
| --- | --- | --- | --- |
| thread_inferred | 22907 | 22907 | 0.5359 |
| exact_in_reply_to | 14076 | 14076 | 0.3293 |
| unresolved | 5646 | 0 | 0.1321 |
| references_chain | 112 | 112 | 0.0026 |

## Threads Worth Reading

The following are automatically selected candidates for close reading, not a curated canon.

| case_score | subject | primary_topic | list_function | message_count | author_count | reply_count | page_path |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 427 | A distraction from the Coronavirus | General scholarly discussion | general discussion | 122 | 19 | 122 | threads/001-052077-a-distraction-from-the-coronavirus.html |
| 388 | SV: Paired Horse and PIE breakup | General scholarly discussion | general discussion | 108 | 14 | 106 | threads/002-013924-sv-paired-horse-and-pie-breakup.html |
| 338 | "Science" in India | History and culture | general discussion | 70 | 34 | 68 | threads/003-023195-science-in-india.html |
| 285 | Sexism and Bias on INDOLOGY governing committee | General scholarly discussion | debate/controversy | 56 | 35 | 55 | threads/004-049728-sexism-and-bias-on-indology-governing-committee.html |
| 284 | Ontology of Ramanuja | General scholarly discussion | general discussion | 74 | 12 | 73 | threads/005-015606-ontology-of-ramanuja.html |
| 282 | Non-standard sandhi | Grammar and linguistics | philological discussion | 82 | 10 | 81 | threads/006-049514-non-standard-sandhi.html |
| 279 | Tamil words in English | General scholarly discussion | general discussion | 59 | 26 | 57 | threads/007-010710-tamil-words-in-english.html |
| 264 | questions: hymns, latAveZin, manner of death | General scholarly discussion | general discussion | 58 | 20 | 57 | threads/008-015672-questions-hymns-latavezin-manner-of-death.html |
| 257 | Millennium | General scholarly discussion | general discussion | 61 | 16 | 60 | threads/009-019623-millennium.html |
| 247 | BiBTeX Packages for citing MSS | Veda and ritual | general discussion | 47 | 22 | 46 | threads/010-020450-bibtex-packages-for-citing-mss.html |
| 238 | Pancaratna of the MBh? | General scholarly discussion | general discussion | 44 | 26 | 43 | threads/011-030283-pancaratna-of-the-mbh.html |
| 233 | Johannes Bronkhorst gone | General scholarly discussion | general discussion | 39 | 38 | 38 | threads/012-060627-johannes-bronkhorst-gone.html |
| 232 | South India geography | General scholarly discussion | general discussion | 53 | 15 | 51 | threads/013-012389-south-india-geography.html |
| 229 | Early Giithaa sculptures | General scholarly discussion | general discussion | 49 | 16 | 47 | threads/014-014966-early-giithaa-sculptures.html |
| 229 | 'Siva and Avalokitezvara | General scholarly discussion | general discussion | 55 | 14 | 54 | threads/015-014599-siva-and-avalokitezvara.html |

## Curated Case-Study Workflow

Case-study curation is English-only. Rows remain `candidate` until a human reviewer changes the status to `selected`, `rejected`, or `needs_more_review`.

| curation_status | effective_track | case_type | thread_count |
| --- | --- | --- | --- |
| candidate |  | general discussion | 186 |
| candidate |  | announcement | 3 |
| candidate |  | bibliographic rescue | 3 |
| candidate |  | debate/controversy | 3 |
| candidate |  | announcement/event | 1 |
| candidate |  | memorial/community memory | 1 |
| candidate | infrastructure_history | digital resource/tool | 6 |
| candidate | infrastructure_history | general discussion | 6 |
| candidate | infrastructure_history | bibliographic rescue | 2 |
| candidate | infrastructure_history | philological debate | 2 |
| candidate | philological_substance | identification/help request | 15 |
| candidate | philological_substance | general discussion | 13 |
| candidate | philological_substance | philological debate | 7 |
| candidate | philological_substance | philological discussion | 2 |

- Review queue rows: 250
- First review shortlist rows: 25
- Philological review packet rows: 37
- Infrastructure review packet rows: 16
- Unassigned review packet rows: 197
- Review import audit rows: 25
- Unified human review index rows: 1,921
- Interpretive guardrail rows: 7

| review_priority_reason | short_title | effective_track | case_type | message_count | author_count | reply_count | page_path |
| --- | --- | --- | --- | --- | --- | --- | --- |
| highest overall candidate score | A distraction from the Coronavirus |  | general discussion | 122 | 19 | 122 | threads/001-052077-a-distraction-from-the-coronavirus.html |
| highest overall candidate score | SV: Paired Horse and PIE breakup |  | general discussion | 108 | 14 | 106 | threads/002-013924-sv-paired-horse-and-pie-breakup.html |
| highest overall candidate score | "Science" in India |  | general discussion | 70 | 34 | 68 | threads/003-023195-science-in-india.html |
| highest overall candidate score | Sexism and Bias on INDOLOGY governing committee |  | debate/controversy | 56 | 35 | 55 | threads/004-049728-sexism-and-bias-on-indology-governing-committee.html |
| highest overall candidate score | Ontology of Ramanuja |  | general discussion | 74 | 12 | 73 | threads/005-015606-ontology-of-ramanuja.html |
| highest overall candidate score | Non-standard sandhi | philological_substance | philological debate | 82 | 10 | 81 | threads/006-049514-non-standard-sandhi.html |
| highest overall candidate score | Tamil words in English |  | general discussion | 59 | 26 | 57 | threads/007-010710-tamil-words-in-english.html |
| philological substance track | BiBTeX Packages for citing MSS | philological_substance | general discussion | 47 | 22 | 46 | threads/010-020450-bibtex-packages-for-citing-mss.html |
| philological substance track | Correction re: Cerebral L in Rg Veda | philological_substance | general discussion | 39 | 21 | 38 | threads/018-024160-correction-re-cerebral-l-in-rg-veda.html |
| philological substance track | Early excommunications from / inclusions into vedic ... | philological_substance | general discussion | 45 | 14 | 44 | threads/031-013052-early-excommunications-from-inclusions-into-vedic.html |
| philological substance track | question for European Indologists | philological_substance | identification/help request | 30 | 24 | 29 | threads/039-038062-question-for-european-indologists.html |
| philological substance track | Query on verse forms | philological_substance | identification/help request | 45 | 5 | 44 | threads/044-050859-query-on-verse-forms.html |
| infrastructure history track | HTML Based Email (AOL 6.0) | infrastructure_history | general discussion | 46 | 19 | 44 | threads/017-023602-html-based-email-aol-6-0.html |
| infrastructure history track | Update 2 to Pali Canon online | infrastructure_history | digital resource/tool | 39 | 22 | 38 | threads/025-006983-update-2-to-pali-canon-online.html |
| infrastructure history track | Vedic Website | infrastructure_history | digital resource/tool | 27 | 14 | 26 | threads/070-006442-vedic-website.html |
| infrastructure history track | INSA email address? | infrastructure_history | general discussion | 29 | 12 | 28 | threads/075-016462-insa-email-address.html |
| infrastructure history track | Manuscript collections on archive.org | infrastructure_history | philological debate | 28 | 14 | 27 | threads/081-057928-manuscript-collections-on-archive-org.html |
| debate or controversy case type | Vicious Debate |  | debate/controversy | 35 | 10 | 33 | threads/066-014354-vicious-debate.html |
| debate or controversy case type | "samsara" meaning "life" | philological_substance | philological debate | 23 | 15 | 21 | threads/090-032536-samsara-meaning-life.html |
| debate or controversy case type | references to tuLu language in ancient Tamil text | philological_substance | philological debate | 26 | 14 | 25 | threads/109-015333-references-to-tulu-language-in-ancient-tamil-text.html |
| community memory or announcement case type | Johannes Bronkhorst gone |  | memorial/community memory | 39 | 38 | 38 | threads/012-060627-johannes-bronkhorst-gone.html |
| community memory or announcement case type | Event announcement: Testing Workshop |  | announcement | 21 | 13 | 19 | threads/100-005629-event-announcement-testing-workshop.html |
| community memory or announcement case type | New publication |  | announcement/event | 24 | 15 | 23 | threads/143-043031-new-publication.html |
| high-participation unassigned candidate | questions: hymns, latAveZin, manner of death |  | general discussion | 58 | 20 | 57 | threads/008-015672-questions-hymns-latavezin-manner-of-death.html |
| high-participation unassigned candidate | Millennium |  | general discussion | 61 | 16 | 60 | threads/009-019623-millennium.html |

## How To Read Thread Pages

- Thread pages show chronology, participants, public archive links, and a compact directed-reply map.
- Conversation-map rows keep reply confidence visible: exact header matches are stronger than thread-inferred links.
- Unresolved reply-like messages are separated rather than forced into the graph.
- `curated_case_studies.csv` is the place to add human notes before presenting a thread as an interpreted example.
- `case_review_queue.csv` separates generated evidence from human public notes.

## Named Network Summaries

The named network tables are public-archive metadata summaries. `direct_reply` rows come from reply evidence; `co_participation` rows mean two authors appear in the same thread. Self-reply rows are flagged and omitted from the sample table below.

| network_type | source_author | target_author | decade | primary_topic | confidence | reply_count | is_self_reply |
| --- | --- | --- | --- | --- | --- | --- | --- |
| direct_reply | Paul Kekai Manansala | N. Ganesan | 1990s | General scholarly discussion | thread_inferred | 56 | False |
| direct_reply | N. Ganesan | Sudalaimuthu Palaniappan | 1990s | General scholarly discussion | thread_inferred | 35 | False |
| direct_reply | Madhav Deshpande | Christian Ferstl | 2020s | General scholarly discussion | thread_inferred | 28 | False |
| direct_reply | Madhav Deshpande | Harry Spier | 2020s | General scholarly discussion | exact_in_reply_to | 28 | False |
| direct_reply | N. Ganesan | Swaminathan Madhuresan | 1990s | General scholarly discussion | thread_inferred | 27 | False |
| direct_reply | Christian Ferstl | Madhav Deshpande | 2020s | General scholarly discussion | exact_in_reply_to | 27 | False |
| direct_reply | Hock, Hans Henrich | Madhav Deshpande | 2020s | General scholarly discussion | exact_in_reply_to | 26 | False |
| direct_reply | Lars Martin Fosse | N. Ganesan | 1990s | General scholarly discussion | thread_inferred | 26 | False |
| direct_reply | DEVARAKONDA VENKATA NARAYANA SARMA | Sudalaimuthu Palaniappan | 1990s | General scholarly discussion | thread_inferred | 25 | False |
| direct_reply | Nagaraj Paturi | patrick mccartney | 2010s | General scholarly discussion | exact_in_reply_to | 24 | False |
| direct_reply | Petr Mares | Swaminathan Madhuresan | 1990s | General scholarly discussion | thread_inferred | 24 | False |
| direct_reply | Miguel Carrasquer Vidal | N. Ganesan | 1990s | General scholarly discussion | thread_inferred | 23 | False |
| direct_reply | N. Ganesan | Edwin Bryant | 1990s | General scholarly discussion | thread_inferred | 22 | False |
| direct_reply | Nagaraj Paturi | Artur Karp | 2010s | General scholarly discussion | exact_in_reply_to | 21 | False |
| direct_reply | Vidyasankar Sundaresan | Sudalaimuthu Palaniappan | 2000s | General scholarly discussion | thread_inferred | 20 | False |

| network_type | source_author | target_author | topic | thread_count |
| --- | --- | --- | --- | --- |
| co_participation | Dominik Wujastyk | Madhav Deshpande | Announcements and events | 154 |
| co_participation | Dominik Wujastyk | Madhav Deshpande | Bibliographic requests | 154 |
| co_participation | Dominik Wujastyk | Madhav Deshpande | Buddhism and Jainism | 154 |
| co_participation | Dominik Wujastyk | Madhav Deshpande | Digital resources and tools | 154 |
| co_participation | Dominik Wujastyk | Madhav Deshpande | General scholarly discussion | 154 |
| co_participation | Dominik Wujastyk | Madhav Deshpande | Grammar and linguistics | 154 |
| co_participation | Dominik Wujastyk | Madhav Deshpande | History and culture | 154 |
| co_participation | Dominik Wujastyk | Madhav Deshpande | Manuscripts and epigraphy | 154 |
| co_participation | Dominik Wujastyk | Madhav Deshpande | Texts and philology | 154 |
| co_participation | Dominik Wujastyk | Madhav Deshpande | Veda and ritual | 154 |
| co_participation | Dominik Wujastyk | Matthew Kapstein | Announcements and events | 113 |
| co_participation | Dominik Wujastyk | Matthew Kapstein | Bibliographic requests | 113 |
| co_participation | Dominik Wujastyk | Matthew Kapstein | Buddhism and Jainism | 113 |
| co_participation | Dominik Wujastyk | Matthew Kapstein | Digital resources and tools | 113 |
| co_participation | Dominik Wujastyk | Matthew Kapstein | General scholarly discussion | 113 |

## Archive Caveats

- Count-mismatch months documented: 8
- Early archive metadata contains empty subjects and legacy email/address strings.
- Direct reply reconstruction is incomplete where headers are missing or reference messages fall outside the harvested archive.

## Ethical Notes

- Names and email-like strings are taken from a public scholarly mailing-list archive.
- The normalization table is an audit instrument, not a biographical authority file.
- Ambiguous identities remain reviewable instead of silently merged.
- Data reuse files (`data_dictionary.md`, `datapackage.json`, and `CITATION.cff`) describe generated metadata separately from the source archive.
