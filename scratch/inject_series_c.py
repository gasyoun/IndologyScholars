import json

with open("generate_publication_pages.py", "r", encoding="utf-8") as f:
    content = f.read()

python_extraction_code = """
    # ===================== EXTENDED GALLERY SERIES C (VIS_038 – VIS_040) =====================

    cursor_tmp.execute('''
        SELECT pr.presentation_id, e.year, es.series_name_en, 
               (SELECT COUNT(*) FROM media m WHERE m.attached_to_id = pr.presentation_id AND m.attached_to_type='presentation') as has_video
        FROM presentation pr
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
        JOIN event_series es ON e.event_series_id = es.event_series_id
    ''')
    vid_data = cursor_tmp.fetchall()

    vid_years = defaultdict(lambda: {"total": 0, "video": 0})
    for row in vid_data:
        vid_years[row['year']]["total"] += 1
        if row['has_video'] > 0:
            vid_years[row['year']]["video"] += 1
            
    vis038_data = [{"year": k, "total": v["total"], "video": v["video"]} for k, v in vid_years.items()]
    vis038_data.sort(key=lambda x: x["year"])
    serialized_vis038 = json.dumps(vis038_data, ensure_ascii=False)

    vid_dict = {row['presentation_id']: row['has_video'] > 0 for row in vid_data}
    vid_g = {"Recorded": {"1":0, "2":0, "3":0}, "Unrecorded": {"1":0, "2":0, "3":0}}
    for row in ds_data:
        g = row.get("gumilyov_level", "")
        pid = row.get("presentation_id", "")
        if g in ["1", "2", "3"] and pid in vid_dict:
            group = "Recorded" if vid_dict[pid] else "Unrecorded"
            vid_g[group][g] += 1
    vis039_data = [{"group": k, "g1": v["1"], "g2": v["2"], "g3": v["3"]} for k, v in vid_g.items()]
    serialized_vis039 = json.dumps(vis039_data, ensure_ascii=False)

    cursor_tmp.execute('''
        SELECT pp.person_id, pr.presentation_id
        FROM presentation_person pp
        JOIN presentation pr ON pp.presentation_id = pr.presentation_id
    ''')
    pp_data = cursor_tmp.fetchall()
    person_counts = defaultdict(int)
    for row in pp_data:
        person_counts[row['person_id']] += 1
        
    core_periph_vid = {"Core (>=5)": {"video":0, "no_video":0}, "Periphery (<5)": {"video":0, "no_video":0}}
    for row in pp_data:
        pid = row['presentation_id']
        if pid in vid_dict:
            group = "Core (>=5)" if person_counts[row['person_id']] >= 5 else "Periphery (<5)"
            status = "video" if vid_dict[pid] else "no_video"
            core_periph_vid[group][status] += 1
            
    vis040_data = [{"group": k, "video": v["video"], "no_video": v["no_video"]} for k, v in core_periph_vid.items()]
    serialized_vis040 = json.dumps(vis040_data, ensure_ascii=False)

"""

content = content.replace("    conn_tmp.close()", python_extraction_code + "\n    conn_tmp.close()")

toc_html = """
            <!-- SERIES C -->
            <a href="#VIS_038_vid_years" class="viz-toc-item">
                <span>VIS_038</span>
                <b class="bilingual-text" data-ru="Радары видимости (YouTube Bias)" data-en="Visibility Radars (YouTube Bias)">Радары видимости (YouTube Bias)</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_039_vid_scale" class="viz-toc-item">
                <span>VIS_039</span>
                <b class="bilingual-text" data-ru="Смещение в Микрокейсы" data-en="Microcase Bias">Смещение в Микрокейсы</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_040_vid_core" class="viz-toc-item">
                <span>VIS_040</span>
                <b class="bilingual-text" data-ru="Статус и Камера" data-en="Status and Camera">Статус и Камера</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
"""

content = content.replace("        </section>\n\n        {findings_style}", toc_html + "        </section>\n\n        {findings_style}")

