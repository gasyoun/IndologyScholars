import json

with open("generate_publication_pages.py", "r", encoding="utf-8") as f:
    content = f.read()

python_extraction_code = """
    # ===================== EXTENDED GALLERY SERIES B (VIS_035 – VIS_037) =====================

    cursor_tmp.execute('''
        SELECT pr.presentation_id, pr.title, e.year 
        FROM presentation pr
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        WHERE pr.title IS NOT NULL
    ''')
    title_data = cursor_tmp.fetchall()
    
    words_by_year = defaultdict(list)
    colon_by_year = defaultdict(list)
    for row in title_data:
        title = row['title'].strip()
        if not title: continue
        words_by_year[row['year']].append(len(title.split()))
        colon_by_year[row['year']].append(1 if ':' in title else 0)
        
    vis035_data = [{"year": k, "avg": sum(v)/len(v)} for k, v in words_by_year.items()]
    vis035_data.sort(key=lambda x: x["year"])
    serialized_vis035 = json.dumps(vis035_data, ensure_ascii=False)
    
    vis036_data = [{"year": k, "ratio": sum(v)/len(v)*100} for k, v in colon_by_year.items()]
    vis036_data.sort(key=lambda x: x["year"])
    serialized_vis036 = json.dumps(vis036_data, ensure_ascii=False)

    cursor_tmp.execute('''
        SELECT presentation_id, COUNT(person_id) as author_count
        FROM presentation_person
        GROUP BY presentation_id
    ''')
    authors_count = {row['presentation_id']: row['author_count'] for row in cursor_tmp.fetchall()}
    
    coauth_g = {"Single Author": {"1":0, "2":0, "3":0}, "Co-authored": {"1":0, "2":0, "3":0}}
    for row in ds_data:
        g = row.get("gumilyov_level", "")
        pid = row.get("presentation_id", "")
        if g in ["1", "2", "3"] and pid in authors_count:
            group = "Single Author" if authors_count[pid] == 1 else "Co-authored"
            coauth_g[group][g] += 1
            
    vis037_data = [{"group": k, "g1": v["1"], "g2": v["2"], "g3": v["3"]} for k, v in coauth_g.items()]
    serialized_vis037 = json.dumps(vis037_data, ensure_ascii=False)

"""

content = content.replace("    conn_tmp.close()", python_extraction_code + "\n    conn_tmp.close()")

toc_html = """
            <!-- SERIES B -->
            <a href="#VIS_035_words" class="viz-toc-item">
                <span>VIS_035</span>
                <b class="bilingual-text" data-ru="Инфляция заголовков (Слова)" data-en="Title Length Inflation (Words)">Инфляция заголовков (Слова)</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_036_colons" class="viz-toc-item">
                <span>VIS_036</span>
                <b class="bilingual-text" data-ru="Эра подзаголовков (Двоеточия)" data-en="The Colon Era">Эра подзаголовков (Двоеточия)</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_037_coauthors" class="viz-toc-item">
                <span>VIS_037</span>
                <b class="bilingual-text" data-ru="Коллективность и Микрокейс" data-en="Co-authorship vs Gumilyov Scale">Коллективность и Микрокейс</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
"""

content = content.replace("        </section>\n\n        {findings_style}", toc_html + "        </section>\n\n        {findings_style}")

sections_html = """
        <!-- VIS_035_words -->
        <section class="viz-showcase-section" id="VIS_035_words">
            <h2>
                <span class="viz-id-badge">VIS_035</span>
                <span class="bilingual-text" data-ru="Инфляция заголовков (Слова)" data-en="Title Length Inflation (Words)">Инфляция заголовков (Слова)</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Среднее количество слов в названиях докладов по годам. Подтверждает гипотезу H24 о сдвиге в сторону объяснительных и длинных заголовков." data-en="Average number of words in presentation titles by year. Supports H24.">Среднее количество слов в названиях докладов.</p>
            <div id="vis035-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis035-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis035-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_036_colons -->
        <section class="viz-showcase-section" id="VIS_036_colons">
            <h2>
                <span class="viz-id-badge">VIS_036</span>
                <span class="bilingual-text" data-ru="Эра подзаголовков" data-en="The Colon Era">Эра подзаголовков</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Доля названий докладов, содержащих двоеточие (как признак объяснительного подзаголовка). Подтверждает гипотезу H24." data-en="Share of presentation titles containing a colon (indicating an explanatory subtitle). Supports H24.">Доля названий докладов с подзаголовком (через двоеточие).</p>
            <div id="vis036-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis036-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis036-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_037_coauthors -->
        <section class="viz-showcase-section" id="VIS_037_coauthors">
            <h2>
                <span class="viz-id-badge">VIS_037</span>
                <span class="bilingual-text" data-ru="Коллективность и Масштаб" data-en="Co-authorship vs Scale">Коллективность и Масштаб</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Корреляция между коллективным авторством и уровнем обобщения. Подтверждает гипотезу H20." data-en="Correlation between multi-authorship and the level of generalization (Gumilyov scale). Supports H20.">Масштаб обобщения у индивидуальных и коллективных докладов.</p>
            <div id="vis037-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis037-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis037-tooltip" style="{tip_style}"></div>
            </div>
        </section>

"""

