# Editor profile — ВДИ «Вестник древней истории» (ИВИ РАН, Наука)
# Профиль редактора — Journal of Ancient History (Vestnik drevnei istorii)

> A **journal profile** loaded by Agent 6 (`agents/6-editor.md`). Same editor
> behaviour as in the other profiles; this file supplies the ВДИ house style.
>
> Журнальный профиль для Агента 6. Поведение редактора то же, что и в остальных
> профилях; этот файл задаёт издательский стиль ВДИ.

> ⚠️ **Verify before submission.** ВДИ — журнал Института всеобщей истории РАН
> (издаётся при поддержке «Наука»), Перечень ВАК. Обязательны актуальные
> «Правила оформления статей» на официальном сайте журнала. Этот профиль
> фиксирует устойчивые структурные факты; всё с пометкой **`[verify]`**
> проверять по руководству. Точка входа: страница журнала на сайте ИВИ РАН
> (`vdi.igh.ru` — **`[verify]`** актуальный URL).
>
> ⚠️ **Сверять перед подачей.** Профиль фиксирует то, что устойчиво известно
> о стиле ВДИ; точные требования — по официальным «Правилам».

---

## RU — Жёсткие требования (устойчивое + [verify])

### Профиль и язык
- **Язык** — русский (резюме и ключевые слова также на английском); другие
  языки — `[verify]`.
- Издатель / научный держатель — **Институт всеобщей истории РАН** (ИВИ РАН);
  типография «Наука» `[verify]`.
- Область — древняя история, классическая древность, древний Восток,
  археология, эпиграфика, нумизматика; рецензируемый.

### Объём
- Точного лимита знаков в публичной форме нет — `[verify]` (обычно
  исследовательская статья 30 000–60 000 знаков; сообщения и заметки короче).
- Сообщай фактический объём, не выдавай лимит за факт.

### Аннотация и ключевые слова
- Аннотация на русском и английском (`[verify]` точную длину); ключевые слова
  на русском и английском.

### Транслитерация и диакритика
- **Строгая научная транслитерация** для древних языков и письменностей:
  - санскрит/пали — IAST;
  - древнегреческий — общепринятая академическая;
  - аккадский — общепринятые системы (Borger / CDA — `[verify]`);
  - древнеперсидский, авестийский, хеттский — стандартные научные системы;
  - арабский, древнееврейский — традиции немецкой / международной классической
    индологии и семитологии (`[verify]` принятую в ВДИ).
- Диакритика сохраняется точно; не «выпрямлять» в ASCII.
- Греческие и иные нелатинские шрифты — Unicode (`[verify]` шрифтовые ограничения).

### Ссылочный аппарат
- В тексте — **внутритекстовая** ссылка автор-год с указанием страниц
  (тип `(Иванов 2005, 12)` или `(Иванов 2005: 12)` — `[verify]` точный знак
  разделителя по правилам).
- Содержательные примечания — постраничными сносками.
- В конце — список «Литература» (кириллическая основа) и обязательный
  латинский дубль **References** для индексирования (`[verify]` точную форму;
  по практике российских филологических/исторических журналов в Перечне ВАК
  он, как правило, требуется).

### «Литература» и References
- «Литература» — алфавитная; форма строки сходна с другими РАН-журналами
  (`*Автор И.О.* Заглавие. Город: Изд-во, Год.` для книги;
  `// Журнал. Год. Т. X, № Y. С. N–M.` для статьи). Точную пунктуацию
  и курсив — `[verify]` по «Правилам ВДИ».
- **References** — те же позиции латиницей: транслит кириллицы + перевод
  заглавия в квадратных скобках + пометка языка `(in Russian)` и т. п.

### Метаданные автора
- На русском и английском: ФИО полностью, ученая степень/звание, должность,
  место работы, рабочий адрес, e-mail, ORCID. УДК — `[verify]` (для журналов
  ВИ РАН обычно требуется; для ВДИ — сверить).

### Иллюстрации и таблицы
- Отдельными файлами с высоким разрешением (`[verify]` минимум; не ниже 300 dpi
  по общей практике); подписи отдельным файлом.

### Рецензирование
- Двойное слепое — `[verify]`; при двойном — обезличить (см. `editors/ppv.md`
  для тех же действий).

---

## RU — Что выдаёт редактор ВДИ (формат вывода)

```
Редактор (профиль ВДИ):
- Категория и объём: X знаков; лимит [verify]
- Аннотация RU/EN: X / Y знаков; ключевые слова RU/EN: n/m
- Транслитерация (системы по языкам): [нормализованные формы]; диакритика — строгая
- Ссылочный аппарат: внутритекстовые (Автор Год: с.); сноски постраничные
- Метаданные автора (RU/EN): ✅/❌ по полям
- Иллюстрации: ✅/⚠️ (минимум dpi — [verify])
- Обезличивание: ✅/⚠️ ([verify] модель рецензирования)
- Содержательные вопросы назад к агентам: [если есть]

Литература
[*Автор И.О.* … — по алфавиту]

References
[те же позиции латиницей; транслит + [перевод] + (in Russian) и т. п.]
```

---

## EN — Hard requirements (stable + [verify])

- **Language:** Russian main text; Russian + English abstract and keywords.
  Publisher / academic home: Institute of World History RAS (ИВИ РАН), Nauka
  printing house — `[verify]`. Peer-reviewed; in the ВАК list.
- **Length:** no published hard char cap — `[verify]`; usual length 30 000–60 000
  chars; communications / notes shorter.
- **Transliteration:** strict scholarly Latinisation per ancient language:
  IAST for Sanskrit/Pali; standard scholarly for Greek; Borger/CDA for Akkadian
  (`[verify]`); standard for Old Persian / Avestan / Hittite; consult `[verify]`
  for Arabic / Hebrew.
- **Citations:** **author-date in-text** `(Author Year: page)` (separator
  `[verify]`); discursive footnotes per page.
- **Bibliography:** Russian-script Литература (alphabetical) **and** Latin
  References (transliteration + bracketed translation + language tag), the
  duplicate required for indexing — `[verify]` exact form against the journal's
  Author Instructions.
- **Author metadata:** RU + EN with full name, degree/title, position,
  workplace, postal address, e-mail, ORCID. УДК — `[verify]`.
- **Illustrations:** separate high-resolution files; captions list (≥300 dpi
  by general practice; cap-specific — `[verify]`).
- **Review:** double-blind — `[verify]`; if double-blind, anonymise.

> To adapt to another journal, copy `editors/ppv.md` or this file to
> `editors/<journal>.md` and replace the house-style rules. The base editor
> agent and pipeline are unchanged.
