import re

with open("generate_publication_pages.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Inject Data Extraction python code
python_extraction_code = """
    # ===================== EXTENDED GALLERY PHASE 2 (VIS_020 – VIS_023) =====================

    conn_tmp = sqlite3.connect('conferences.db')
    conn_tmp.row_factory = sqlite3.Row
    cursor_tmp = conn_tmp.cursor()
    
    # VIS_020: Top Scholars Velocity
    cursor_tmp.execute('''
        SELECT p.display_name, e.year
        FROM person p
        JOIN presentation_person pp ON p.person_id = pp.person_id
        JOIN presentation pr ON pp.presentation_id = pr.presentation_id
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        ORDER BY e.year ASC
    ''')
    yearly_counts = defaultdict(lambda: defaultdict(int))
    for row in cursor_tmp.fetchall():
        yearly_counts[row['year']][row['display_name']] += 1
    
    all_time = defaultdict(int)
    for y, counts in yearly_counts.items():
        for name, c in counts.items():
            all_time[name] += c
    top5_names = [x[0] for x in sorted(all_time.items(), key=lambda x: x[1], reverse=True)[:5]]
    
    vis020_data = []
    running_totals = defaultdict(int)
    for y in sorted(yearly_counts.keys()):
        for name in top5_names:
            running_totals[name] += yearly_counts[y].get(name, 0)
        vis020_data.append({"year": y, "scores": {k: v for k, v in running_totals.items()}})
    serialized_vis020 = json.dumps({"names": top5_names, "timeline": vis020_data}, ensure_ascii=False)

    # VIS_021: Institutional Gravity
    cursor_tmp.execute('''
        SELECT affiliation_text_raw, COUNT(*) as c
        FROM presentation_person
        WHERE affiliation_text_raw IS NOT NULL AND affiliation_text_raw != ''
        GROUP BY affiliation_text_raw
    ''')
    inst_counts = defaultdict(int)
    for row in cursor_tmp.fetchall():
        n = normalize_affiliation(row['affiliation_text_raw'])
        if n:
            inst_counts[n] += row['c']
    vis021_data = [{"name": k, "val": v} for k, v in sorted(inst_counts.items(), key=lambda x: x[1], reverse=True)[:10]]
    serialized_vis021 = json.dumps(vis021_data, ensure_ascii=False)

    # VIS_022: Age at Presentation Trend
    cursor_tmp.execute('''
        SELECT p.birth_year, e.year 
        FROM person p
        JOIN presentation_person pp ON p.person_id = pp.person_id
        JOIN presentation pr ON pp.presentation_id = pr.presentation_id
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        WHERE p.birth_year IS NOT NULL AND p.birth_year > 1900
    ''')
    age_dist = defaultdict(list)
    for row in cursor_tmp.fetchall():
        age = row['year'] - row['birth_year']
        if 20 < age < 100:
            age_dist[row['year']].append(age)
    
    vis022_data = []
    for y, ages in age_dist.items():
        ages.sort()
        vis022_data.append({
            "year": y,
            "min": ages[0],
            "max": ages[-1],
            "median": ages[len(ages)//2]
        })
    vis022_data.sort(key=lambda x: x["year"])
    serialized_vis022 = json.dumps(vis022_data, ensure_ascii=False)

    # VIS_023: Scholar Returns (Loyalty)
    cursor_tmp.execute('''
        SELECT pp.person_id, COUNT(DISTINCT e.year) as c
        FROM presentation_person pp
        JOIN presentation pr ON pp.presentation_id = pr.presentation_id
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        GROUP BY pp.person_id
    ''')
    returns = defaultdict(int)
    for row in cursor_tmp.fetchall():
        returns[str(min(5, row['c']))] += 1
    vis023_data = [{"years": k, "count": v} for k, v in returns.items()]
    vis023_data.sort(key=lambda x: x["years"])
    serialized_vis023 = json.dumps(vis023_data, ensure_ascii=False)

    conn_tmp.close()

"""

content = content.replace("    tip_style = (", python_extraction_code + "\n    tip_style = (")

# 2. Inject TOC items
toc_html = """
            <a href="#VIS_020_velocity" class="viz-toc-item">
                <span>VIS_020</span>
                <b class="bilingual-text" data-ru="Активность топ-5 ученых" data-en="Top 5 Scholars Velocity">Активность топ-5 ученых</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_021_institutions" class="viz-toc-item">
                <span>VIS_021</span>
                <b class="bilingual-text" data-ru="Топ институций" data-en="Top Institutions">Топ институций</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_022_age_at_talk" class="viz-toc-item">
                <span>VIS_022</span>
                <b class="bilingual-text" data-ru="Возраст на момент доклада" data-en="Age at Presentation">Возраст на момент доклада</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_023_loyalty" class="viz-toc-item">
                <span>VIS_023</span>
                <b class="bilingual-text" data-ru="Лояльность (кол-во лет участия)" data-en="Loyalty (years participated)">Лояльность (кол-во лет участия)</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
"""

content = content.replace("        </section>\n\n        {findings_style}", toc_html + "        </section>\n\n        {findings_style}")

# 3. Inject HTML sections
sections_html = """
        <!-- VIS_020_velocity -->
        <section class="viz-showcase-section" id="VIS_020_velocity">
            <h2>
                <span class="viz-id-badge">VIS_020</span>
                <span class="bilingual-text" data-ru="Активность топ-5 ученых" data-en="Top 5 Scholars Velocity">Активность топ-5 ученых</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Кумулятивное число докладов пяти самых активных участников по годам." data-en="Cumulative presentations of the five most active scholars over time.">Кумулятивное число докладов пяти самых активных участников по годам.</p>
            <div id="vis020-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis020-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis020-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_021_institutions -->
        <section class="viz-showcase-section" id="VIS_021_institutions">
            <h2>
                <span class="viz-id-badge">VIS_021</span>
                <span class="bilingual-text" data-ru="Топ институций" data-en="Top Institutions">Топ институций</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Крупнейшие центры индологии по числу выступлений." data-en="Largest Indology centers by number of presentations.">Крупнейшие центры индологии по числу выступлений.</p>
            <div id="vis021-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis021-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis021-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_022_age_at_talk -->
        <section class="viz-showcase-section" id="VIS_022_age_at_talk">
            <h2>
                <span class="viz-id-badge">VIS_022</span>
                <span class="bilingual-text" data-ru="Возраст на момент доклада" data-en="Age at Presentation">Возраст на момент доклада</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Размах возраста исследователей в момент их выступления (мин, медиана, макс)." data-en="Age range of researchers at the time of their presentation (min, median, max).">Размах возраста исследователей в момент их выступления.</p>
            <div id="vis022-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis022-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis022-tooltip" style="{tip_style}"></div>
            </div>
        </section>
        
        <!-- VIS_023_loyalty -->
        <section class="viz-showcase-section" id="VIS_023_loyalty">
            <h2>
                <span class="viz-id-badge">VIS_023</span>
                <span class="bilingual-text" data-ru="Лояльность аудитории" data-en="Audience Loyalty">Лояльность аудитории</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Распределение числа уникальных лет участия." data-en="Distribution of unique years of participation.">Распределение числа уникальных лет участия.</p>
            <div id="vis023-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis023-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis023-tooltip" style="{tip_style}"></div>
            </div>
        </section>

"""

content = content.replace("        <!-- VIS_016_generations -->", sections_html + "\n        <!-- VIS_016_generations -->")

# 4. Inject Constants
constants_js = '            const VIS020_DATA = """ + serialized_vis020 + """;\n            const VIS021_DATA = """ + serialized_vis021 + """;\n            const VIS022_DATA = """ + serialized_vis022 + """;\n            const VIS023_DATA = """ + serialized_vis023 + """;\n'
content = content.replace("const ONLINE_DATA = \"\"\" + serialized_online + \"\"\";", "const ONLINE_DATA = \"\"\" + serialized_online + \"\"\";\n" + constants_js)


# 5. Inject JS Functions
js_functions = """

            function drawVIS020() {
                const svg = document.getElementById('vis020-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 50, l: 50};
                const D = VIS020_DATA; if (!D.timeline || !D.timeline.length) return;
                const years = D.timeline.map(d => d.year);
                const span = years[years.length - 1] - years[0] || 1;
                const xq = y => pad.l + (y - years[0]) / span * (W - pad.l - pad.r);
                const maxV = Math.max(...D.timeline.map(d => Math.max(...Object.values(d.scores))));
                const yq = v => H - pad.b - v / maxV * (H - pad.t - pad.b);
                
                for (let v = 0; v <= maxV; v += 5) { const yy = yq(v); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, v, 'end', 11)); }
                years.forEach(y => { if (y % 2 === 0 || y === years[0]) svg.appendChild(gText(xq(y), H - pad.b + 20, y, 'middle', 10)); });
                
                const cols = ['#ec4899', '#8b5cf6', '#3b82f6', '#10b981', '#f59e0b'];
                D.names.forEach((name, i) => {
                    const c = cols[i];
                    svg.appendChild(gEl('polyline', {points: D.timeline.map(d => xq(d.year) + ',' + yq(d.scores[name])).join(' '), fill: 'none', stroke: c, 'stroke-width': 2}));
                    const lastD = D.timeline[D.timeline.length - 1];
                    const t = gText(W - pad.r + 5, yq(lastD.scores[name]) + 4, name.split(' ')[0], 'start', 9, c); t.style.pointerEvents = 'none'; svg.appendChild(t);
                });
                
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
                svg.appendChild(gEl('line', {x1: pad.l, y1: pad.t, x2: pad.l, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
            }

            function drawVIS021() {
                const svg = document.getElementById('vis021-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 150, b: 30, l: 50};
                const D = VIS021_DATA; if (!D.length) return;
                const maxV = D[0].val;
                const barH = (H - pad.t - pad.b) / D.length * 0.7;
                const pitch = (H - pad.t - pad.b) / D.length;
                
                D.forEach((d, i) => {
                    const y = pad.t + i * pitch;
                    const w = (d.val / maxV) * (W - pad.l - pad.r);
                    const rect = gEl('rect', {x: pad.l, y: y, width: w, height: barH, fill: '#3b82f6', rx: 2});
                    bindTip(rect, 'vis021-wrapper', 'vis021-tooltip', () => '<strong>' + d.name + '</strong><br>' + d.val + ' ' + T('докладов', 'presentations'));
                    svg.appendChild(rect);
                    svg.appendChild(gText(pad.l + w + 10, y + barH/2 + 4, d.name + ' (' + d.val + ')', 'start', 11, 'var(--muted)'));
                });
            }

            function drawVIS022() {
                const svg = document.getElementById('vis022-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 50, l: 50};
                const D = VIS022_DATA; if (!D.length) return;
                const years = D.map(d => d.year);
                const span = years[years.length - 1] - years[0] || 1;
                const xq = y => pad.l + (y - years[0]) / span * (W - pad.l - pad.r);
                const yq = v => H - pad.b - v / 90 * (H - pad.t - pad.b);
                
                for (let v = 20; v <= 90; v += 10) { const yy = yq(v); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, v, 'end', 11)); }
                years.forEach(y => { if (y % 2 === 0 || y === years[0]) svg.appendChild(gText(xq(y), H - pad.b + 20, y, 'middle', 10)); });
                
                D.forEach(d => {
                    svg.appendChild(gEl('line', {x1: xq(d.year), y1: yq(d.min), x2: xq(d.year), y2: yq(d.max), stroke: 'rgba(16, 185, 129, 0.4)', 'stroke-width': 4}));
                    const c = gEl('circle', {cx: xq(d.year), cy: yq(d.median), r: 4, fill: '#10b981'});
                    bindTip(c, 'vis022-wrapper', 'vis022-tooltip', () => '<strong>' + d.year + '</strong><br>Min: ' + d.min + '<br>Median: ' + d.median + '<br>Max: ' + d.max);
                    svg.appendChild(c);
                });
                
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
                svg.appendChild(gEl('line', {x1: pad.l, y1: pad.t, x2: pad.l, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
            }

            function drawVIS023() {
                const svg = document.getElementById('vis023-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 50, l: 50};
                const D = VIS023_DATA; if (!D.length) return;
                const maxV = Math.max(...D.map(d => d.count));
                const yq = v => H - pad.b - v / maxV * (H - pad.t - pad.b);
                const pitch = (W - pad.l - pad.r) / D.length;
                
                for (let v = 0; v <= maxV; v += 50) { const yy = yq(v); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, v, 'end', 11)); }
                
                D.forEach((d, i) => {
                    const cx = pad.l + i * pitch + pitch / 2;
                    const w = pitch * 0.6;
                    const rect = gEl('rect', {x: cx - w/2, y: yq(d.count), width: w, height: H - pad.b - yq(d.count), fill: '#f59e0b', rx: 2});
                    bindTip(rect, 'vis023-wrapper', 'vis023-tooltip', () => '<strong>' + (d.years==='5'?'5+':d.years) + ' ' + T('лет участия', 'years') + '</strong><br>' + d.count + ' ' + T('ученых', 'scholars'));
                    svg.appendChild(rect);
                    svg.appendChild(gText(cx, H - pad.b + 20, (d.years==='5'?'5+':d.years), 'middle', 11, 'var(--muted)'));
                });
                
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
            }

"""

content = content.replace("            function drawGallery() {", js_functions + "\n            function drawGallery() {")

content = content.replace("drawVIS016, drawVIS018, drawVIS019];", "drawVIS016, drawVIS018, drawVIS019, drawVIS020, drawVIS021, drawVIS022, drawVIS023];")

with open("generate_publication_pages.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Injection complete!")
