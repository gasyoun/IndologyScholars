import json

with open("generate_publication_pages.py", "r", encoding="utf-8") as f:
    content = f.read()

python_extraction_code = """
    # ===================== EXTENDED GALLERY SERIES A (VIS_031 – VIS_034) =====================

    cursor_tmp.execute('''
        SELECT pr.presentation_id, p.birth_year, e.year, pp.person_id, es.series_name_en
        FROM presentation pr
        JOIN presentation_person pp ON pr.presentation_id = pp.presentation_id
        JOIN person p ON pp.person_id = p.person_id
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        JOIN event_series es ON e.event_series_id = es.event_series_id
    ''')
    pres_meta = {row['presentation_id']: dict(row) for row in cursor_tmp.fetchall()}
    
    # Pre-calculate Boxplot stats
    def boxplot_stats(data):
        if not data: return None
        s = sorted(data)
        n = len(s)
        q1 = s[int(n*0.25)]
        median = s[int(n*0.5)]
        q3 = s[int(n*0.75)]
        return {"min": s[0], "q1": q1, "median": median, "q3": q3, "max": s[-1], "count": n}

    # VIS_031: Age vs Gumilyov Level
    vis031_raw = {"1": [], "2": [], "3": []}
    for row in ds_data:
        g = row.get("gumilyov_level", "")
        pid = row.get("presentation_id", "")
        if g in vis031_raw and pid in pres_meta:
            meta = pres_meta[pid]
            if meta['birth_year']:
                age = meta['year'] - meta['birth_year']
                if 20 <= age <= 100:
                    vis031_raw[g].append(age)
    vis031_data = [{"level": k, "stats": boxplot_stats(v)} for k, v in vis031_raw.items() if v]
    serialized_vis031 = json.dumps(vis031_data, ensure_ascii=False)

    # VIS_032: Disciplinary Scale (L1 themes)
    vis032_raw = defaultdict(lambda: {"1": 0, "2": 0, "3": 0})
    for row in ds_data:
        l1 = row.get("theme_l1", "")
        g = row.get("gumilyov_level", "")
        if l1 and g in ["1", "2", "3"]:
            vis032_raw[l1][g] += 1
    vis032_data = [{"theme": k, "g1": v["1"], "g2": v["2"], "g3": v["3"]} for k, v in vis032_raw.items()]
    vis032_data.sort(key=lambda x: x["g1"] + x["g2"] + x["g3"], reverse=True)
    serialized_vis032 = json.dumps(vis032_data, ensure_ascii=False)

    # VIS_033: Core vs Periphery Abstraction
    person_counts = defaultdict(int)
    for meta in pres_meta.values():
        person_counts[meta['person_id']] += 1
        
    core_periph_g = {"Core (>=5)": {"1":0, "2":0, "3":0}, "Periphery (<5)": {"1":0, "2":0, "3":0}}
    for row in ds_data:
        g = row.get("gumilyov_level", "")
        pid = row.get("presentation_id", "")
        if g in ["1", "2", "3"] and pid in pres_meta:
            p_id = pres_meta[pid]['person_id']
            group = "Core (>=5)" if person_counts[p_id] >= 5 else "Periphery (<5)"
            core_periph_g[group][g] += 1
    vis033_data = [{"group": k, "g1": v["1"], "g2": v["2"], "g3": v["3"]} for k, v in core_periph_g.items()]
    serialized_vis033 = json.dumps(vis033_data, ensure_ascii=False)

    # VIS_034: Bridge vs Single-Venue Abstraction
    pers_series = defaultdict(set)
    for meta in pres_meta.values():
        pers_series[meta['person_id']].add(meta['series_name_en'])
    
    bridge_single_g = {"Bridge (Both)": {"1":0, "2":0, "3":0}, "Single-Venue": {"1":0, "2":0, "3":0}}
    for row in ds_data:
        g = row.get("gumilyov_level", "")
        pid = row.get("presentation_id", "")
        if g in ["1", "2", "3"] and pid in pres_meta:
            p_id = pres_meta[pid]['person_id']
            series = pers_series[p_id]
            is_z = any('Zograf' in x for x in series)
            is_r = any('Roerich' in x for x in series)
            group = "Bridge (Both)" if (is_z and is_r) else "Single-Venue"
            bridge_single_g[group][g] += 1
    vis034_data = [{"group": k, "g1": v["1"], "g2": v["2"], "g3": v["3"]} for k, v in bridge_single_g.items()]
    serialized_vis034 = json.dumps(vis034_data, ensure_ascii=False)

"""

content = content.replace("    conn_tmp.close()", python_extraction_code + "\n    conn_tmp.close()")

