# Editor profiles · Профили редакторов

> Agent 6 (`../agents/6-editor.md`) defines **editor behaviour**; a profile in this
> folder defines **one journal's house style**. Different journals → different editor
> roles. Pick the profile that matches your target venue.
>
> Агент 6 задаёт **поведение редактора**; профиль в этой папке задаёт **издательский
> стиль одного журнала**. Разные журналы → разные роли редактора. Выбирайте профиль под
> целевое издание.

## Available profiles · Доступные профили

| Profile · Профиль | Journal · Журнал | Status |
|---|---|---|
| `ppv.md` | ППВ «Письменные памятники Востока» (ИВР РАН) · *Written Monuments of the Orient* | ✅ ready · готов |
| `iij.md` | *Indo-Iranian Journal* (Brill, Leiden) | ✅ ready; house-style specifics marked **[verify]** · готов; специфика стиля помечена **[verify]** |
| `vdi.md` | ВДИ «Вестник древней истории» (ИВИ РАН, Наука) · *Journal of Ancient History* | 🟡 starter profile; specifics marked **[verify]** against ВДИ Author Instructions · стартовый профиль |
| `vya.md` | ВЯ «Вопросы языкознания» (ИЯз РАН) · *Voprosy Jazykoznanija* | 🟡 starter profile; specifics marked **[verify]** · стартовый профиль |
| `jaos.md` | *Journal of the American Oriental Society* (AOS) | 🟡 starter profile; specifics marked **[verify]** against the JAOS Style Sheet · стартовый профиль |
| `olz.md` | *Orientalistische Literaturzeitung* (De Gruyter, Berlin) | 🟡 starter profile; review-journal-focused; specifics marked **[verify]** · стартовый профиль; рецензионный журнал |

## How to add a journal · Как добавить журнал

1. Copy `ppv.md` to `editors/<journal>.md`. · Скопируйте `ppv.md` в `editors/<journal>.md`.
2. Replace the house-style rules (length limits, citation format, References rules,
   metadata, illustrations, language). · Замените правила стиля.
3. Add a row to the table above. · Добавьте строку в таблицу.

The base editor agent and the rest of the pipeline stay unchanged — only the profile
swaps. · Базовый агент-редактор и остальной конвейер не меняются — меняется только профиль.

## How a profile is used · Как используется профиль

When driving the pipeline, tell the model which profile to load, e.g.:
> "Editor: use the ППВ profile (`editors/ppv.md`)."

При прогоне укажите модели, какой профиль брать, например:
> «Редактор: профиль ППВ (`editors/ppv.md`)».

If no profile is named, the editor falls back to the generic scholarly style in
`../agents/6-editor.md` and says so. · Если профиль не указан, редактор работает в общем
научном стиле из `../agents/6-editor.md` и сообщает об этом.
