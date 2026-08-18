"""HTML/CSS/JS template for the retrospective page (imported by :mod:`page`).

Kept in its own module so ``page.py`` stays about data shaping. ``__PLACEHOLDER__``
tokens are substituted by :func:`page.render`; ``__DATA__`` receives the full JSON
payload. Palette = the data-viz reference instance, wired as CSS custom properties
so light/dark swap in one place and SVG marks recolor via ``.s1``…``.s8`` classes.
"""

TEMPLATE = r'''<!doctype html>
<html lang="ru" data-theme="">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>20 лет Обществу ревнителей санскрита: история гуглгруппы</title>
<meta name="description" content="История закрытой гуглгруппы nagari@googlegroups.com (2005–2026): __MSGS__ сообщений, __THREADS__ тредов, __MEMBERS__ участников. Хронология, сети, темы, санскрит и книгохранилище.">
<style>
:root{
  --plane:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,.10);
  --seq:#256abf; --accent:#2a78d6;
  --s1:#2a78d6; --s2:#1baf7a; --s3:#eda100; --s4:#008300;
  --s5:#4a3aa7; --s6:#e34948; --s7:#e87ba4; --s8:#eb6834; --sother:#898781;
}
@media (prefers-color-scheme:dark){:root{
  --plane:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,.10);
  --seq:#3987e5; --accent:#3987e5;
  --s1:#3987e5; --s2:#199e70; --s3:#c98500; --s4:#008300;
  --s5:#9085e9; --s6:#e66767; --s7:#d55181; --s8:#d95926; --sother:#898781;
}}
:root[data-theme=dark]{
  --plane:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,.10);
  --seq:#3987e5; --accent:#3987e5;
  --s1:#3987e5; --s2:#199e70; --s3:#c98500; --s4:#008300;
  --s5:#9085e9; --s6:#e66767; --s7:#d55181; --s8:#d95926; --sother:#898781;
}
:root[data-theme=light]{
  --plane:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,.10);
  --seq:#256abf; --accent:#2a78d6;
  --s1:#2a78d6; --s2:#1baf7a; --s3:#eda100; --s4:#008300;
  --s5:#4a3aa7; --s6:#e34948; --s7:#e87ba4; --s8:#eb6834; --sother:#898781;
}
*{box-sizing:border-box}
html,body{margin:0}
body{background:var(--plane);color:var(--ink);
  font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;line-height:1.6;
  font-size:17px;-webkit-font-smoothing:antialiased}
.wrap{max-width:1080px;margin:0 auto;padding:0 20px}
a{color:var(--accent)}
h1,h2,h3{line-height:1.2;font-weight:700}
h2{font-size:1.7rem;margin:0 0 4px;letter-spacing:-.01em}
.section{padding:40px 0;border-top:1px solid var(--border)}
.section > .wrap > p.lead{color:var(--ink2);max-width:70ch;margin:.2rem 0 1.4rem}
.kicker{text-transform:uppercase;letter-spacing:.14em;font-size:.72rem;font-weight:700;color:var(--muted)}
/* hero */
header.hero{background:
  radial-gradient(1200px 400px at 70% -10%, color-mix(in oklab,var(--accent) 16%,transparent), transparent 60%);
  padding:64px 0 40px}
.hero h1{font-size:clamp(2rem,5vw,3.3rem);margin:.3rem 0 .6rem;letter-spacing:-.02em}
.hero .sub{font-size:1.15rem;color:var(--ink2);max-width:64ch}
.hero .desc{margin-top:16px;padding:14px 16px;border:1px solid var(--border);border-radius:12px;
  background:var(--surface);color:var(--ink2);font-size:.95rem;max-width:74ch}
.prov{margin-top:14px;font-size:.82rem;color:var(--muted)}
/* stat tiles */
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:26px}
.tile{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:16px 18px}
.tile .v{font-size:1.9rem;font-weight:700;letter-spacing:-.02em}
.tile .l{font-size:.82rem;color:var(--ink2);margin-top:2px}
/* charts */
.card{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:18px 18px 12px;margin-top:16px}
.card h3{margin:0 0 2px;font-size:1.05rem}
.card .note{color:var(--muted);font-size:.82rem;margin:0 0 8px}
svg.chart{width:100%;height:auto;display:block;overflow:visible}
.grid line{stroke:var(--grid);stroke-width:1}
.axis line,.axis path{stroke:var(--axis)}
text{fill:var(--ink2);font-size:12px}
text.tick{fill:var(--muted);font-size:11px}
text.vlabel{fill:var(--ink);font-size:11px;font-weight:600}
.s1{fill:var(--s1);stroke:var(--s1)}.s2{fill:var(--s2);stroke:var(--s2)}
.s3{fill:var(--s3);stroke:var(--s3)}.s4{fill:var(--s4);stroke:var(--s4)}
.s5{fill:var(--s5);stroke:var(--s5)}.s6{fill:var(--s6);stroke:var(--s6)}
.s7{fill:var(--s7);stroke:var(--s7)}.s8{fill:var(--s8);stroke:var(--s8)}
.sother{fill:var(--sother);stroke:var(--sother)}
.legend{display:flex;flex-wrap:wrap;gap:6px 14px;margin:6px 0 2px;font-size:.85rem}
.legend button{border:0;background:none;color:var(--ink2);cursor:pointer;display:flex;align-items:center;gap:6px;padding:2px 4px;font:inherit;font-size:.85rem;border-radius:6px}
.legend button[aria-pressed=false]{opacity:.38}
.legend .sw{width:11px;height:11px;border-radius:3px}
.tbtn{float:right;font-size:.78rem;color:var(--accent);background:none;border:1px solid var(--border);
  border-radius:8px;padding:3px 9px;cursor:pointer}
table.data{width:100%;border-collapse:collapse;font-size:.86rem;margin-top:8px}
table.data th,table.data td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--border);vertical-align:top}
table.data td.n,table.data th.n{text-align:right;font-variant-numeric:tabular-nums}
.hidden{display:none}
/* tooltip */
#tip{position:fixed;pointer-events:none;z-index:50;background:var(--ink);color:var(--surface);
  padding:6px 9px;border-radius:8px;font-size:.8rem;line-height:1.35;opacity:0;transition:opacity .08s;
  max-width:260px;box-shadow:0 4px 14px rgba(0,0,0,.25)}
/* chips */
.chips{display:flex;flex-wrap:wrap;gap:7px;margin-top:8px}
.chip{border:1px solid var(--border);border-radius:999px;padding:4px 11px;font-size:.9rem;background:var(--surface)}
.chip b{font-variant-numeric:tabular-nums;color:var(--muted);font-weight:600;margin-left:5px}
.chip.deva{font-size:1.02rem}
/* two-col */
.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:760px){.cols{grid-template-columns:1fr}}
/* search */
#q{width:100%;padding:11px 14px;font:inherit;border:1px solid var(--border);border-radius:12px;
  background:var(--surface);color:var(--ink)}
#results{margin-top:10px;max-height:440px;overflow:auto;border:1px solid var(--border);border-radius:12px}
.row{display:grid;grid-template-columns:1fr auto;gap:10px;padding:9px 14px;border-bottom:1px solid var(--border)}
.row:last-child{border-bottom:0}
.row .t{font-weight:600}
.row .m{color:var(--muted);font-size:.82rem}
.row .meta{color:var(--ink2);font-size:.85rem;white-space:nowrap;font-variant-numeric:tabular-nums}
/* toolbar */
.toolbar{position:sticky;top:0;z-index:40;background:color-mix(in oklab,var(--plane) 88%,transparent);
  backdrop-filter:blur(8px);border-bottom:1px solid var(--border)}
.toolbar .wrap{display:flex;align-items:center;gap:16px;padding:10px 20px;font-size:.85rem}
.toolbar nav{display:flex;gap:14px;flex-wrap:wrap;color:var(--ink2)}
.toolbar nav a{color:var(--ink2);text-decoration:none}
.toolbar nav a:hover{color:var(--accent)}
.spacer{flex:1}
.themebtn{border:1px solid var(--border);background:var(--surface);color:var(--ink);border-radius:8px;
  padding:5px 10px;cursor:pointer;font:inherit;font-size:.82rem}
.guard{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:16px 18px;color:var(--ink2);font-size:.9rem}
.guard li{margin:4px 0}
footer{padding:30px 0 60px;color:var(--muted);font-size:.85rem}
.hl{background:color-mix(in oklab,var(--s3) 26%,transparent);border-radius:4px;padding:0 3px}
</style>
</head>
<body>
<div class="toolbar"><div class="wrap">
  <strong>नागरी · 2005–2026</strong>
  <nav>
    <a href="#hronologia">Хронология</a>
    <a href="#lyudi">Люди</a>
    <a href="#temy">Темы</a>
    <a href="#sushchnosti">Сущности</a>
    <a href="#seti">Сети</a>
    <a href="#knigi">Книгохранилище</a>
    <a href="#sanskrit">Санскрит</a>
    <a href="#poisk">Поиск</a>
  </nav>
  <span class="spacer"></span>
  <button class="themebtn" id="theme">◑ тема</button>
</div></div>

<header class="hero"><div class="wrap">
  <div class="kicker">История одной гуглгруппы · nagari@googlegroups.com</div>
  <h1>20 лет Обществу ревнителей санскрита</h1>
  <div class="sub">Закрытый академический список о санскрите и индологии живет с __FY__ года — уже __SPAN__ года и продолжается. Перед вами срез его переписки по состоянию на __LY__ год, который обновляется примерно раз в месяц: __MSGS__ сообщений в __THREADS__ тредах от __AUTHORS__ авторов, __MEMBERS__ участников и целое книгохранилище.</div>
  <div class="desc">__DESC__</div>
  <div class="prov">Источник: экспорт Google Takeout (<code>topics.mbox</code>). Данные разобраны воспроизводимым конвейером; имена и цитаты приводятся как в архиве. Порядок сообщений и треды восстановлены по заголовку <code>X-GM-THRID</code>.</div>

  <div class="tiles">
    <div class="tile"><div class="v">__SPAN__</div><div class="l">года истории — с __FY__ по сей день</div></div>
    <div class="tile"><div class="v">__MSGS__</div><div class="l">сообщений</div></div>
    <div class="tile"><div class="v">__THREADS__</div><div class="l">тредов (тем)</div></div>
    <div class="tile"><div class="v">__MEMBERS__</div><div class="l">участников</div></div>
    <div class="tile"><div class="v">__AUTHORS__</div><div class="l">писавших авторов</div></div>
    <div class="tile"><div class="v">__ATT__</div><div class="l">вложений · __ATTHUMAN__</div></div>
    <div class="tile"><div class="v">__BOOKS__</div><div class="l">книг и сканов (PDF/DjVu/…)</div></div>
    <div class="tile"><div class="v">__REPLIES__</div><div class="l">связей «ответ на…»</div></div>
  </div>
</div></header>

<section class="section" id="hronologia"><div class="wrap">
  <div class="kicker">Хронология</div>
  <h2>Как всё было</h2>
  <p class="lead">Группа основана в __FY__ году. Взрывной приток пришёлся на 2007-й (<b>+__JOIN2007__</b> участников за год), пик переписки — на <b>__PEAKY__</b> (__PEAKM__ сообщений). Дальше — интересный поворот: сообщений становится меньше, а тем всё больше (в 2025-м — __RECTHREADS__ тредов): длинные споры сменились множеством коротких вопросов-ответов.</p>

  <div class="card">
    <h3>Сообщения по годам</h3>
    <p class="note">Одна серия. Наведите курсор для точных значений; пик отмечен.</p>
    <div id="c_msgs"></div>
    <p class="note" id="n_partial"></p>
  </div>

  <div class="cols">
    <div class="card">
      <h3>Новые участники по годам</h3>
      <p class="note">Когда группа набирала людей.</p>
      <div id="c_newmem"></div>
    </div>
    <div class="card">
      <h3>Всего участников (накопительно)</h3>
      <p class="note">Совокупная аудитория списка.</p>
      <div id="c_cummem"></div>
    </div>
  </div>

  <div class="card">
    <h3>Тепловая карта активности</h3>
    <p class="note">Строка — год, столбец — месяц. Насыщеннее = больше сообщений. Видна и сезонность, и «горячие» годы.</p>
    <div id="c_heat"></div>
  </div>
</div></section>

<section class="section" id="lyudi"><div class="wrap">
  <div class="kicker">Люди</div>
  <h2>Кто держал разговор</h2>
  <p class="lead">Список вёл <b>__TOPA__</b> — __TOPAM__ сообщений и __TOPAS__ начатых тем за все годы. Но говорили многие. Ниже — 20 самых активных авторов. <b>Важно:</b> это счётчик сообщений, а не мера учёности; разные подписи и почтовые ники одного человека здесь не объединены.</p>
  <div class="card">
    <button class="tbtn" data-toggle="t_authors">таблица</button>
    <h3>Самые активные авторы</h3>
    <div id="c_authors"></div>
    <div id="t_authors" class="hidden"></div>
  </div>
</div></section>

<section class="section" id="temy"><div class="wrap">
  <div class="kicker">Темы</div>
  <h2>О чём говорили</h2>
  <p class="lead">Каждое сообщение размечено по двухуровневой рубрике — раздел и тема внутри него (сообщение может попадать в несколько тем). Больше всего — о <b>текстах</b> и их чтении, об <b>учебниках и грамматике</b>, о <b>книгах</b> и <b>словарях</b>; отдельная устойчивая линия — <b>шрифты и юникод</b> деванагари.</p>
  <div class="card">
    <button class="tbtn" data-toggle="t_topics">таблица</button>
    <h3>Темы по годам</h3>
    <p class="note">Нажмите на легенду, чтобы скрыть/показать линию. Некоторые цвета намеренно приглушены — точные числа в таблице и по наведению.</p>
    <div class="legend" id="l_topics"></div>
    <div id="c_topics"></div>
    <div id="t_topics" class="hidden"></div>
  </div>

  <div class="card">
    <h3>Разделы и темы внутри них</h3>
    <p class="note">Столбец — раздел (сумма всех тем внутри). Нажмите на раздел, чтобы раскрыть темы внутри.</p>
    <div id="c_parents"></div>
    <div id="c_children"></div>
  </div>

  <div class="cols">
    <div class="card">
      <h3>Какие темы обсуждаются вместе</h3>
      <p class="note">Пары тем, чаще всего встречающиеся в одном треде (без учёта «разное»/шаблонных пар).</p>
      <div id="t_cooc"></div>
    </div>
    <div class="card">
      <h3>Устойчивые словосочетания</h3>
      <p class="note">Вместо частот отдельных слов — многословные коллокации (PMI/логарифм правдоподобия) и TF-IDF термины.</p>
      <div class="chips" id="ch_phrases"></div>
    </div>
  </div>
</div></section>

<section class="section" id="sushchnosti"><div class="wrap">
  <div class="kicker">Сущности</div>
  <h2>О чём и о ком именно</h2>
  <p class="lead">Помимо тем — какие конкретно тексты, учёные, словари и инструменты упоминались в переписке (сопоставление по эталонным спискам названий, с алиасами на русском/IAST/латинице). Ниже — самые частые сущности по типу и как менялась их упоминаемость по годам.</p>
  <div id="c_entity_types"></div>
  <div class="card">
    <h3>Темы × сущности</h3>
    <p class="note">Насколько плотно каждая тема связана с каждой сущностью — насыщеннее ячейка, чаще совместное упоминание.</p>
    <div id="c_topic_entity"></div>
  </div>
  <div class="card">
    <h3>Упоминаемость по годам</h3>
    <p class="note">12 самых частых сущностей.</p>
    <div id="c_entity_trends"></div>
  </div>
  <div id="c_quotes"></div>
</div></section>

<section class="section" id="seti"><div class="wrap">
  <div class="kicker">Сети</div>
  <h2>Кто кому отвечал</h2>
  <p class="lead">Из заголовков <code>In-Reply-To</code> восстановлено __REPLIES__ связей «ответ на сообщение». Ниже — ядро сети ответов между 26 самыми активными авторами: толще линия — больше ответов, крупнее точка — больше сообщений. <b>Связь ответа — это разговор, а не влияние.</b> Наведите на имя, чтобы подсветить его собеседников.</p>
  <div class="card">
    <h3>Ядро сети ответов</h3>
    <div id="c_net"></div>
  </div>
</div></section>

<section class="section" id="knigi"><div class="wrap">
  <div class="kicker">Книгохранилище</div>
  <h2>Что читали и чем делились</h2>
  <p class="lead">Группа была ещё и библиотекой: __NPDF__ PDF и всего __BOOKS__ книг, сканов и документов (__ATTHUMAN__ вложений всех типов). Здесь — Кнауэр и Бюлер, Шанкара-бхашьи, упанишады, грамматики.</p>
  <div class="card">
    <h3>Книги и сканы по годам</h3>
    <p class="note">Файлы книжных форматов (PDF, DjVu, DOC…) крупнее 50 КБ.</p>
    <div id="c_books"></div>
  </div>
  <div class="card">
    <button class="tbtn" data-toggle="t_att">все типы</button>
    <h3>Заметные файлы</h3>
    <div id="t_books"></div>
    <div id="t_att" class="hidden"></div>
  </div>
</div></section>

<section class="section" id="sanskrit"><div class="wrap">
  <div class="kicker">Санскрит в переписке</div>
  <h2>Язык внутри писем</h2>
  <p class="lead">В телах писем — живой санскрит: деванагари и латинская транслитерация (IAST). Показательно, что среди латинских терминов лидируют слова <i>аппарата толкования</i> — <i>anvaya, pratipadārtha, padavibhāga, tātparya</i>: это метод традиционного разбора шлоки, которым и занимались читательские треды. Отдельная тема — __NFONT__ обсуждений шрифтов и юникода.</p>
  <div class="cols">
    <div class="card"><h3>Деванагари — частые формы</h3><div class="chips" id="ch_deva"></div></div>
    <div class="card"><h3>IAST — частые термины</h3><div class="chips" id="ch_iast"></div></div>
  </div>
  <div class="card">
    <h3>Легендарные треды</h3>
    <p class="note">Самые длинные обсуждения за 20 лет. Среди них — «Бхагавад Гита — подсудное дело» (2011), эхо реального судебного процесса.</p>
    <div id="t_notable"></div>
  </div>
</div></section>

<section class="section" id="poisk"><div class="wrap">
  <div class="kicker">Поиск</div>
  <h2>Найти тред</h2>
  <p class="lead">Поиск по темам всех __THREADS__ тредов (по названию и автору). Полнотекстовый поиск по телам писем — в базе SQLite и в Markdown-зеркале архива.</p>
  <input id="q" placeholder="напр.: словарь, Бюлер, гита, шрифт, Карицкий…" autocomplete="off">
  <div id="results"></div>
</div></section>

<section class="section"><div class="wrap">
  <div class="kicker">Как это устроено</div>
  <h2>Данные и оговорки</h2>
  <div class="guard">
    <ul>
      <li><b>Источник.</b> Экспорт Google Takeout закрытой группы <code>nagari@googlegroups.com</code>: __MSGS__ сообщений (2005–2026), разобранных из <code>topics.mbox</code> воспроизводимым конвейером (mbox → SQLite + FTS5 → таблицы → эта страница).</li>
      <li><b>Треды</b> восстановлены по <code>X-GM-THRID</code>; связи ответов — по <code>In-Reply-To</code>. Связь ответа — это разговор, а не влияние; совместное участие в теме — не соавторство.</li>
      <li><b>Счётчик сообщений — не мера учёности.</b> Активность автора отражает роль в переписке, а не вклад в науку.</li>
      <li><b>Имена не объединены.</b> Один человек мог писать под разными подписями и почтовыми никами; они здесь не слиты в одну личность.</li>
      <li id="cav_partial" hidden></li>
      <li><b>Приватность.</b> Это была закрытая группа. Все адреса электронной почты со страницы удалены — проверено скриптом <code>audit_publish_surface.py</code> (0 адресов на странице). Публикация имён и цитат — решение владельца списка; полнотекстовый архив писем и файлы-вложения не опубликованы.</li>
    </ul>
  </div>
  <footer>
    Автоматически сгенерировано конвейером <code>nagari_group_archive</code> · модель Opus 4.8 (<code>claude-opus-4-8</code>). Палитра и правила графиков — по методике data-viz. Страница самодостаточна (без внешних ресурсов).
  </footer>
</div></section>

<div id="tip" role="status" aria-live="polite"></div>

<script>
const DATA = __DATA__;
const $ = s => document.querySelector(s);
const NS = "http://www.w3.org/2000/svg";
const fmt = n => (n==null?"":String(n).replace(/\B(?=(\d{3})+(?!\d))/g," "));
function el(t,a){const e=document.createElementNS(NS,t);for(const k in (a||{}))e.setAttribute(k,a[k]);return e;}
function add(p,t,a){const e=el(t,a);p.appendChild(e);return e;}
function txt(p,x,y,s,cls){const e=add(p,"text",{x,y});if(cls)e.setAttribute("class",cls);e.textContent=s;return e;}
const tip=$("#tip");
function showTip(html,ev){tip.innerHTML=html;tip.style.opacity=1;moveTip(ev);}
function moveTip(ev){let x=ev.clientX+14,y=ev.clientY+14;if(x+270>innerWidth)x=ev.clientX-tip.offsetWidth-14;tip.style.left=x+"px";tip.style.top=y+"px";}
function hideTip(){tip.style.opacity=0;}
function hoverable(e,html){e.style.cursor="crosshair";e.addEventListener("mousemove",ev=>showTip(html,ev));e.addEventListener("mouseleave",hideTip);}

// ---- partial final year: the mbox ends mid-year, so the last by-year point is
// incomplete. Mark it everywhere so a short final bar is not misread as a crash.
const PARTIAL = (DATA.meta && DATA.meta.partial) || null;
function isPartial(y){return !!(PARTIAL && y===PARTIAL.year);}
function pnote(y){return isPartial(y)?`<br><i>неполный год · только до ${PARTIAL.cutoff_ru}</i>`:"";}
function partialGuide(F,x){
  if(!PARTIAL)return;
  add(F.svg,"line",{x1:x,y1:F.m.t,x2:x,y2:F.H-F.m.b,stroke:"var(--muted)","stroke-width":1,"stroke-dasharray":"3 3","stroke-opacity":.7});
  const t=txt(F.svg,x,F.m.t+11,"неполный",null);
  t.setAttribute("text-anchor","middle");t.setAttribute("fill","var(--muted)");t.setAttribute("font-size","10");
}

// ---- base plot frame ----
function frame(mount,W,H,m){
  const svg=el("svg",{viewBox:`0 0 ${W} ${H}`,class:"chart",role:"img"});
  mount.appendChild(svg);
  return {svg,W,H,m,iw:W-m.l-m.r,ih:H-m.t-m.b};
}
function yGrid(F,ymax,ticks){
  const g=add(F.svg,"g",{class:"grid"});
  const ax=add(F.svg,"g",{class:"axis"});
  for(let i=0;i<=ticks;i++){
    const v=ymax*i/ticks, y=F.m.t+F.ih-(v/ymax)*F.ih;
    add(g,"line",{x1:F.m.l,y1:y,x2:F.m.l+F.iw,y2:y});
    txt(F.svg,F.m.l-8,y+4,fmt(Math.round(v)),"tick").setAttribute("text-anchor","end");
  }
}

// ---- single-series area/line over years ----
function areaYears(mountId,rows,valKey,{peak}={}){
  const mount=$(mountId);mount.innerHTML="";
  const W=1000,H=340,m={l:52,r:16,t:16,b:34};
  const F=frame(mount,W,H,m);
  const xs=rows.map(r=>r.year), ymax=Math.max(...rows.map(r=>r[valKey]))*1.08||1;
  const X=y=>m.l+((y-xs[0])/(xs[xs.length-1]-xs[0]))*F.iw;
  const Y=v=>m.t+F.ih-(v/ymax)*F.ih;
  yGrid(F,ymax,4);
  let d="M"+X(xs[0])+","+Y(0);
  rows.forEach(r=>d+="L"+X(r.year)+","+Y(r[valKey]));
  d+="L"+X(xs[xs.length-1])+","+Y(0)+"Z";
  const area=add(F.svg,"path",{d,class:"s1"});area.setAttribute("fill-opacity",".16");area.setAttribute("stroke","none");
  let dl="M"+X(rows[0].year)+","+Y(rows[0][valKey]);
  rows.forEach((r,i)=>{if(i)dl+="L"+X(r.year)+","+Y(r[valKey]);});
  add(F.svg,"path",{d:dl,class:"s1",fill:"none","stroke-width":2});
  rows.forEach(r=>{
    const cx=X(r.year),cy=Y(r[valKey]);
    if(isPartial(r.year))partialGuide(F,cx);
    const dot=add(F.svg,"circle",{cx,cy,r:8,fill:"transparent"});
    hoverable(dot,`<b>${r.year}</b><br>${fmt(r[valKey])}${pnote(r.year)}`);
    if(isPartial(r.year)){
      const pm=add(F.svg,"circle",{cx,cy,r:5,class:"s1"});pm.setAttribute("fill","var(--surface)");pm.setAttribute("stroke-width","2");
    }
    if(peak&&r.year===peak.year){
      add(F.svg,"circle",{cx,cy,r:4,class:"s1"}).setAttribute("stroke","var(--surface)");
      txt(F.svg,cx,cy-12,`пик · ${fmt(r[valKey])}`,"vlabel").setAttribute("text-anchor","middle");
    }
  });
  xs.forEach((y,i)=>{if(i%2===0||i===xs.length-1)txt(F.svg,X(y),H-14,y,"tick").setAttribute("text-anchor","middle");});
}

// ---- vertical bars over years ----
function barsYears(mountId,rows,valKey){
  const mount=$(mountId);mount.innerHTML="";
  const W=1000,H=300,m={l:52,r:16,t:14,b:34};
  const F=frame(mount,W,H,m);
  const ymax=Math.max(...rows.map(r=>r[valKey]))*1.08||1;
  const bw=F.iw/rows.length*0.72;
  yGrid(F,ymax,4);
  rows.forEach((r,i)=>{
    const x=m.l+(i+0.5)*(F.iw/rows.length), h=(r[valKey]/ymax)*F.ih, y=m.t+F.ih-h;
    const b=add(F.svg,"rect",{x:x-bw/2,y,width:bw,height:Math.max(h,0.5),rx:3,class:"s1"});
    if(isPartial(r.year)){b.setAttribute("fill","var(--surface)");b.setAttribute("stroke-width","1.5");b.setAttribute("stroke-dasharray","4 2");}
    hoverable(b,`<b>${r.year}</b><br>${fmt(r[valKey])}${pnote(r.year)}`);
    if(i%2===0||i===rows.length-1)txt(F.svg,x,H-14,r.year,"tick").setAttribute("text-anchor","middle");
  });
}
function lineYears(mountId,rows,valKey){
  const mount=$(mountId);mount.innerHTML="";
  const W=1000,H=300,m={l:56,r:16,t:14,b:34};
  const F=frame(mount,W,H,m);
  const xs=rows.map(r=>r.year), ymax=Math.max(...rows.map(r=>r[valKey]))*1.08||1;
  const X=y=>m.l+((y-xs[0])/(xs[xs.length-1]-xs[0]))*F.iw, Y=v=>m.t+F.ih-(v/ymax)*F.ih;
  yGrid(F,ymax,4);
  let dl="";rows.forEach((r,i)=>dl+=(i?"L":"M")+X(r.year)+","+Y(r[valKey]));
  add(F.svg,"path",{d:dl,class:"s2",fill:"none","stroke-width":2});
  rows.forEach(r=>{const cx=X(r.year),cy=Y(r[valKey]);
    const dot=add(F.svg,"circle",{cx,cy,r:7,fill:"transparent"});hoverable(dot,`<b>${r.year}</b><br>${fmt(r[valKey])} всего${pnote(r.year)}`);
    if(isPartial(r.year)){const pm=add(F.svg,"circle",{cx,cy,r:5,class:"s2"});pm.setAttribute("fill","var(--surface)");pm.setAttribute("stroke-width","2");}});
  xs.forEach((y,i)=>{if(i%2===0||i===xs.length-1)txt(F.svg,X(y),H-14,y,"tick").setAttribute("text-anchor","middle");});
}

// ---- horizontal bars (authors) ----
function hbars(mountId,items,{label,value}){
  const mount=$(mountId);mount.innerHTML="";
  const n=items.length,rowh=26,W=1000,m={l:220,r:60,t:6,b:6},H=m.t+m.b+n*rowh;
  const F=frame(mount,W,H,m);
  const vmax=Math.max(...items.map(value))||1;
  items.forEach((it,i)=>{
    const y=m.t+i*rowh, w=(value(it)/vmax)*F.iw;
    txt(F.svg,m.l-10,y+rowh/2+4,label(it),"vlabel").setAttribute("text-anchor","end");
    const b=add(F.svg,"rect",{x:m.l,y:y+4,width:Math.max(w,1),height:rowh-9,rx:4,class:"s1"});
    hoverable(b,`<b>${label(it)}</b><br>${fmt(value(it))} сообщений`);
    txt(F.svg,m.l+w+8,y+rowh/2+4,fmt(value(it)),"tick");
  });
}

// ---- heatmap year x month ----
function heatmap(mountId,heat){
  const mount=$(mountId);mount.innerHTML="";
  const years=Object.keys(heat).map(Number).sort((a,b)=>a-b);
  const MON=["Я","Ф","М","А","М","И","И","А","С","О","Н","Д"];
  const cell=26,gap=3,m={l:52,t:24,r:10,b:8};
  const W=m.l+m.r+12*(cell+gap),H=m.t+m.b+years.length*(cell+gap);
  const F=frame(mount,W,H,m);
  let vmax=1;years.forEach(y=>heat[y].forEach(v=>vmax=Math.max(vmax,v)));
  MON.forEach((mo,j)=>txt(F.svg,m.l+j*(cell+gap)+cell/2,18,mo,"tick").setAttribute("text-anchor","middle"));
  years.forEach((y,i)=>{
    txt(F.svg,m.l-8,m.t+i*(cell+gap)+cell/2+4,y,"tick").setAttribute("text-anchor","end");
    heat[y].forEach((v,j)=>{
      const x=m.l+j*(cell+gap),yy=m.t+i*(cell+gap);
      const t=v/vmax, op=v?0.12+0.88*Math.sqrt(t):0;
      const c=add(F.svg,"rect",{x,y:yy,width:cell,height:cell,rx:5,fill:"var(--seq)","fill-opacity":op});
      c.setAttribute("stroke","var(--border)");
      hoverable(c,`<b>${y}, мес. ${j+1}</b><br>${fmt(v)} сообщ.`);
    });
  });
}

// ---- multi-line topics ----
const SERCLS=["s1","s2","s3","s4","s5","s6","s7","s8","sother"];
function topicLines(){
  const years=DATA.activity.map(r=>r.year);
  const ser=DATA.topic_series;
  const mount=$("#c_topics");mount.innerHTML="";
  const W=1000,H=380,m={l:52,r:16,t:12,b:34};
  const F=frame(mount,W,H,m);
  let ymax=1;ser.forEach(s=>s.values.forEach(v=>ymax=Math.max(ymax,v)));ymax*=1.08;
  const X=i=>m.l+(i/(years.length-1))*F.iw, Y=v=>m.t+F.ih-(v/ymax)*F.ih;
  yGrid(F,ymax,4);
  years.forEach((y,i)=>{if(isPartial(y))partialGuide(F,X(i));});
  years.forEach((y,i)=>{if(i%2===0||i===years.length-1)txt(F.svg,X(i),H-14,y,"tick").setAttribute("text-anchor","middle");});
  const paths={};
  ser.forEach((s,si)=>{
    let d="";s.values.forEach((v,i)=>d+=(i?"L":"M")+X(i)+","+Y(v));
    const p=add(F.svg,"path",{d,class:SERCLS[si],fill:"none","stroke-width":2,"data-tag":s.tag});
    p.setAttribute("stroke-opacity",".9");paths[s.tag]=p;
    s.values.forEach((v,i)=>{const dot=add(F.svg,"circle",{cx:X(i),cy:Y(v),r:6,fill:"transparent","data-tag":s.tag});
      hoverable(dot,`<b>${s.tag}</b> · ${years[i]}<br>${fmt(v)} сообщ.${pnote(years[i])}`);});
  });
  // legend with toggles
  const L=$("#l_topics");L.innerHTML="";
  ser.forEach((s,si)=>{
    const b=document.createElement("button");b.setAttribute("aria-pressed","true");
    b.innerHTML=`<span class="sw" style="background:var(--${SERCLS[si]==='sother'?'sother':'s'+(si+1)})"></span>${s.tag} <b style="color:var(--muted);font-variant-numeric:tabular-nums">${fmt(DATA.topic_total[s.tag]||0)}</b>`;
    b.onclick=()=>{const on=b.getAttribute("aria-pressed")==="true";b.setAttribute("aria-pressed",!on);
      mount.querySelectorAll(`[data-tag="${CSS.escape(s.tag)}"]`).forEach(e=>e.style.display=on?"none":"");};
    L.appendChild(b);
  });
  // table view
  let th="<table class=data><thead><tr><th>Год</th>"+ser.map(s=>`<th class=n>${s.tag}</th>`).join("")+"</tr></thead><tbody>";
  years.forEach((y,i)=>{th+=`<tr><td>${y}</td>`+ser.map(s=>`<td class=n>${fmt(s.values[i])}</td>`).join("")+"</tr>";});
  $("#t_topics").innerHTML=th+"</tbody></table>";
}

// ---- reply network (circular) ----
function network(){
  const mount=$("#c_net");mount.innerHTML="";
  const nodes=DATA.nodes,edges=DATA.edges;
  const W=1000,H=620,cx=W/2,cy=H/2,R=Math.min(W,H)/2-140;
  const F=frame(mount,W,H,{l:0,r:0,t:0,b:0});
  const N=nodes.length;
  const pos={},mmax=Math.max(...nodes.map(n=>n.msgs));
  nodes.forEach((n,i)=>{const a=-Math.PI/2+i/N*2*Math.PI;pos[n.id]={x:cx+R*Math.cos(a),y:cy+R*Math.sin(a),a};});
  const wmax=Math.max(...edges.map(e=>e.w),1);
  const eg=add(F.svg,"g",{});
  edges.forEach(e=>{
    const a=pos[e.s],b=pos[e.d];if(!a||!b)return;
    const mx=(a.x+b.x)/2,my=(a.y+b.y)/2, k=0.35, qx=cx+(mx-cx)*k, qy=cy+(my-cy)*k;
    const p=add(eg,"path",{d:`M${a.x},${a.y}Q${qx},${qy} ${b.x},${b.y}`,fill:"none",
      stroke:"var(--ink2)","stroke-opacity":0.10+0.5*(e.w/wmax),"stroke-width":0.6+3*(e.w/wmax),
      "data-s":e.s,"data-d":e.d});
  });
  nodes.forEach(n=>{
    const p=pos[n.id],r=4+9*Math.sqrt(n.msgs/mmax);
    const c=add(F.svg,"circle",{cx:p.x,cy:p.y,r,class:"s1"});c.setAttribute("stroke","var(--surface)");c.setAttribute("stroke-width",1.5);
    const right=Math.cos(p.a)>=0;
    const t=txt(F.svg,p.x+(right?1:-1)*(r+6),p.y+4,n.name.length>22?n.name.slice(0,21)+"…":n.name,"tick");
    t.setAttribute("text-anchor",right?"start":"end");
    const hi=()=>{eg.querySelectorAll("path").forEach(pt=>{
        const on=pt.getAttribute("data-s")===String(n.id)||pt.getAttribute("data-d")===String(n.id);
        pt.setAttribute("stroke",on?"var(--accent)":"var(--ink2)");
        pt.style.opacity=on?1:0.12;});};
    const un=()=>{eg.querySelectorAll("path").forEach(pt=>{pt.setAttribute("stroke","var(--ink2)");pt.style.opacity=1;});};
    [c,t].forEach(x=>{x.style.cursor="pointer";
      x.addEventListener("mouseenter",ev=>{hi();showTip(`<b>${n.name}</b><br>${fmt(n.msgs)} сообщений`,ev);});
      x.addEventListener("mousemove",moveTip);
      x.addEventListener("mouseleave",()=>{un();hideTip();});});
  });
}

// ---- books by year ----
function booksChart(){
  const rows=DATA.books_by_year.map(r=>({year:r.year,count:r.count}));
  if(!rows.length){$("#c_books").textContent="—";return;}
  barsYears("#c_books",rows,"count");
}

// ---- chips ----
function chips(mountId,items){
  const m=$(mountId);m.innerHTML="";const cls=mountId.includes("deva")?"chip deva":"chip";
  items.forEach(it=>{const c=document.createElement("span");c.className=cls;c.innerHTML=`${it.t}<b>${fmt(it.c)}</b>`;m.appendChild(c);});
}

// ---- H1518 Step 7: parent/child topic drill-down ----
function parentBars(){
  const mount=$("#c_parents");mount.innerHTML="";
  const items=DATA.parent_totals;
  hbars("#c_parents",items,{label:p=>p.parent,value:p=>p.count});
  mount.querySelectorAll("rect.s1").forEach((rect,i)=>{
    rect.style.cursor="pointer";
    rect.addEventListener("click",()=>childBars(items[i].parent));
  });
  if(items.length)childBars(items[0].parent);
}
function childBars(parent){
  const kids=DATA.parent_children[parent]||[];
  const mount=$("#c_children");mount.innerHTML=`<p class="note" style="margin:0 0 6px">${parent} — темы внутри раздела</p><div id="c_children_inner"></div>`;
  hbars("#c_children_inner",kids,{label:k=>k.tag,value:k=>k.count});
}

// ---- topic co-occurrence (table, no bodies) ----
function coocTable(){
  let h="<table class=data><thead><tr><th>Тема A</th><th>Тема B</th><th class=n>Тредов вместе</th></tr></thead><tbody>";
  DATA.cooc.forEach(e=>h+=`<tr><td>${e.a}</td><td>${e.b}</td><td class=n>${fmt(e.n)}</td></tr>`);
  $("#t_cooc").innerHTML=h+"</tbody></table>";
}

// ---- phrase cloud (multi-word collocations, not single-word frequency) ----
function phraseCloud(){
  const m=$("#ch_phrases");m.innerHTML="";
  const items=DATA.phrases_llr.slice(0,40).map(p=>({t:p,c:0})).concat(
    DATA.phrases_tfidf.slice(0,15).map(p=>({t:p,c:0})));
  items.forEach(it=>{const c=document.createElement("span");c.className="chip";c.textContent=it.t;m.appendChild(c);});
}

// ---- entity types: one horizontal-bar card per type ----
function entityTypeCards(){
  const mount=$("#c_entity_types");mount.innerHTML="";
  DATA.entity_types.forEach((et,ti)=>{
    const card=document.createElement("div");card.className="card";
    const id=`c_ent_${ti}`;
    card.innerHTML=`<h3>${et.label}</h3><p class="note">${et.items.length} из категории, самые частые ниже.</p><div id="${id}"></div>`;
    mount.appendChild(card);
    hbars(`#${id}`,et.items,{label:e=>e.name,value:e=>e.count});
  });
}

// ---- topic x entity heatmap (categorical, reuses the year x month palette) ----
function topicEntityHeatmap(){
  const mount=$("#c_topic_entity");mount.innerHTML="";
  const M=DATA.topic_entity_matrix, topics=M.topics, ents=M.entities;
  if(!topics.length||!ents.length){mount.textContent="—";return;}
  const cell=26,gap=3,m={l:150,t:90,r:10,b:8};
  const W=m.l+m.r+ents.length*(cell+gap),H=m.t+m.b+topics.length*(cell+gap);
  const F=frame(mount,W,H,m);
  let vmax=1;M.cells.forEach(row=>row.forEach(v=>vmax=Math.max(vmax,v)));
  ents.forEach((e,j)=>{
    const t=txt(F.svg,m.l+j*(cell+gap)+cell/2,m.t-8,e.length>18?e.slice(0,17)+"…":e,"tick");
    t.setAttribute("text-anchor","start");t.setAttribute("transform",`rotate(-40 ${m.l+j*(cell+gap)+cell/2} ${m.t-8})`);
  });
  topics.forEach((tpc,i)=>{
    txt(F.svg,m.l-8,m.t+i*(cell+gap)+cell/2+4,tpc,"tick").setAttribute("text-anchor","end");
    M.cells[i].forEach((v,j)=>{
      const x=m.l+j*(cell+gap),y=m.t+i*(cell+gap);
      const t=v/vmax, op=v?0.12+0.88*Math.sqrt(t):0;
      const c=add(F.svg,"rect",{x,y,width:cell,height:cell,rx:5,fill:"var(--seq)","fill-opacity":op});
      c.setAttribute("stroke","var(--border)");
      hoverable(c,`<b>${tpc}</b> × <b>${ents[j]}</b><br>${fmt(v)} упом.`);
    });
  });
}

// ---- entity trend lines (top entities, count per year) ----
function entityTrendLines(){
  const mount=$("#c_entity_trends");mount.innerHTML="";
  const series=DATA.entity_trends;
  if(!series.length){mount.textContent="—";return;}
  const years=DATA.activity.map(r=>r.year);
  const W=1000,H=380,m={l:52,r:16,t:12,b:34};
  const F=frame(mount,W,H,m);
  let ymax=1;series.forEach(s=>s.series.forEach(p=>ymax=Math.max(ymax,p.count)));ymax*=1.08;
  const X=i=>m.l+(i/(years.length-1))*F.iw, Y=v=>m.t+F.ih-(v/ymax)*F.ih;
  yGrid(F,ymax,4);
  years.forEach((y,i)=>{if(i%2===0||i===years.length-1)txt(F.svg,X(i),H-14,y,"tick").setAttribute("text-anchor","middle");});
  const byYear=Object.fromEntries(years.map((y,i)=>[y,i]));
  series.forEach((s,si)=>{
    let d="";s.series.forEach((p,i)=>{const xi=byYear[p.year];if(xi==null)return;d+=(i?"L":"M")+X(xi)+","+Y(p.count);});
    const cls=SERCLS[si%SERCLS.length];
    const p=add(F.svg,"path",{d,class:cls,fill:"none","stroke-width":2,"stroke-opacity":.85});
    s.series.forEach(pt=>{const xi=byYear[pt.year];if(xi==null)return;
      const dot=add(F.svg,"circle",{cx:X(xi),cy:Y(pt.count),r:5,fill:"transparent"});
      hoverable(dot,`<b>${s.entity}</b> · ${pt.year}<br>${fmt(pt.count)} упом.`);});
  });
  const L=document.createElement("div");L.className="legend";
  series.forEach((s,si)=>{L.innerHTML+=`<span><span class="sw" style="display:inline-block;background:var(--${SERCLS[si%SERCLS.length]})"></span> ${s.entity}</span>`;});
  mount.parentElement.insertBefore(L,mount);
}

// ---- quote surface: wired but disabled (Wave-2 human gate, H1518) ----
function quoteBlock(){
  if(!DATA.show_quotes){return;}
  // Intentionally never reached in Wave 1 -- enabling this is a human
  // @DECIDE after /publish-safety-check, not something this generator does.
}

// ---- tables ----
function authorsTable(){
  let h="<table class=data><thead><tr><th>Автор</th><th class=n>Сообщ.</th><th class=n>Начал тем</th><th>Годы</th></tr></thead><tbody>";
  DATA.top_authors.forEach(a=>h+=`<tr><td>${a.name}</td><td class=n>${fmt(a.msgs)}</td><td class=n>${fmt(a.started)}</td><td>${a.first}–${a.last}</td></tr>`);
  $("#t_authors").innerHTML=h+"</tbody></table>";
  hbars("#c_authors",DATA.top_authors,{label:a=>a.name,value:a=>a.msgs});
}
function notableTable(){
  let h="<table class=data><thead><tr><th>Тема</th><th class=n>Год</th><th class=n>Сообщ.</th><th class=n>Авторов</th></tr></thead><tbody>";
  DATA.notable.forEach(t=>{const gita=/подсудное|суд/i.test(t.subject);
    h+=`<tr><td>${gita?'<span class=hl>':''}<a href="${t.url}" target=_blank rel=noopener>${t.subject}</a>${gita?'</span>':''}</td><td class=n>${t.year}</td><td class=n>${fmt(t.n)}</td><td class=n>${fmt(t.a)}</td></tr>`;});
  $("#t_notable").innerHTML=h+"</tbody></table>";
}
function booksTable(){
  let h="<table class=data><thead><tr><th>Файл</th><th class=n>Год</th><th class=n>МБ</th><th>Поделился</th></tr></thead><tbody>";
  DATA.book_top.forEach(b=>h+=`<tr><td><a href="${b.url}" target=_blank rel=noopener>${b.f||"—"}</a> <span class=m>.${b.ext}</span></td><td class=n>${b.y}</td><td class=n>${b.mb}</td><td>${b.by||""}</td></tr>`);
  $("#t_books").innerHTML=h+"</tbody></table>";
  let a="<table class=data><thead><tr><th>Тип</th><th class=n>Файлов</th><th class=n>Объём</th></tr></thead><tbody>";
  DATA.attachments_by_type.forEach(r=>a+=`<tr><td>.${r.ext}</td><td class=n>${fmt(r.count)}</td><td class=n>${(r.total_bytes/1048576).toFixed(1)} МБ</td></tr>`);
  $("#t_att").innerHTML=a+"</tbody></table>";
}

// ---- search ----
function search(){
  const q=$("#q"),res=$("#results"),T=DATA.threads;
  function run(){
    const s=q.value.trim().toLowerCase();
    let rows=T;
    if(s){const parts=s.split(/\s+/);rows=T.filter(r=>{const hay=(r[0]+" "+r[1]).toLowerCase();return parts.every(p=>hay.includes(p));});}
    rows=rows.slice().sort((a,b)=>b[3]-a[3]).slice(0,200);
    res.innerHTML=rows.map(r=>`<div class=row><div><div class=t><a href="${r[5]}" target=_blank rel=noopener>${esc(r[0])}</a></div><div class=m>${esc(r[1])} · ${r[2]||"?"}</div></div><div class=meta>${r[3]} сообщ.<br>${r[4]} авт.</div></div>`).join("")||"<div class=row><div class=m>Ничего не найдено</div></div>";
  }
  const esc=x=>(x||"").replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
  q.addEventListener("input",run);run();
}

// ---- toggles + theme ----
document.querySelectorAll(".tbtn").forEach(b=>b.onclick=()=>{
  const t=$("#"+b.dataset.toggle);t.classList.toggle("hidden");
  b.textContent=t.classList.contains("hidden")?(b.dataset.toggle==="t_att"?"все типы":"таблица"):"график";
});
$("#theme").onclick=()=>{const r=document.documentElement;
  const cur=r.getAttribute("data-theme")||(matchMedia("(prefers-color-scheme:dark)").matches?"dark":"light");
  r.setAttribute("data-theme",cur==="dark"?"light":"dark");};

// ---- render all ----
areaYears("#c_msgs",DATA.activity,"messages",{peak:DATA.peak});
barsYears("#c_newmem",DATA.activity,"new_members");
lineYears("#c_cummem",DATA.membership,"cum");
heatmap("#c_heat",DATA.heat);
authorsTable();
topicLines();
network();
booksChart();
booksTable();
chips("#ch_deva",DATA.deva);
chips("#ch_iast",DATA.iast);
notableTable();
search();
parentBars();
coocTable();
phraseCloud();
entityTypeCards();
topicEntityHeatmap();
entityTrendLines();
quoteBlock();

// ---- partial-year disclosure (filled only when the data ends mid-year) ----
if(PARTIAL){
  const n=$("#n_partial");
  if(n)n.innerHTML=`<b>${PARTIAL.year}</b> — неполный год: данные только до ${PARTIAL.cutoff_ru} (≈${PARTIAL.coverage_pct}% года), поэтому последний столбец ниже полных лет. В пересчёте на полный год — примерно ${fmt(PARTIAL.annualized_msgs)} сообщений.`;
  const cav=$("#cav_partial");
  if(cav){cav.hidden=false;cav.innerHTML=`<b>Последний год неполный.</b> Экспорт обрывается на ${PARTIAL.cutoff_ru} (≈${PARTIAL.coverage_pct}% ${PARTIAL.year} года), так что ${PARTIAL.year}-й во всех графиках «по годам» показан частично и помечен пунктиром; годовые итоги за ${PARTIAL.year} сравнивать с полными годами напрямую нельзя.`;}
}
</script>
</body>
</html>'''