toc_html = """
            <!-- SERIES A -->
            <a href="#VIS_031_age_scale" class="viz-toc-item">
                <span>VIS_031</span>
                <b class="bilingual-text" data-ru="Возраст и Масштаб (G1-G3)" data-en="Age vs Abstraction (G1-G3)">Возраст и Масштаб (G1-G3)</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_032_disc_scale" class="viz-toc-item">
                <span>VIS_032</span>
                <b class="bilingual-text" data-ru="Дисциплина и Масштаб" data-en="Discipline vs Abstraction">Дисциплина и Масштаб</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_033_core_scale" class="viz-toc-item">
                <span>VIS_033</span>
                <b class="bilingual-text" data-ru="Масштаб: Ядро vs Периферия" data-en="Scale: Core vs Periphery">Масштаб: Ядро vs Периферия</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_034_bridge_scale" class="viz-toc-item">
                <span>VIS_034</span>
                <b class="bilingual-text" data-ru="Масштаб: Мостовики vs Локальные" data-en="Scale: Bridges vs Local">Масштаб: Мостовики vs Локальные</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
"""

content = content.replace("        </section>\n\n        {findings_style}", toc_html + "        </section>\n\n        {findings_style}")

sections_html = """
        <!-- VIS_031_age_scale -->
        <section class="viz-showcase-section" id="VIS_031_age_scale">
            <h2>
                <span class="viz-id-badge">VIS_031</span>
                <span class="bilingual-text" data-ru="Возраст и Масштаб обобщения (Шкала Гумилева)" data-en="Age vs Scale of Abstraction">Возраст и Масштаб обобщения</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Распределение возраста авторов для докладов уровней G1, G2, G3. Подтверждает гипотезу H35 о том, что широкое обобщение — прерогатива старшего поколения." data-en="Distribution of author age for G1, G2, G3 presentations. Supports H35.">Возраст авторов и масштаб доклада.</p>
            <div id="vis031-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis031-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis031-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_032_disc_scale -->
        <section class="viz-showcase-section" id="VIS_032_disc_scale">
            <h2>
                <span class="viz-id-badge">VIS_032</span>
                <span class="bilingual-text" data-ru="Дисциплинарный масштаб" data-en="Disciplinary Scale">Дисциплинарный масштаб</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Доля микрокейсов (G1) и обобщений (G2/G3) внутри каждой дисциплины (L1). Подтверждает гипотезу H34." data-en="Share of microcases (G1) and generalizations (G2/G3) by discipline (L1). Supports H34.">Масштаб обобщения по дисциплинам.</p>
            <div id="vis032-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis032-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis032-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_033_core_scale -->
        <section class="viz-showcase-section" id="VIS_033_core_scale">
            <h2>
                <span class="viz-id-badge">VIS_033</span>
                <span class="bilingual-text" data-ru="Масштаб: Ядро vs Периферия" data-en="Scale: Core vs Periphery">Масштаб: Ядро vs Периферия</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Подтверждает H32: Ядро (>=5 докладов) не производит больше макрообобщений (G3), чем периферия." data-en="Supports H32: Core (>=5 talks) does not produce more macro generalizations than periphery.">Масштаб обобщения у Ядра и Периферии.</p>
            <div id="vis033-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis033-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis033-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_034_bridge_scale -->
        <section class="viz-showcase-section" id="VIS_034_bridge_scale">
            <h2>
                <span class="viz-id-badge">VIS_034</span>
                <span class="bilingual-text" data-ru="Масштаб: Мостовики vs Локальные" data-en="Scale: Bridges vs Local">Масштаб: Мостовики vs Локальные</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Подтверждает H27: Участники обеих площадок не являются синтетиками, их доля макрообобщений даже ниже." data-en="Supports H27: Bridge scholars are not macro-synthesizers.">Масштаб мышления участников обеих площадок.</p>
            <div id="vis034-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis034-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis034-tooltip" style="{tip_style}"></div>
            </div>
        </section>

"""

content = content.replace("        <!-- VIS_016_generations -->", sections_html + "\n        <!-- VIS_016_generations -->")

constants_js = '            const VIS031_DATA = """ + serialized_vis031 + """;\n            const VIS032_DATA = """ + serialized_vis032 + """;\n            const VIS033_DATA = """ + serialized_vis033 + """;\n            const VIS034_DATA = """ + serialized_vis034 + """;\n'
content = content.replace("const ONLINE_DATA = \"\"\" + serialized_online + \"\"\";", "const ONLINE_DATA = \"\"\" + serialized_online + \"\"\";\n" + constants_js)

