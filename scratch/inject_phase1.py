import re

with open("generate_publication_pages.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Inject Data Extraction python code
python_extraction_code = """
    # ===================== EXTENDED GALLERY PHASE 1 (VIS_016 – VIS_020) =====================

    # VIS_016: Generational Eras (Смена поколений)
    vis016_eras = defaultdict(lambda: defaultdict(int))
        
    conn_tmp = sqlite3.connect('conferences.db')
    conn_tmp.row_factory = sqlite3.Row
    cursor_tmp = conn_tmp.cursor()
    
    cursor_tmp.execute('''
        SELECT p.birth_year, e.year 
        FROM person p
        JOIN presentation_person pp ON p.person_id = pp.person_id
        JOIN presentation pr ON pp.presentation_id = pr.presentation_id
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        WHERE p.birth_year IS NOT NULL
    ''')
    for row in cursor_tmp.fetchall():
        decade = (row['birth_year'] // 10) * 10
        vis016_eras[row['year']][decade] += 1
        
    vis016_data = []
    for y in sorted(vis016_eras.keys()):
        vis016_data.append({"year": y, "decades": dict(vis016_eras[y])})
    serialized_vis016 = json.dumps(vis016_data, ensure_ascii=False)

    # VIS_018: Title Length Dynamics
    cursor_tmp.execute('''
        SELECT pr.title, e.year 
        FROM presentation pr
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
    ''')
    lengths = defaultdict(list)
    for row in cursor_tmp.fetchall():
        if row['title']:
            lengths[row['year']].append(len(row['title'].split()))
    vis018_data = [{"year": k, "avg": sum(v)/len(v)} for k, v in lengths.items()]
    vis018_data.sort(key=lambda x: x["year"])
    serialized_vis018 = json.dumps(vis018_data, ensure_ascii=False)

    # VIS_019: Co-authorship Rate
    cursor_tmp.execute('''
        SELECT pp.presentation_id, e.year, COUNT(pp.person_id) as c
        FROM presentation_person pp
        JOIN presentation pr ON pp.presentation_id = pr.presentation_id
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        GROUP BY pp.presentation_id, e.year
    ''')
    coauth = defaultdict(lambda: {"total": 0, "multi": 0})
    for row in cursor_tmp.fetchall():
        y = row['year']
        coauth[y]["total"] += 1
        if row['c'] > 1:
            coauth[y]["multi"] += 1
    vis019_data = [{"year": k, "pct": (v["multi"]/v["total"])*100} for k, v in coauth.items()]
    vis019_data.sort(key=lambda x: x["year"])
    serialized_vis019 = json.dumps(vis019_data, ensure_ascii=False)

    conn_tmp.close()

"""

content = content.replace("    tip_style = (", python_extraction_code + "\n    tip_style = (")

# 2. Inject TOC items
toc_html = """
            <a href="#VIS_016_generations" class="viz-toc-item">
                <span>VIS_016</span>
                <b class="bilingual-text" data-ru="Смена поколений (по декадам рождения)" data-en="Generational Eras (by birth decade)">Смена поколений (по декадам рождения)</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_018_title_length" class="viz-toc-item">
                <span>VIS_018</span>
                <b class="bilingual-text" data-ru="Динамика длины названий докладов" data-en="Title Length Dynamics">Динамика длины названий докладов</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_019_coauthorship" class="viz-toc-item">
                <span>VIS_019</span>
                <b class="bilingual-text" data-ru="Индекс соавторства" data-en="Co-authorship Index">Индекс соавторства</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
"""

content = content.replace("        </section>\n\n        {findings_style}", toc_html + "        </section>\n\n        {findings_style}")

# 3. Inject HTML sections
sections_html = """
        <!-- VIS_016_generations -->
        <section class="viz-showcase-section" id="VIS_016_generations">
            <h2>
                <span class="viz-id-badge">VIS_016</span>
                <span class="bilingual-text" data-ru="Смена поколений" data-en="Generational Eras">Смена поколений</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Распределение докладов по десятилетиям рождения авторов." data-en="Distribution of presentations by authors' birth decades.">Распределение докладов по десятилетиям рождения авторов.</p>
            <div id="vis016-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis016-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis016-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_018_title_length -->
        <section class="viz-showcase-section" id="VIS_018_title_length">
            <h2>
                <span class="viz-id-badge">VIS_018</span>
                <span class="bilingual-text" data-ru="Сложность названий" data-en="Title Complexity">Сложность названий</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Среднее количество слов в названиях докладов по годам." data-en="Average word count in presentation titles by year.">Среднее количество слов в названиях докладов по годам.</p>
            <div id="vis018-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis018-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis018-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_019_coauthorship -->
        <section class="viz-showcase-section" id="VIS_019_coauthorship">
            <h2>
                <span class="viz-id-badge">VIS_019</span>
                <span class="bilingual-text" data-ru="Индекс соавторства" data-en="Co-authorship Index">Индекс соавторства</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Процент докладов, написанных в соавторстве." data-en="Percentage of co-authored presentations over time.">Процент докладов, написанных в соавторстве.</p>
            <div id="vis019-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis019-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis019-tooltip" style="{tip_style}"></div>
            </div>
        </section>

"""

content = content.replace("        </section>\n\n    \"\"\"", "        </section>\n\n" + sections_html + "    \"\"\"")

# 4. Inject Constants
constants_js = '            const VIS016_DATA = """ + serialized_vis016 + """;\n            const VIS018_DATA = """ + serialized_vis018 + """;\n            const VIS019_DATA = """ + serialized_vis019 + """;\n'
content = content.replace("const ONLINE_DATA = \"\"\" + serialized_online + \"\"\";", "const ONLINE_DATA = \"\"\" + serialized_online + \"\"\";\n" + constants_js)


# 5. Inject JS Functions
js_functions = """

            function drawVIS016() {
                const svg = document.getElementById('vis016-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 50, l: 50};
                const D = VIS016_DATA; if (!D.length) return;
                const years = D.map(d => d.year);
                const span = years[years.length - 1] - years[0] || 1;
                const xq = y => pad.l + (y - years[0]) / span * (W - pad.l - pad.r);
                years.forEach(y => { if (y % 2 === 0 || y === years[0]) svg.appendChild(gText(xq(y), H - pad.b + 20, y, 'middle', 10)); });
                
                // Stacked logic for decades
                let allDecades = new Set();
                D.forEach(d => Object.keys(d.decades).forEach(k => allDecades.add(parseInt(k))));
                const decades = Array.from(allDecades).sort((a,b)=>a-b);
                const maxTot = Math.max(...D.map(d => Object.values(d.decades).reduce((a,b)=>a+b, 0))) || 1;
                const yq = v => H - pad.b - v / maxTot * (H - pad.t - pad.b);
                
                for (let f = 0; f <= 1.0001; f += 0.25) { const v = maxTot * f, yy = yq(v); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, Math.round(v), 'end', 11)); }
                
                const cols = ['#0f172a', '#1e293b', '#334155', '#475569', '#64748b', '#94a3b8', '#cbd5e1', '#e2e8f0', '#f1f5f9', '#f8fafc'];
                const lower = D.map(() => 0);
                decades.forEach((dk, ki) => {
                    let up = [], down = [];
                    D.forEach((d, i) => { const v = d.decades[dk] || 0; const topv = lower[i] + v; up.push(xq(d.year) + ',' + yq(topv)); lower[i] = topv; });
                    for (let i = D.length - 1; i >= 0; i--) down.push(xq(D[i].year) + ',' + yq(lower[i] - (D[i].decades[dk]||0)));
                    const poly = gEl('polygon', {points: up.concat(down).join(' '), fill: cols[ki%cols.length], 'fill-opacity': 0.8, stroke: 'none'});
                    bindTip(poly, 'vis016-wrapper', 'vis016-tooltip', () => '<strong>' + T('Поколение', 'Generation') + ' ' + dk + 's</strong>');
                    svg.appendChild(poly);
                });
                
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
                svg.appendChild(gEl('line', {x1: pad.l, y1: pad.t, x2: pad.l, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
            }

            function drawVIS018() {
                const svg = document.getElementById('vis018-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 50, l: 50};
                const D = VIS018_DATA; if (!D.length) return;
                const years = D.map(d => d.year);
                const span = years[years.length - 1] - years[0] || 1;
                const xq = y => pad.l + (y - years[0]) / span * (W - pad.l - pad.r);
                const maxV = Math.max(...D.map(d => d.avg)) + 2;
                const yq = v => H - pad.b - v / maxV * (H - pad.t - pad.b);
                
                for (let v = 0; v <= maxV; v += 2) { const yy = yq(v); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, v, 'end', 11)); }
                years.forEach(y => { if (y % 2 === 0 || y === years[0]) svg.appendChild(gText(xq(y), H - pad.b + 20, y, 'middle', 10)); });
                
                svg.appendChild(gEl('polyline', {points: D.map(d => xq(d.year) + ',' + yq(d.avg)).join(' '), fill: 'none', stroke: '#10b981', 'stroke-width': 3}));
                D.forEach(d => { const c = gEl('circle', {cx: xq(d.year), cy: yq(d.avg), r: 4, fill: '#10b981'});
                    bindTip(c, 'vis018-wrapper', 'vis018-tooltip', () => '<strong>' + d.year + '</strong><br>' + T('Слов в названии', 'Words per title') + ': ' + d.avg.toFixed(1));
                    svg.appendChild(c); });
                
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
                svg.appendChild(gEl('line', {x1: pad.l, y1: pad.t, x2: pad.l, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
            }

            function drawVIS019() {
                const svg = document.getElementById('vis019-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 50, l: 50};
                const D = VIS019_DATA; if (!D.length) return;
                const years = D.map(d => d.year);
                const span = years[years.length - 1] - years[0] || 1;
                const xq = y => pad.l + (y - years[0]) / span * (W - pad.l - pad.r);
                const maxV = Math.max(20, Math.max(...D.map(d => d.pct)) + 5);
                const yq = v => H - pad.b - v / maxV * (H - pad.t - pad.b);
                
                for (let v = 0; v <= maxV; v += 5) { const yy = yq(v); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, v + '%', 'end', 11)); }
                years.forEach(y => { if (y % 2 === 0 || y === years[0]) svg.appendChild(gText(xq(y), H - pad.b + 20, y, 'middle', 10)); });
                
                svg.appendChild(gEl('polyline', {points: D.map(d => xq(d.year) + ',' + yq(d.pct)).join(' '), fill: 'none', stroke: '#f59e0b', 'stroke-width': 3}));
                D.forEach(d => { const c = gEl('circle', {cx: xq(d.year), cy: yq(d.pct), r: 4, fill: '#f59e0b'});
                    bindTip(c, 'vis019-wrapper', 'vis019-tooltip', () => '<strong>' + d.year + '</strong><br>' + T('Соавторство', 'Co-authorship') + ': ' + d.pct.toFixed(1) + '%');
                    svg.appendChild(c); });
                
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
                svg.appendChild(gEl('line', {x1: pad.l, y1: pad.t, x2: pad.l, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
            }

"""

content = content.replace("            function drawGallery() {", js_functions + "\n            function drawGallery() {")

content = content.replace("const fns = [drawDemography, drawSurvival, drawNewcomer, drawTreemap, drawGumilyov, drawKeywordDiv, drawClosedness, drawOnline];", "const fns = [drawDemography, drawSurvival, drawNewcomer, drawTreemap, drawGumilyov, drawKeywordDiv, drawClosedness, drawOnline, drawVIS016, drawVIS018, drawVIS019];")

with open("generate_publication_pages.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Injection complete!")
