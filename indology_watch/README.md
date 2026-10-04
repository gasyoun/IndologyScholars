# INDOLOGY daily watch — контракт

_Created: 04-10-2026 · Last updated: 04-10-2026_

Повод: рулинг MG 04-10-2026 («can you read the indology forum daily?») после того, как
Second CFP 9-го ISCLS (Пуна, 20–22-01-2027, дедлайн 20-10-2026) пришёл в INDOLOGY, а наш
venue-watch ждал 9-е издание в ~2029 — дрейт вскрыл гриль
[DECIDE_BRIEF_iscls9-cfp-response_04-10-2026](https://github.com/gasyoun/Uprava/blob/main/decide_briefs/DECIDE_BRIEF_iscls9-cfp-response_04-10-2026.md).

## Что это

Ежедневный агентный триаж списка INDOLOGY
([list.indology.info](https://list.indology.info/mailman/listinfo/indology)). Источник —
публичный pipermail-архив <https://list.indology.info/pipermail/indology/> (помесячные
`YYYY-Month.txt.gz`, полные mbox). Расписание: ZCode cron **09:30 локального** времени,
workspace `github-efbbd2ba217bdb21`. Известное ограничение (замер 04-10): pipermail
**отстаёт от живой рассылки** — CFP ISCLS от 04-10 08:32 отсутствовал в архиве вечером
04-10; прямой почтовый ящик MG остаётся faster path, watch — подстраховка и регулярность.

## Процедура прогона

1. Скачать mbox текущего (и при смене месяца — предыдущего) `YYYY-Month.txt.gz`.
2. Прочитать watermark в [STATE.md](https://github.com/gasyoun/IndologyScholars/blob/main/indology_watch/STATE.md)
   (последний обработанный Message-ID + дата).
3. Триажировать ТОЛЬКО письма после watermark: CFP / дедлайн / конференция / симпозиум /
   семинар / fellowship в заголовке или теле; совпадения с watch-листом (ниже).
4. Обновить watermark в STATE.md; дописать строку в
   [LOG.md](https://github.com/gasyoun/IndologyScholars/blob/main/indology_watch/LOG.md):
   дата прогона, N новых, сигнал да/нет.
5. Сигнал есть → создать `indology_watch/YYYY-MM-DD-signal.md` (что, дедлайн, ссылка,
   предлагаемая правка поверхности) → закоммитить через worktree off `origin/main` + PR в
   gasyoun/IndologyScholars и вмержить (репо shared-contention: в основном дереве никаких
   pull/commit/push).
6. Сигнала нет → только локальные обновления STATE/LOG, без коммита.
7. Архив недоступен → строка об ошибке в LOG.md, завершение без ретраев.

## Watch-лист

- Площадки: ISCLS, WSC (World Sanskrit Conference), LREC, ACL, EACL, COLING, EMNLP,
  EURALEX, eLex, IJL, LaTeCH-CLfL, NLP4DH, DSH, JOHD, Brill RDJ.
- Темы: Sanskrit computational linguistics, lexicography (CDSL/DCS/MW), digital
  manuscripts, OCR индических письменностей, treebank, computational Pāṇini, Vedic corpora.

## Priors (не строить заново)

Харвест-механика и таксономия тем существуют в репо
[indology-archive-research-map](https://github.com/gasyoun/indology-archive-research-map);
ежедневный Ops-триаж переиспользует формат архива, но НЕ является частью той research-
pipeline. GTD-правки и минты из прогона запрещены — только сигнал-файл; решение всегда за
сессией/MG.

## Приватность

Архив публичный; имена авторов писем допустимы в логах/сигналах; никакой экстраполяции
личных данных за пределы содержимого листа.

_Гасунс_