sections_html = """
        <!-- VIS_038_vid_years -->
        <section class="viz-showcase-section" id="VIS_038_vid_years">
            <h2>
                <span class="viz-id-badge">VIS_038</span>
                <span class="bilingual-text" data-ru="Радары видимости (YouTube Bias)" data-en="Visibility Radars (YouTube Bias)">Радары видимости (YouTube Bias)</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Количество записанных на видео докладов (красный) относительно общего числа докладов (синий) по годам. Доказывает H13 об огромном историческом перекосе медиа-архива." data-en="Number of video-recorded presentations vs total presentations by year. Proves H13 regarding the massive historical bias of the media archive.">Покрытие конференции видеозаписями.</p>
            <div id="vis038-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis038-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis038-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_039_vid_scale -->
        <section class="viz-showcase-section" id="VIS_039_vid_scale">
            <h2>
                <span class="viz-id-badge">VIS_039</span>
                <span class="bilingual-text" data-ru="Смещение в Микрокейсы" data-en="Microcase Bias">Смещение в Микрокейсы</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Распределение записанных и незаписанных докладов по шкале Гумилева. Доказывает H30: на видео попадают почти исключительно G1, макрообобщения мы не записываем." data-en="Distribution of recorded and unrecorded talks on the Gumilyov scale. Proves H30: video almost exclusively captures G1 microcases.">Какие жанры попадают на YouTube?</p>
            <div id="vis039-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis039-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis039-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_040_vid_core -->
        <section class="viz-showcase-section" id="VIS_040_vid_core">
            <h2>
                <span class="viz-id-badge">VIS_040</span>
                <span class="bilingual-text" data-ru="Статус и Камера" data-en="Status and Camera">Статус и Камера</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Сравнение покрытия видеозаписями Ядра (>=5 докладов) и Периферии. Доказывает H25: камера снимает не по статусу ученого, а по технической случайности." data-en="Comparison of video coverage for Core (>=5 talks) vs Periphery. Proves H25: the camera records by chance, not by academic status.">Зависит ли видеозапись от статуса ученого?</p>
            <div id="vis040-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis040-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis040-tooltip" style="{tip_style}"></div>
            </div>
        </section>

"""

content = content.replace("        <!-- VIS_016_generations -->", sections_html + "\n        <!-- VIS_016_generations -->")

constants_js = '            const VIS038_DATA = """ + serialized_vis038 + """;\n            const VIS039_DATA = """ + serialized_vis039 + """;\n            const VIS040_DATA = """ + serialized_vis040 + """;\n'
content = content.replace("const ONLINE_DATA = \"\"\" + serialized_online + \"\"\";", "const ONLINE_DATA = \"\"\" + serialized_online + \"\"\";\n" + constants_js)

