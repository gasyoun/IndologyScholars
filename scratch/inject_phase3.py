import re
import json

with open("generate_publication_pages.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Inject Data Extraction python code
python_extraction_code = """
    # ===================== EXTENDED GALLERY PHASE 3 (VIS_024 – VIS_030) =====================

    conn_tmp = sqlite3.connect('conferences.db')
    conn_tmp.row_factory = sqlite3.Row
    cursor_tmp = conn_tmp.cursor()
    
    # VIS_024: Top Keywords by Year (Simplified to overall top keywords for a bubble chart)
    cursor_tmp.execute('''
        SELECT raw_title, year FROM presentation pr
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
    ''')
    import re as regex
    words = defaultdict(int)
    for row in cursor_tmp.fetchall():
        if row['raw_title']:
            clean = regex.sub(r'[^а-яА-ЯёЁ]', ' ', row['raw_title'].lower())
            for w in clean.split():
                if len(w) > 4:
                    words[w] += 1
    top_words = [{"text": k, "val": v} for k, v in sorted(words.items(), key=lambda x: x[1], reverse=True)[:30]]
    serialized_vis024 = json.dumps(top_words, ensure_ascii=False)

    # VIS_025: Conference Scale
    cursor_tmp.execute('''
        SELECT e.year, COUNT(DISTINCT s.session_id) as sess, COUNT(pr.presentation_id) as pres
        FROM event e
        JOIN event_day ed ON e.event_id = ed.event_id
        JOIN event_day_venue edv ON ed.event_day_id = edv.event_day_id
        JOIN session s ON edv.event_day_venue_id = s.event_day_venue_id
        JOIN presentation pr ON s.session_id = pr.session_id
        GROUP BY e.year
        ORDER BY e.year ASC
    ''')
    vis025_data = [dict(row) for row in cursor_tmp.fetchall()]
    serialized_vis025 = json.dumps(vis025_data, ensure_ascii=False)

    # Read DeepSeek classification for VIS_026, VIS_027, VIS_028
    ds_data = list(load_csv_rows("analytics_output/expanded_classification_deepseek.csv"))

    # VIS_026: DeepSeek Confidence
    confidences = defaultdict(int)
    for row in ds_data:
        c = row.get("confidence", "")
        if c: confidences[c] += 1
    vis026_data = [{"conf": k, "val": v} for k, v in confidences.items()]
    serialized_vis026 = json.dumps(vis026_data, ensure_ascii=False)

    # VIS_027: Theme Co-occurrence (Proxy via L1 themes counts)
    l1_counts = defaultdict(int)
    for row in ds_data:
        l1 = row.get("theme_l1", "")
        if l1: l1_counts[l1] += 1
    vis027_data = [{"theme": k, "val": v} for k, v in sorted(l1_counts.items(), key=lambda x: x[1], reverse=True)[:10]]
    serialized_vis027 = json.dumps(vis027_data, ensure_ascii=False)

    # VIS_028: Gumilyov vs Period
    gp_matrix = defaultdict(lambda: defaultdict(int))
    for row in ds_data:
        g = row.get("gumilyov_level", "")
        p = row.get("period_l2", "")
        if g and p: gp_matrix[g][p] += 1
    vis028_data = []
    for g, p_dict in gp_matrix.items():
        vis028_data.append({"gumilyov": g, "periods": dict(p_dict)})
    serialized_vis028 = json.dumps(vis028_data, ensure_ascii=False)

    # VIS_029: Title Character Length
    cursor_tmp.execute('''
        SELECT e.year, LENGTH(pr.raw_title) as l
        FROM presentation pr
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        WHERE pr.raw_title IS NOT NULL
    ''')
    chars = defaultdict(list)
    for row in cursor_tmp.fetchall():
        chars[row['year']].append(row['l'])
    vis029_data = [{"year": k, "avg": sum(v)/len(v)} for k, v in chars.items()]
    vis029_data.sort(key=lambda x: x["year"])
    serialized_vis029 = json.dumps(vis029_data, ensure_ascii=False)

    # VIS_030: Series Overlap
    cursor_tmp.execute('''
        SELECT pp.person_id, es.series_name_en
        FROM presentation_person pp
        JOIN presentation pr ON pp.presentation_id = pr.presentation_id
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        JOIN event_series es ON e.event_series_id = es.event_series_id
    ''')
    pers_series = defaultdict(set)
    for row in cursor_tmp.fetchall():
        pers_series[row['person_id']].add(row['series_name_en'])
    
    venn = {"zograf_only": 0, "roerich_only": 0, "both": 0}
    for s in pers_series.values():
        is_z = any('Zograf' in x for x in s)
        is_r = any('Roerich' in x for x in s)
        if is_z and is_r: venn["both"] += 1
        elif is_z: venn["zograf_only"] += 1
        elif is_r: venn["roerich_only"] += 1
    serialized_vis030 = json.dumps(venn, ensure_ascii=False)

    conn_tmp.close()

"""

content = content.replace("    tip_style = (", python_extraction_code + "\n    tip_style = (")

# 2. Inject TOC items
toc_html = """
            <a href="#VIS_024_keywords" class="viz-toc-item">
                <span>VIS_024</span>
                <b class="bilingual-text" data-ru="Облако терминов" data-en="Keyword Cloud">Облако терминов</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_025_scale" class="viz-toc-item">
                <span>VIS_025</span>
                <b class="bilingual-text" data-ru="Масштаб конференций" data-en="Conference Scale">Масштаб конференций</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_026_confidence" class="viz-toc-item">
                <span>VIS_026</span>
                <b class="bilingual-text" data-ru="Уверенность ИИ-разметки" data-en="AI Annotation Confidence">Уверенность ИИ-разметки</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_027_l1_themes" class="viz-toc-item">
                <span>VIS_027</span>
                <b class="bilingual-text" data-ru="Популярность макро-тем" data-en="Macro-theme Popularity">Популярность макро-тем</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_028_gumilyov" class="viz-toc-item">
                <span>VIS_028</span>
                <b class="bilingual-text" data-ru="Пассионарность Гумилева" data-en="Gumilyov Passionarity">Пассионарность Гумилева</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_029_chars" class="viz-toc-item">
                <span>VIS_029</span>
                <b class="bilingual-text" data-ru="Длина названий (символы)" data-en="Title Length (chars)">Длина названий (символы)</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_030_overlap" class="viz-toc-item">
                <span>VIS_030</span>
                <b class="bilingual-text" data-ru="Пересечение аудиторий Зограф/Рерих" data-en="Zograf/Roerich Audience Overlap">Пересечение аудиторий Зограф/Рерих</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
"""

content = content.replace("        </section>\n\n        {findings_style}", toc_html + "        </section>\n\n        {findings_style}")

# 3. Inject HTML sections
sections_html = """
        <!-- VIS_024_keywords -->
        <section class="viz-showcase-section" id="VIS_024_keywords">
            <h2>
                <span class="viz-id-badge">VIS_024</span>
                <span class="bilingual-text" data-ru="Облако терминов" data-en="Keyword Cloud">Облако терминов</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Самые частые слова в названиях докладов (>4 букв)." data-en="Most frequent words in presentation titles (>4 chars).">Самые частые слова в названиях докладов.</p>
            <div id="vis024-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis024-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis024-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_025_scale -->
        <section class="viz-showcase-section" id="VIS_025_scale">
            <h2>
                <span class="viz-id-badge">VIS_025</span>
                <span class="bilingual-text" data-ru="Масштаб конференций" data-en="Conference Scale">Масштаб конференций</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Динамика количества секций и докладов по годам." data-en="Dynamics of session and presentation counts by year.">Динамика количества секций и докладов по годам.</p>
            <div id="vis025-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis025-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis025-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_026_confidence -->
        <section class="viz-showcase-section" id="VIS_026_confidence">
            <h2>
                <span class="viz-id-badge">VIS_026</span>
                <span class="bilingual-text" data-ru="Уверенность ИИ-разметки" data-en="AI Annotation Confidence">Уверенность ИИ-разметки</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Распределение уровня уверенности DeepSeek при классификации докладов." data-en="Distribution of DeepSeek confidence levels during presentation classification.">Распределение уровня уверенности DeepSeek.</p>
            <div id="vis026-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis026-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis026-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_027_l1_themes -->
        <section class="viz-showcase-section" id="VIS_027_l1_themes">
            <h2>
                <span class="viz-id-badge">VIS_027</span>
                <span class="bilingual-text" data-ru="Популярность макро-тем" data-en="Macro-theme Popularity">Популярность макро-тем</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Топ-10 макро-тем (L1) по количеству докладов." data-en="Top 10 macro-themes (L1) by number of presentations.">Топ-10 макро-тем (L1) по количеству докладов.</p>
            <div id="vis027-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis027-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis027-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_028_gumilyov -->
        <section class="viz-showcase-section" id="VIS_028_gumilyov">
            <h2>
                <span class="viz-id-badge">VIS_028</span>
                <span class="bilingual-text" data-ru="Пассионарность Гумилева" data-en="Gumilyov Passionarity">Пассионарность Гумилева</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Распределение стадий этногенеза Гумилева в классификации докладов." data-en="Distribution of Gumilyov ethnogenesis stages in presentation classifications.">Распределение стадий этногенеза Гумилева.</p>
            <div id="vis028-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis028-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis028-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_029_chars -->
        <section class="viz-showcase-section" id="VIS_029_chars">
            <h2>
                <span class="viz-id-badge">VIS_029</span>
                <span class="bilingual-text" data-ru="Длина названий (символы)" data-en="Title Length (chars)">Длина названий (символы)</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Средняя длина названий докладов в символах по годам." data-en="Average length of presentation titles in characters by year.">Средняя длина названий докладов в символах.</p>
            <div id="vis029-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis029-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis029-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_030_overlap -->
        <section class="viz-showcase-section" id="VIS_030_overlap">
            <h2>
                <span class="viz-id-badge">VIS_030</span>
                <span class="bilingual-text" data-ru="Пересечение аудиторий" data-en="Audience Overlap">Пересечение аудиторий</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Доля ученых, выступавших только на Зографских чтениях, только на Рериховских, или на обеих конференциях." data-en="Share of scholars presenting only at Zograf, only at Roerich, or both.">Доля ученых, выступавших только на Зографских, только на Рериховских, или на обеих.</p>
            <div id="vis030-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis030-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis030-tooltip" style="{tip_style}"></div>
            </div>
        </section>

"""

content = content.replace("        <!-- VIS_016_generations -->", sections_html + "\n        <!-- VIS_016_generations -->")

# 4. Inject Constants
constants_js = '            const VIS024_DATA = """ + serialized_vis024 + """;\n            const VIS025_DATA = """ + serialized_vis025 + """;\n            const VIS026_DATA = """ + serialized_vis026 + """;\n            const VIS027_DATA = """ + serialized_vis027 + """;\n            const VIS028_DATA = """ + serialized_vis028 + """;\n            const VIS029_DATA = """ + serialized_vis029 + """;\n            const VIS030_DATA = """ + serialized_vis030 + """;\n'
content = content.replace("const ONLINE_DATA = \"\"\" + serialized_online + \"\"\";", "const ONLINE_DATA = \"\"\" + serialized_online + \"\"\";\n" + constants_js)


# 5. Inject JS Functions
js_functions = """

            function drawVIS024() {
                const svg = document.getElementById('vis024-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 30, l: 30};
                const D = VIS024_DATA; if (!D.length) return;
                
                const maxV = Math.max(...D.map(d => d.val));
                D.forEach((d, i) => {
                    const x = pad.l + Math.random() * (W - pad.l - pad.r);
                    const y = pad.t + Math.random() * (H - pad.t - pad.b);
                    const r = 5 + (d.val / maxV) * 30;
                    const c = gEl('circle', {cx: x, cy: y, r: r, fill: '#6366f1', 'fill-opacity': 0.6, stroke: '#6366f1'});
                    bindTip(c, 'vis024-wrapper', 'vis024-tooltip', () => '<strong>' + d.text + '</strong><br>' + d.val);
                    svg.appendChild(c);
                    if (r > 10) svg.appendChild(gText(x, y + 4, d.text, 'middle', Math.min(14, r), 'white'));
                });
            }

            function drawVIS025() {
                const svg = document.getElementById('vis025-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 50, l: 50};
                const D = VIS025_DATA; if (!D.length) return;
                const years = D.map(d => d.year);
                const span = years[years.length - 1] - years[0] || 1;
                const xq = y => pad.l + (y - years[0]) / span * (W - pad.l - pad.r);
                const maxV = Math.max(...D.map(d => d.pres));
                const yq = v => H - pad.b - v / maxV * (H - pad.t - pad.b);
                
                for (let v = 0; v <= maxV; v += 20) { const yy = yq(v); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, v, 'end', 11)); }
                years.forEach(y => { if (y % 2 === 0 || y === years[0]) svg.appendChild(gText(xq(y), H - pad.b + 20, y, 'middle', 10)); });
                
                svg.appendChild(gEl('polyline', {points: D.map(d => xq(d.year) + ',' + yq(d.pres)).join(' '), fill: 'none', stroke: '#10b981', 'stroke-width': 3}));
                svg.appendChild(gEl('polyline', {points: D.map(d => xq(d.year) + ',' + yq(d.sess)).join(' '), fill: 'none', stroke: '#8b5cf6', 'stroke-width': 3}));
                
                D.forEach(d => { 
                    const cp = gEl('circle', {cx: xq(d.year), cy: yq(d.pres), r: 4, fill: '#10b981'});
                    bindTip(cp, 'vis025-wrapper', 'vis025-tooltip', () => '<strong>' + d.year + '</strong><br>' + T('Доклады', 'Presentations') + ': ' + d.pres);
                    svg.appendChild(cp); 
                    
                    const cs = gEl('circle', {cx: xq(d.year), cy: yq(d.sess), r: 4, fill: '#8b5cf6'});
                    bindTip(cs, 'vis025-wrapper', 'vis025-tooltip', () => '<strong>' + d.year + '</strong><br>' + T('Секции', 'Sessions') + ': ' + d.sess);
                    svg.appendChild(cs);
                });
                
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
            }

            function drawVIS026() {
                const svg = document.getElementById('vis026-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 50, l: 100};
                const D = VIS026_DATA; if (!D.length) return;
                const maxV = Math.max(...D.map(d => d.val));
                const barH = (H - pad.t - pad.b) / D.length * 0.7;
                const pitch = (H - pad.t - pad.b) / D.length;
                
                D.forEach((d, i) => {
                    const y = pad.t + i * pitch;
                    const w = (d.val / maxV) * (W - pad.l - pad.r);
                    const rect = gEl('rect', {x: pad.l, y: y, width: w, height: barH, fill: '#ec4899', rx: 2});
                    bindTip(rect, 'vis026-wrapper', 'vis026-tooltip', () => '<strong>' + d.conf + '</strong><br>' + d.val);
                    svg.appendChild(rect);
                    svg.appendChild(gText(pad.l - 10, y + barH/2 + 4, d.conf, 'end', 11, 'var(--muted)'));
                    svg.appendChild(gText(pad.l + w + 10, y + barH/2 + 4, d.val, 'start', 11, 'var(--muted)'));
                });
            }

            function drawVIS027() {
                const svg = document.getElementById('vis027-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 50, l: 200};
                const D = VIS027_DATA; if (!D.length) return;
                const maxV = Math.max(...D.map(d => d.val));
                const barH = (H - pad.t - pad.b) / D.length * 0.7;
                const pitch = (H - pad.t - pad.b) / D.length;
                
                D.forEach((d, i) => {
                    const y = pad.t + i * pitch;
                    const w = (d.val / maxV) * (W - pad.l - pad.r);
                    const rect = gEl('rect', {x: pad.l, y: y, width: w, height: barH, fill: '#3b82f6', rx: 2});
                    bindTip(rect, 'vis027-wrapper', 'vis027-tooltip', () => '<strong>' + d.theme + '</strong><br>' + d.val);
                    svg.appendChild(rect);
                    const tLabel = d.theme.length > 30 ? d.theme.substring(0, 27) + '...' : d.theme;
                    svg.appendChild(gText(pad.l - 10, y + barH/2 + 4, tLabel, 'end', 11, 'var(--muted)'));
                    svg.appendChild(gText(pad.l + w + 10, y + barH/2 + 4, d.val, 'start', 11, 'var(--muted)'));
                });
            }

            function drawVIS028() {
                const svg = document.getElementById('vis028-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 30, l: 150};
                const D = VIS028_DATA; if (!D.length) return;
                
                const barH = (H - pad.t - pad.b) / D.length * 0.7;
                const pitch = (H - pad.t - pad.b) / D.length;
                const maxV = Math.max(...D.map(d => Object.values(d.periods).reduce((a,b)=>a+b,0)));
                
                D.forEach((d, i) => {
                    const y = pad.t + i * pitch;
                    svg.appendChild(gText(pad.l - 10, y + barH/2 + 4, d.gumilyov, 'end', 11, 'var(--muted)'));
                    let currX = pad.l;
                    const tot = Object.values(d.periods).reduce((a,b)=>a+b,0);
                    const wTot = (tot / maxV) * (W - pad.l - pad.r);
                    const rect = gEl('rect', {x: currX, y: y, width: wTot, height: barH, fill: '#f59e0b', rx: 2});
                    bindTip(rect, 'vis028-wrapper', 'vis028-tooltip', () => '<strong>' + d.gumilyov + '</strong><br>' + tot);
                    svg.appendChild(rect);
                    svg.appendChild(gText(currX + wTot + 10, y + barH/2 + 4, tot, 'start', 11, 'var(--muted)'));
                });
            }

            function drawVIS029() {
                const svg = document.getElementById('vis029-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 50, l: 50};
                const D = VIS029_DATA; if (!D.length) return;
                const years = D.map(d => d.year);
                const span = years[years.length - 1] - years[0] || 1;
                const xq = y => pad.l + (y - years[0]) / span * (W - pad.l - pad.r);
                const maxV = Math.max(...D.map(d => d.avg)) + 10;
                const yq = v => H - pad.b - v / maxV * (H - pad.t - pad.b);
                
                for (let v = 0; v <= maxV; v += 20) { const yy = yq(v); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, v, 'end', 11)); }
                years.forEach(y => { if (y % 2 === 0 || y === years[0]) svg.appendChild(gText(xq(y), H - pad.b + 20, y, 'middle', 10)); });
                
                svg.appendChild(gEl('polyline', {points: D.map(d => xq(d.year) + ',' + yq(d.avg)).join(' '), fill: 'none', stroke: '#10b981', 'stroke-width': 3}));
                D.forEach(d => { const c = gEl('circle', {cx: xq(d.year), cy: yq(d.avg), r: 4, fill: '#10b981'});
                    bindTip(c, 'vis029-wrapper', 'vis029-tooltip', () => '<strong>' + d.year + '</strong><br>' + T('Символов', 'Characters') + ': ' + d.avg.toFixed(1));
                    svg.appendChild(c); });
                
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
                svg.appendChild(gEl('line', {x1: pad.l, y1: pad.t, x2: pad.l, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
            }

            function drawVIS030() {
                const svg = document.getElementById('vis030-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 30, l: 30};
                const D = VIS030_DATA; if (!D) return;
                
                const cx1 = W/2 - 50, cx2 = W/2 + 50, cy = H/2;
                const r = 100;
                
                svg.appendChild(gEl('circle', {cx: cx1, cy: cy, r: r, fill: '#3b82f6', 'fill-opacity': 0.5, stroke: '#3b82f6'}));
                svg.appendChild(gEl('circle', {cx: cx2, cy: cy, r: r, fill: '#ef4444', 'fill-opacity': 0.5, stroke: '#ef4444'}));
                
                svg.appendChild(gText(cx1 - 40, cy, D.zograf_only, 'middle', 24, 'white'));
                svg.appendChild(gText(cx2 + 40, cy, D.roerich_only, 'middle', 24, 'white'));
                svg.appendChild(gText(W/2, cy, D.both, 'middle', 24, 'white'));
                
                svg.appendChild(gText(cx1 - 40, cy - r - 20, 'Только Зографские', 'middle', 14, 'var(--muted)'));
                svg.appendChild(gText(cx2 + 40, cy - r - 20, 'Только Рериховские', 'middle', 14, 'var(--muted)'));
                svg.appendChild(gText(W/2, cy + r + 30, 'Обе конференции (' + D.both + ')', 'middle', 14, 'var(--muted)'));
            }

"""

content = content.replace("            function drawGallery() {", js_functions + "\n            function drawGallery() {")

content = content.replace("drawVIS022, drawVIS023];", "drawVIS022, drawVIS023, drawVIS024, drawVIS025, drawVIS026, drawVIS027, drawVIS028, drawVIS029, drawVIS030];")

with open("generate_publication_pages.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Injection complete!")
