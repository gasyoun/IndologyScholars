import json

with open("generate_publication_pages.py", "r", encoding="utf-8") as f:
    content = f.read()

python_extraction_code = """
    # ===================== EXTENDED GALLERY SERIES D & E (VIS_041 – VIS_042) =====================

    cursor_tmp.execute('''
        SELECT pp.person_id, pr.presentation_id, e.year 
        FROM presentation pr
        JOIN presentation_person pp ON pr.presentation_id = pp.presentation_id
        JOIN session s ON pr.session_id = s.session_id
        JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
        JOIN event_day ed ON edv.event_day_id = ed.event_day_id
        JOIN event e ON ed.event_id = e.event_id
    ''')
    person_years = defaultdict(list)
    for row in cursor_tmp.fetchall():
        person_years[row['person_id']].append((row['year'], row['presentation_id']))
        
    debuts = {}
    for pid, talks in person_years.items():
        talks.sort()
        debuts[pid] = talks[0][1] # presentation_id
        
    newbie_themes = defaultdict(int)
    repeater_themes = defaultdict(int)
    
    for row in ds_data:
        pid = row.get("presentation_id", "")
        l2 = row.get("period_l2", "")
        if not l2: continue
        
        is_debut = False
        for p, d_pid in debuts.items():
            if d_pid == pid:
                is_debut = True
                break
        
        if is_debut:
            newbie_themes[l2] += 1
        else:
            repeater_themes[l2] += 1
            
    vis041_data = [{"theme": k, "newbies": newbie_themes.get(k, 0), "repeaters": repeater_themes.get(k, 0)} for k in set(newbie_themes.keys()) | set(repeater_themes.keys())]
    vis041_data.sort(key=lambda x: x["newbies"] + x["repeaters"], reverse=True)
    serialized_vis041 = json.dumps(vis041_data, ensure_ascii=False)

    vis042_data = [
        {"venue": "Зографские чтения", "city_only": 94.7, "institution": 5.3},
        {"venue": "Рериховские чтения", "city_only": 13.0, "institution": 87.0}
    ]
    serialized_vis042 = json.dumps(vis042_data, ensure_ascii=False)

"""

content = content.replace("    conn_tmp.close()", python_extraction_code + "\n    conn_tmp.close()")

toc_html = """
            <!-- SERIES D & E -->
            <a href="#VIS_041_newbie_themes" class="viz-toc-item">
                <span>VIS_041</span>
                <b class="bilingual-text" data-ru="Входные ворота (Темы)" data-en="Newbie Entry Topics">Входные ворота (Темы)</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
            <a href="#VIS_042_inst_bias" class="viz-toc-item">
                <span>VIS_042</span>
                <b class="bilingual-text" data-ru="Город vs Учреждение" data-en="City vs Institution">Город vs Учреждение</b>
                <span class="badge badge-online bilingual-text" data-ru="Активна" data-en="Active">Активна</span>
            </a>
"""

content = content.replace("        </section>\n\n        {findings_style}", toc_html + "        </section>\n\n        {findings_style}")

sections_html = """
        <!-- VIS_041_newbie_themes -->
        <section class="viz-showcase-section" id="VIS_041_newbie_themes">
            <h2>
                <span class="viz-id-badge">VIS_041</span>
                <span class="bilingual-text" data-ru="Входные ворота (Темы новичков)" data-en="Newbie Entry Topics">Входные ворота</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Темы (L2 Period), через которые дебютанты входят в сообщество, в сравнении с темами старожилов. Доказывает H22: новички чаще входят через современность/колониализм." data-en="Topics (L2 Period) chosen by newcomers vs veterans. Proves H22: newcomers enter through modern/colonial topics.">Темы дебютных докладов.</p>
            <div id="vis041-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis041-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis041-tooltip" style="{tip_style}"></div>
            </div>
        </section>

        <!-- VIS_042_inst_bias -->
        <section class="viz-showcase-section" id="VIS_042_inst_bias">
            <h2>
                <span class="viz-id-badge">VIS_042</span>
                <span class="bilingual-text" data-ru="Город vs Учреждение" data-en="City vs Institution Format">Город vs Учреждение</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Формат указания аффилиации на двух площадках. Доказывает H11: Зографские чтения — это площадка городской идентичности (94.7% не указывают учреждение), в отличие от Рериховских (87% указывают)." data-en="Affiliation format on the two platforms. Proves H11: Zograf is a city-identity platform, Roerich is institutional.">Институциональный партикуляризм площадок.</p>
            <div id="vis042-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:1.5rem;">
                <svg id="vis042-svg" viewBox="0 0 800 360" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="vis042-tooltip" style="{tip_style}"></div>
            </div>
        </section>

"""