content = content.replace("        <!-- VIS_016_generations -->", sections_html + "\n        <!-- VIS_016_generations -->")

constants_js = '            const VIS035_DATA = """ + serialized_vis035 + """;\n            const VIS036_DATA = """ + serialized_vis036 + """;\n            const VIS037_DATA = """ + serialized_vis037 + """;\n'
content = content.replace("const ONLINE_DATA = \"\"\" + serialized_online + \"\"\";", "const ONLINE_DATA = \"\"\" + serialized_online + \"\"\";\n" + constants_js)

js_functions = """

            function drawVIS035() {
                const svg = document.getElementById('vis035-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 50, l: 50};
                const D = VIS035_DATA; if (!D.length) return;
                const years = D.map(d => d.year);
                const span = years[years.length - 1] - years[0] || 1;
                const xq = y => pad.l + (y - years[0]) / span * (W - pad.l - pad.r);
                const maxV = Math.max(...D.map(d => d.avg)) + 2;
                const minV = Math.max(0, Math.min(...D.map(d => d.avg)) - 2);
                const yspan = maxV - minV || 1;
                const yq = v => H - pad.b - ((v - minV) / yspan) * (H - pad.t - pad.b);
                
                for (let v = Math.floor(minV); v <= maxV; v += 1) { const yy = yq(v); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, v, 'end', 11)); }
                years.forEach(y => { if (y % 2 === 0 || y === years[0]) svg.appendChild(gText(xq(y), H - pad.b + 20, y, 'middle', 10)); });
                
                svg.appendChild(gEl('polyline', {points: D.map(d => xq(d.year) + ',' + yq(d.avg)).join(' '), fill: 'none', stroke: '#a855f7', 'stroke-width': 3}));
                D.forEach(d => { const c = gEl('circle', {cx: xq(d.year), cy: yq(d.avg), r: 4, fill: '#a855f7'});
                    bindTip(c, 'vis035-wrapper', 'vis035-tooltip', () => '<strong>' + d.year + '</strong><br>' + T('Слов', 'Words') + ': ' + d.avg.toFixed(1));
                    svg.appendChild(c); });
                
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
            }

            function drawVIS036() {
                const svg = document.getElementById('vis036-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 50, l: 50};
                const D = VIS036_DATA; if (!D.length) return;
                const years = D.map(d => d.year);
                const span = years[years.length - 1] - years[0] || 1;
                const xq = y => pad.l + (y - years[0]) / span * (W - pad.l - pad.r);
                const maxV = Math.max(...D.map(d => d.ratio)) + 5;
                const yspan = maxV || 1;
                const yq = v => H - pad.b - (v / yspan) * (H - pad.t - pad.b);
                
                for (let v = 0; v <= maxV; v += 10) { const yy = yq(v); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, v + '%', 'end', 11)); }
                years.forEach(y => { if (y % 2 === 0 || y === years[0]) svg.appendChild(gText(xq(y), H - pad.b + 20, y, 'middle', 10)); });
                
                svg.appendChild(gEl('polyline', {points: D.map(d => xq(d.year) + ',' + yq(d.ratio)).join(' '), fill: 'none', stroke: '#ec4899', 'stroke-width': 3}));
                D.forEach(d => { const c = gEl('circle', {cx: xq(d.year), cy: yq(d.ratio), r: 4, fill: '#ec4899'});
                    bindTip(c, 'vis036-wrapper', 'vis036-tooltip', () => '<strong>' + d.year + '</strong><br>' + T('С двоеточием', 'With colon') + ': ' + d.ratio.toFixed(1) + '%');
                    svg.appendChild(c); });
                
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
            }

            function drawVIS037() {
                const svg = document.getElementById('vis037-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 200, pad = {t: 30, r: 30, b: 30, l: 150};
                const D = VIS037_DATA; if (!D.length) return;
                
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
                        bindTip(r1, 'vis037-wrapper', 'vis037-tooltip', () => '<strong>' + d.group + '</strong><br>G1: ' + Math.round(d.g1/tot*100) + '%');
                        svg.appendChild(r1);
                    }
                    if(w2 > 0) {
                        const r2 = gEl('rect', {x: pad.l + w1, y: y, width: w2, height: barH, fill: c2});
                        bindTip(r2, 'vis037-wrapper', 'vis037-tooltip', () => '<strong>' + d.group + '</strong><br>G2: ' + Math.round(d.g2/tot*100) + '%');
                        svg.appendChild(r2);
                    }
                    if(w3 > 0) {
                        const r3 = gEl('rect', {x: pad.l + w1 + w2, y: y, width: w3, height: barH, fill: c3});
                        bindTip(r3, 'vis037-wrapper', 'vis037-tooltip', () => '<strong>' + d.group + '</strong><br>G3: ' + Math.round(d.g3/tot*100) + '%');
                        svg.appendChild(r3);
                    }
                });
            }

"""

content = content.replace("            function drawGallery() {", js_functions + "\n            function drawGallery() {")
content = content.replace("drawVIS034];", "drawVIS034, drawVIS035, drawVIS036, drawVIS037];")

with open("generate_publication_pages.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Injection of Series B complete!")

