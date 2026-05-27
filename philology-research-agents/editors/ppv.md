# Editor profile — ППВ «Письменные памятники Востока» (ИВР РАН)
# Профиль редактора — ППВ (Written Monuments of the Orient, IOM RAS)

> A **journal profile** loaded by Agent 6 (`agents/6-editor.md`). It supplies the
> concrete house style; the base editor agent supplies the behaviour. Different journals
> → different profiles in this folder. This is the **ППВ editor role**.
>
> **Журнальный профиль**, который подгружает Агент 6. Он задаёт конкретный издательский
> стиль; базовый агент-редактор задаёт поведение. Разные журналы → разные профили в этой
> папке. Это **роль редактора ППВ**.

Source of rules · Источник правил:
[Авторам (ru)](https://ppv.orientalstudies.ru/ru/avtoram) ·
[Authors (en)](https://ppv.orientalstudies.ru/en/authors) ·
[Порядок рецензирования](https://ppv.orientalstudies.ru/ru/poryadok-retsenzirovaniya) ·
[Publication Ethics](https://ppv.orientalstudies.ru/en/publication-ethics).
Профиль откалиброван по реальной подаче в этом репозитории
(`article/ppv_submission_article.md`, `article/ppv_submission_checklist.md`).

---

## RU — Жёсткие требования (проверяй и отмечай статусом ✅/⚠️/❌)

### Объём и категория подачи
- **Статья (исследование): ≤ 40 000 знаков** (1 а.л.) с пробелами, сносками и
  библиографией.
- **«Материалы» (публикации/переводы): ≤ 80 000 знаков** (2 а.л.).
- Всегда сообщай фактический объём в знаках и указывай, в какую категорию текст
  укладывается. Это первый блокер ППВ.

### Аннотация и ключевые слова
- Аннотация **RU ≤ 1000–1200 знаков** и **EN ≤ 1000–1200 знаков**.
- Ключевые слова **≤ 10**, отдельно RU и EN.

### Внутритекстовые ссылки
- Только формат **`(Автор Год: с.)`**, например `(Елизаренкова 1989: 12)`;
  для нескольких страниц `(Автор Год: 12–14)`, для нескольких работ через `;`.
- Никаких нумерованных `[1]`, `[2]` в тексте.
- Содержательные примечания — **постраничными сносками**.

### «Литература» (кириллический/основной список)
- Алфавитный, с ключом **`Автор Год – `**, затем полное описание.
- Имя автора — **курсивом** (в markdown это `*Автор И.О.*`).
- Книга: `*Автор И.О.* Заглавие. Город: Изд-во, Год.`
- Статья: `*Автор И.О.* Заглавие // Журнал. Год. Т. X, № Y. С. 1–26.`
- Сборник под ред.: `*Ред.И.О.* (ред.). Заглавие. Город: Изд-во, Год.`
- Первоисточники-издания включай по тому же ключу (по редактору/издателю).

### **References** (латинский дубль — ОБЯЗАТЕЛЕН)
- Те же позиции, **без** ключа `Автор Год –`, в том же алфавитном порядке.
- Кириллицу **транслитерировать**; заглавие — транслит + **перевод в `[ ]`**.
- Заглавие книги/название журнала — курсивом; для нелатинских источников в конце
  пометка языка: `(In Russian)`, `(In Italian)` и т. п.
- Пример строки для русской работы:
  `Elizarenkova, Tatyana Ya. Rigveda. Mandaly I–IV [The Rigveda. Maṇḍalas I–IV].
  Moscow: Nauka, 1989. (In Russian)`

### Метаданные автора (RU + EN)
ФИО полностью · ученая степень и звание (или «без степени, независимый исследователь») ·
должность · место работы · **рабочий адрес с почтовым индексом** · e-mail · ORCID.
УДК — необязателен (можно оставить, безвреден).

### Иллюстрации
Отдельные файлы **TIFF/JPEG/PSD/EPS ≥ 300 dpi** + отдельный список подписей.

### Рецензирование
Двойное слепое: для подачи **обезличить** текст (убрать самоидентификацию автора,
формулировки «мы провели… [я, автор]» с прямой отсылкой на себя).

### Язык
Основной текст — **русский**; EN-аннотация и EN-ключевые слова обязательны;
**References** — латиницей.

---

## RU — Что выдаёт редактор ППВ (формат вывода)

```
Редактор (профиль ППВ):
- Категория и объём: [статья/материалы]; X знаков → ✅/❌ против лимита
- Аннотация RU/EN: X / Y знаков → ✅/⚠️; ключевые слова RU/EN: n/m → ✅/⚠️
- Ссылочный аппарат: внутритекстовые (Автор Год: с.) → ✅/❌; сноски → ✅
- Метаданные автора (RU/EN): ✅/❌ по полям
- Иллюстрации: ✅/⚠️
- Обезличивание под слепое рецензирование: ✅/⚠️
- Нормализация транслитерации (IAST и др.): [исправленные формы]
- Содержательные вопросы назад к агентам: [если есть; новых утверждений не ввожу]

Литература
[Автор Год – *Автор И.О.* … — по алфавиту]

References
[те же позиции латиницей, транслит + [перевод], (In Russian) и т. п.]
```

---

## EN — Hard requirements (check and mark ✅/⚠️/❌)

- **Length:** research article ≤ 40,000 chars (incl. spaces, footnotes, bibliography);
  "Materials" ≤ 80,000 chars. Always report the actual character count.
- **Abstract:** RU ≤ 1000–1200 and EN ≤ 1000–1200 chars; keywords ≤ 10 each (RU + EN).
- **In-text citations:** only `(Author Year: p.)`, e.g. `(Elizarenkova 1989: 12)`; no
  numbered `[1]`. Substantive notes as per-page footnotes.
- **«Литература»:** alphabetical, key `Author Year – `, author name in *italics*; book
  `*Author.* Title. City: Press, Year.`; article `*Author.* Title // Journal. Year.
  Vol. X, no. Y. P. 1–26.`
- **References (mandatory Latin duplicate):** same entries without the key,
  transliterate Cyrillic, title = transliteration + `[translation]`, italic
  book/journal title, append `(In Russian)` etc.
- **Author metadata (RU + EN):** full name, degree/title, position, workplace, work
  address with postal code, e-mail, ORCID. УДК optional.
- **Illustrations:** separate TIFF/JPEG/PSD/EPS ≥ 300 dpi + caption list.
- **Double-blind review:** anonymize self-identification.
- **Language:** Russian main text; EN abstract + keywords required; References in Latin.

> To adapt to another journal, copy this file to `editors/<journal>.md` and replace the
> house-style rules. The base editor agent and the rest of the pipeline are unchanged.
> Для другого журнала: скопируйте файл в `editors/<journal>.md` и замените правила стиля.