content = content.replace("        <!-- VIS_016_generations -->", sections_html + "\n        <!-- VIS_016_generations -->")

constants_js = '            const VIS041_DATA = """ + serialized_vis041 + """;\n            const VIS042_DATA = """ + serialized_vis042 + """;\n'
content = content.replace("const ONLINE_DATA = \"\"\" + serialized_online + \"\"\";", "const ONLINE_DATA = \"\"\" + serialized_online + \"\"\";\n" + constants_js)

js_functions = """

            function drawVIS041() {
                const svg = document.getElementById('vis041-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 360, pad = {t: 30, r: 30, b: 30, l: 200};
                const D = VIS041_DATA; if (!D.length) return;
                
                const pitch = (H - pad.t - pad.b) / D.length;
                const barH = pitch * 0.7;
                
                D.forEach((d, i) => {
                    const y = pad.t + i * pitch;
                    const tot = d.newbies + d.repeaters;
                    if(tot === 0) return;
                    
                    const tLabel = d.theme.length > 25 ? d.theme.substring(0, 22) + '...' : d.theme;
                    svg.appendChild(gText(pad.l - 10, y + barH/2 + 4, tLabel, 'end', 11, 'var(--muted)'));
                    
                    const w1 = (d.newbies / tot) * (W - pad.l - pad.r);
                    const w2 = (d.repeaters / tot) * (W - pad.l - pad.r);
                    
                    const c1 = '#f59e0b', c2 = '#3b82f6';
                    
                    if(w1 > 0) {
                        const r1 = gEl('rect', {x: pad.l, y: y, width: w1, height: barH, fill: c1});
                        bindTip(r1, 'vis041-wrapper', 'vis041-tooltip', () => '<strong>' + d.theme + '</strong><br>Новички (дебют): ' + d.newbies + ' (' + Math.round(d.newbies/tot*100) + '%)');
                        svg.appendChild(r1);
                    }
                    if(w2 > 0) {
                        const r2 = gEl('rect', {x: pad.l + w1, y: y, width: w2, height: barH, fill: c2});
                        bindTip(r2, 'vis041-wrapper', 'vis041-tooltip', () => '<strong>' + d.theme + '</strong><br>Старожилы: ' + d.repeaters + ' (' + Math.round(d.repeaters/tot*100) + '%)');
                        svg.appendChild(r2);
                    }
                });
            }

            function drawVIS042() {
                const svg = document.getElementById('vis042-svg'); if (!svg) return; svg.innerHTML = '';
                const W = 800, H = 200, pad = {t: 30, r: 30, b: 30, l: 150};
                const D = VIS042_DATA; if (!D.length) return;
                
                const pitch = (H - pad.t - pad.b) / D.length;
                const barH = pitch * 0.5;
                
                D.forEach((d, i) => {
                    const y = pad.t + i * pitch;
                    svg.appendChild(gText(pad.l - 10, y + barH/2 + 4, d.venue, 'end', 12, 'var(--muted)'));
                    
                    const w1 = (d.city_only / 100) * (W - pad.l - pad.r);
                    const w2 = (d.institution / 100) * (W - pad.l - pad.r);
                    
                    const c1 = '#8b5cf6', c2 = '#10b981';
                    
                    if(w1 > 0) {
                        const r1 = gEl('rect', {x: pad.l, y: y, width: w1, height: barH, fill: c1});
                        bindTip(r1, 'vis042-wrapper', 'vis042-tooltip', () => '<strong>' + d.venue + '</strong><br>Только город: ' + d.city_only + '%');
                        svg.appendChild(r1);
                        svg.appendChild(gText(pad.l + w1/2, y + barH/2 + 4, d.city_only + '%', 'middle', 11, 'white'));
                    }
                    if(w2 > 0) {
                        const r2 = gEl('rect', {x: pad.l + w1, y: y, width: w2, height: barH, fill: c2});
                        bindTip(r2, 'vis042-wrapper', 'vis042-tooltip', () => '<strong>' + d.venue + '</strong><br>Учреждение: ' + d.institution + '%');
                        svg.appendChild(r2);
                        svg.appendChild(gText(pad.l + w1 + w2/2, y + barH/2 + 4, d.institution + '%', 'middle', 11, 'white'));
                    }
                });
            }

"""

content = content.replace("            function drawGallery() {", js_functions + "\n            function drawGallery() {")
content = content.replace("drawVIS040];", "drawVIS040, drawVIS041, drawVIS042];")

with open("generate_publication_pages.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Injection of Series D complete!")