js_functions = """

            function drawVIS031() {
                const svg = document.getElementById('vis031-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 30, l: 60};
                const D = VIS031_DATA; if (!D.length) return;
                
                const minV = Math.min(...D.map(d => d.stats ? d.stats.min : 100)) - 5;
                const maxV = Math.max(...D.map(d => d.stats ? d.stats.max : 0)) + 5;
                const span = maxV - minV || 1;
                const xq = v => pad.l + ((v - minV) / span) * (W - pad.l - pad.r);
                
                for(let v = Math.floor(minV/10)*10; v <= maxV; v+=10) {
                    svg.appendChild(gEl('line', {x1: xq(v), y1: pad.t, x2: xq(v), y2: H - pad.b, stroke: 'rgba(255,255,255,0.05)'}));
                    svg.appendChild(gText(xq(v), H - pad.b + 20, v, 'middle', 10, 'var(--muted)'));
                }
                
                const pitch = (H - pad.t - pad.b) / D.length;
                D.forEach((d, i) => {
                    const y = pad.t + i * pitch + pitch/2;
                    svg.appendChild(gText(pad.l - 10, y + 4, 'Level ' + d.level, 'end', 12, 'var(--muted)'));
                    if(!d.stats) return;
                    
                    svg.appendChild(gEl('line', {x1: xq(d.stats.min), y1: y, x2: xq(d.stats.max), y2: y, stroke: '#f59e0b', 'stroke-width': 2}));
                    svg.appendChild(gEl('rect', {x: xq(d.stats.q1), y: y - 15, width: xq(d.stats.q3) - xq(d.stats.q1), height: 30, fill: '#f59e0b', 'fill-opacity': 0.4, stroke: '#f59e0b'}));
                    svg.appendChild(gEl('line', {x1: xq(d.stats.median), y1: y - 15, x2: xq(d.stats.median), y2: y + 15, stroke: 'white', 'stroke-width': 2}));
                    
                    const rect = gEl('rect', {x: xq(d.stats.min), y: y - 15, width: xq(d.stats.max) - xq(d.stats.min), height: 30, fill: 'transparent', cursor: 'pointer'});
                    bindTip(rect, 'vis031-wrapper', 'vis031-tooltip', () => '<strong>G' + d.level + '</strong><br>Медиана: ' + d.stats.median + ' лет<br>Разброс: ' + d.stats.min + ' - ' + d.stats.max + ' лет<br>Докладов: ' + d.stats.count);
                    svg.appendChild(rect);
                });
            }

            function drawVIS032() {
                const svg = document.getElementById('vis032-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 30, l: 200};
                const D = VIS032_DATA; if (!D.length) return;
                
                const pitch = (H - pad.t - pad.b) / D.length;
                const barH = pitch * 0.7;
                
                D.forEach((d, i) => {
                    const y = pad.t + i * pitch;
                    const tot = d.g1 + d.g2 + d.g3;
                    if(tot === 0) return;
                    
                    const tLabel = d.theme.length > 25 ? d.theme.substring(0, 22) + '...' : d.theme;
                    svg.appendChild(gText(pad.l - 10, y + barH/2 + 4, tLabel, 'end', 11, 'var(--muted)'));
                    
                    const w1 = (d.g1 / tot) * (W - pad.l - pad.r);
                    const w2 = (d.g2 / tot) * (W - pad.l - pad.r);
                    const w3 = (d.g3 / tot) * (W - pad.l - pad.r);
                    
                    const c1 = '#3b82f6', c2 = '#f59e0b', c3 = '#ef4444';
                    
                    if(w1 > 0) {
                        const r1 = gEl('rect', {x: pad.l, y: y, width: w1, height: barH, fill: c1});
                        bindTip(r1, 'vis032-wrapper', 'vis032-tooltip', () => '<strong>' + d.theme + '</strong><br>G1 (Микрокейс): ' + d.g1 + ' (' + Math.round(d.g1/tot*100) + '%)');
                        svg.appendChild(r1);
                    }
                    if(w2 > 0) {
                        const r2 = gEl('rect', {x: pad.l + w1, y: y, width: w2, height: barH, fill: c2});
                        bindTip(r2, 'vis032-wrapper', 'vis032-tooltip', () => '<strong>' + d.theme + '</strong><br>G2 (Регион): ' + d.g2 + ' (' + Math.round(d.g2/tot*100) + '%)');
                        svg.appendChild(r2);
                    }
                    if(w3 > 0) {
                        const r3 = gEl('rect', {x: pad.l + w1 + w2, y: y, width: w3, height: barH, fill: c3});
                        bindTip(r3, 'vis032-wrapper', 'vis032-tooltip', () => '<strong>' + d.theme + '</strong><br>G3 (Глобал): ' + d.g3 + ' (' + Math.round(d.g3/tot*100) + '%)');
                        svg.appendChild(r3);
                    }
                });
            }

            function drawVIS033() {
                const svg = document.getElementById('vis033-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 200, pad = {t: 30, r: 30, b: 30, l: 150};
                const D = VIS033_DATA; if (!D.length) return;
                
                const pitch = (H - pad.t - pad.b) / D.length;
                const barH = pitch * 0.7;
                
                D.forEach((d, i) => {
                    const y = pad.t + i * pitch;
                    const tot = d.g1 + d.g2 + d.g3;
                    if(tot === 0) return;
                    
                    svg.appendChild(gText(pad.l - 10, y + barH/2 + 4, d.group, 'end', 12, 'var(--muted)'));
                    
                    const w1 = (d.g1 / tot) * (W - pad.l - pad.r);
                    const w2 = (d.g2 / tot) * (W - pad.l - pad.r);
                    const w3 = (d.g3 / tot) * (W - pad.l - pad.r);
                    
                    const c1 = '#3b82f6', c2 = '#f59e0b', c3 = '#ef4444';
                    
                    if(w1 > 0) {
                        const r1 = gEl('rect', {x: pad.l, y: y, width: w1, height: barH, fill: c1});
                        bindTip(r1, 'vis033-wrapper', 'vis033-tooltip', () => '<strong>' + d.group + '</strong><br>G1: ' + Math.round(d.g1/tot*100) + '%');
                        svg.appendChild(r1);
                    }
                    if(w2 > 0) {
                        const r2 = gEl('rect', {x: pad.l + w1, y: y, width: w2, height: barH, fill: c2});
                        bindTip(r2, 'vis033-wrapper', 'vis033-tooltip', () => '<strong>' + d.group + '</strong><br>G2: ' + Math.round(d.g2/tot*100) + '%');
                        svg.appendChild(r2);
                    }
                    if(w3 > 0) {
                        const r3 = gEl('rect', {x: pad.l + w1 + w2, y: y, width: w3, height: barH, fill: c3});
                        bindTip(r3, 'vis033-wrapper', 'vis033-tooltip', () => '<strong>' + d.group + '</strong><br>G3: ' + Math.round(d.g3/tot*100) + '%');
                        svg.appendChild(r3);
                    }
                });
            }

            function drawVIS034() {
                const svg = document.getElementById('vis034-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 200, pad = {t: 30, r: 30, b: 30, l: 150};
                const D = VIS034_DATA; if (!D.length) return;
                
                const pitch = (H - pad.t - pad.b) / D.length;
                const barH = pitch * 0.7;
                
                D.forEach((d, i) => {
                    const y = pad.t + i * pitch;
                    const tot = d.g1 + d.g2 + d.g3;
                    if(tot === 0) return;
                    
                    svg.appendChild(gText(pad.l - 10, y + barH/2 + 4, d.group, 'end', 12, 'var(--muted)'));
                    
                    const w1 = (d.g1 / tot) * (W - pad.l - pad.r);
                    const w2 = (d.g2 / tot) * (W - pad.l - pad.r);
                    const w3 = (d.g3 / tot) * (W - pad.l - pad.r);
                    
                    const c1 = '#3b82f6', c2 = '#f59e0b', c3 = '#ef4444';
                    
                    if(w1 > 0) {
                        const r1 = gEl('rect', {x: pad.l, y: y, width: w1, height: barH, fill: c1});
                        bindTip(r1, 'vis034-wrapper', 'vis034-tooltip', () => '<strong>' + d.group + '</strong><br>G1: ' + Math.round(d.g1/tot*100) + '%');
                        svg.appendChild(r1);
                    }
                    if(w2 > 0) {
                        const r2 = gEl('rect', {x: pad.l + w1, y: y, width: w2, height: barH, fill: c2});
                        bindTip(r2, 'vis034-wrapper', 'vis034-tooltip', () => '<strong>' + d.group + '</strong><br>G2: ' + Math.round(d.g2/tot*100) + '%');
                        svg.appendChild(r2);
                    }
                    if(w3 > 0) {
                        const r3 = gEl('rect', {x: pad.l + w1 + w2, y: y, width: w3, height: barH, fill: c3});
                        bindTip(r3, 'vis034-wrapper', 'vis034-tooltip', () => '<strong>' + d.group + '</strong><br>G3: ' + Math.round(d.g3/tot*100) + '%');
                        svg.appendChild(r3);
                    }
                });
            }

"""

content = content.replace("            function drawGallery() {", js_functions + "\n            function drawGallery() {")
content = content.replace("drawVIS030];", "drawVIS030, drawVIS031, drawVIS032, drawVIS033, drawVIS034];")

with open("generate_publication_pages.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Injection of Series A complete!")