js_functions = """

            function drawVIS038() {
                const svg = document.getElementById('vis038-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 50, l: 50};
                const D = VIS038_DATA; if (!D.length) return;
                const years = D.map(d => d.year);
                const span = years[years.length - 1] - years[0] || 1;
                const xq = y => pad.l + (y - years[0]) / span * (W - pad.l - pad.r);
                const maxV = Math.max(...D.map(d => d.total));
                const yq = v => H - pad.b - (v / maxV) * (H - pad.t - pad.b);
                
                for (let v = 0; v <= maxV; v += 20) { const yy = yq(v); svg.appendChild(gEl('line', {x1: pad.l, y1: yy, x2: W - pad.r, y2: yy, stroke: 'rgba(255,255,255,0.06)'})); svg.appendChild(gText(pad.l - 10, yy + 4, v, 'end', 11)); }
                years.forEach(y => { if (y % 2 === 0 || y === years[0]) svg.appendChild(gText(xq(y), H - pad.b + 20, y, 'middle', 10)); });
                
                const barW = (W - pad.l - pad.r) / D.length * 0.6;
                D.forEach(d => { 
                    const x = xq(d.year) - barW/2;
                    
                    const hTotal = (d.total / maxV) * (H - pad.t - pad.b);
                    const rectTotal = gEl('rect', {x: x, y: H - pad.b - hTotal, width: barW, height: hTotal, fill: '#3b82f6', 'fill-opacity': 0.3});
                    
                    const hVideo = (d.video / maxV) * (H - pad.t - pad.b);
                    const rectVideo = gEl('rect', {x: x, y: H - pad.b - hVideo, width: barW, height: hVideo, fill: '#ef4444'});
                    
                    bindTip(rectTotal, 'vis038-wrapper', 'vis038-tooltip', () => '<strong>' + d.year + '</strong><br>Всего докладов: ' + d.total + '<br>На видео: ' + d.video + ' (' + Math.round(d.video/d.total*100) + '%)');
                    
                    svg.appendChild(rectTotal); 
                    if(d.video > 0) svg.appendChild(rectVideo);
                });
                
                svg.appendChild(gEl('line', {x1: pad.l, y1: H - pad.b, x2: W - pad.r, y2: H - pad.b, stroke: 'rgba(255,255,255,0.2)'}));
            }

            function drawVIS039() {
                const svg = document.getElementById('vis039-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 200, pad = {t: 30, r: 30, b: 30, l: 150};
                const D = VIS039_DATA; if (!D.length) return;
                
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
                        bindTip(r1, 'vis039-wrapper', 'vis039-tooltip', () => '<strong>' + d.group + '</strong><br>G1: ' + Math.round(d.g1/tot*100) + '% (' + d.g1 + ')');
                        svg.appendChild(r1);
                    }
                    if(w2 > 0) {
                        const r2 = gEl('rect', {x: pad.l + w1, y: y, width: w2, height: barH, fill: c2});
                        bindTip(r2, 'vis039-wrapper', 'vis039-tooltip', () => '<strong>' + d.group + '</strong><br>G2: ' + Math.round(d.g2/tot*100) + '% (' + d.g2 + ')');
                        svg.appendChild(r2);
                    }
                    if(w3 > 0) {
                        const r3 = gEl('rect', {x: pad.l + w1 + w2, y: y, width: w3, height: barH, fill: c3});
                        bindTip(r3, 'vis039-wrapper', 'vis039-tooltip', () => '<strong>' + d.group + '</strong><br>G3: ' + Math.round(d.g3/tot*100) + '% (' + d.g3 + ')');
                        svg.appendChild(r3);
                    }
                });
            }

            function drawVIS040() {
                const svg = document.getElementById('vis040-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 200, pad = {t: 30, r: 30, b: 30, l: 150};
                const D = VIS040_DATA; if (!D.length) return;
                
                const pitch = (H - pad.t - pad.b) / D.length;
                const barH = pitch * 0.7;
                
                D.forEach((d, i) => {
                    const y = pad.t + i * pitch;
                    const tot = d.video + d.no_video;
                    if(tot === 0) return;
                    
                    svg.appendChild(gText(pad.l - 10, y + barH/2 + 4, d.group, 'end', 12, 'var(--muted)'));
                    
                    const w1 = (d.video / tot) * (W - pad.l - pad.r);
                    const w2 = (d.no_video / tot) * (W - pad.l - pad.r);
                    
                    const c1 = '#ef4444', c2 = '#3b82f6';
                    
                    if(w1 > 0) {
                        const r1 = gEl('rect', {x: pad.l, y: y, width: w1, height: barH, fill: c1});
                        bindTip(r1, 'vis040-wrapper', 'vis040-tooltip', () => '<strong>' + d.group + '</strong><br>Видео: ' + Math.round(d.video/tot*100) + '% (' + d.video + ')');
                        svg.appendChild(r1);
                    }
                    if(w2 > 0) {
                        const r2 = gEl('rect', {x: pad.l + w1, y: y, width: w2, height: barH, fill: c2, 'fill-opacity': 0.3});
                        bindTip(r2, 'vis040-wrapper', 'vis040-tooltip', () => '<strong>' + d.group + '</strong><br>Без видео: ' + Math.round(d.no_video/tot*100) + '% (' + d.no_video + ')');
                        svg.appendChild(r2);
                    }
                });
            }

"""

content = content.replace("            function drawGallery() {", js_functions + "\n            function drawGallery() {")
content = content.replace("drawVIS037];", "drawVIS037, drawVIS038, drawVIS039, drawVIS040];")

with open("generate_publication_pages.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Injection of Series C complete!")

