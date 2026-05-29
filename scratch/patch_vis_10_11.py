import re

path = 'generate_publication_pages.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Python data extraction logic
py_logic = """
    # --- VIS_010 Geographic Map Data ---
    geo_data = []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT affiliation_text_raw FROM presentation_person WHERE affiliation_text_raw IS NOT NULL AND affiliation_text_raw != ''")
        affs = [row[0] for row in cursor.fetchall()]
        
        cities_meta = {
            "St. Petersburg": {"name_ru": "Санкт-Петербург", "name_en": "St. Petersburg", "lat": 59.9343, "lon": 30.3351, "keys": ["спб", "санкт", "петербург", "st. petersburg", "petersburg", "ленинград", "spb"]},
            "Moscow": {"name_ru": "Москва", "name_en": "Moscow", "lat": 55.7558, "lon": 37.6173, "keys": ["москва", "moscow", "мгу", "ив ран", "вшэ"]},
            "Yekaterinburg": {"name_ru": "Екатеринбург", "name_en": "Yekaterinburg", "lat": 56.8389, "lon": 60.6057, "keys": ["екатеринбург", "урфу", "екб", "ekaterinburg"]},
            "Kazan": {"name_ru": "Казань", "name_en": "Kazan", "lat": 55.7887, "lon": 49.1221, "keys": ["казань", "kazan"]},
            "Hamburg": {"name_ru": "Гамбург", "name_en": "Hamburg", "lat": 53.5511, "lon": 9.9937, "keys": ["гамбург", "hamburg"]},
            "Novosibirsk": {"name_ru": "Новосибирск", "name_en": "Novosibirsk", "lat": 55.0084, "lon": 82.9357, "keys": ["новосибирск", "novosibirsk"]},
            "Elista": {"name_ru": "Элиста", "name_en": "Elista", "lat": 46.3078, "lon": 44.2558, "keys": ["элиста", "elista", "калм"]},
            "Kyiv": {"name_ru": "Киев", "name_en": "Kyiv", "lat": 50.4501, "lon": 30.5234, "keys": ["киев", "kyiv", "kiev"]},
            "Vienna": {"name_ru": "Вена", "name_en": "Vienna", "lat": 48.2082, "lon": 16.3738, "keys": ["вена", "vienna"]},
            "Delhi": {"name_ru": "Дели", "name_en": "Delhi", "lat": 28.6139, "lon": 77.2090, "keys": ["дели", "delhi"]},
            "Ulan-Ude": {"name_ru": "Улан-Удэ", "name_en": "Ulan-Ude", "lat": 51.8292, "lon": 107.6067, "keys": ["улан-удэ", "ulan-ude", "имбт", "бнц"]}
        }
        
        city_counts = defaultdict(int)
        for aff in affs:
            low = aff.lower()
            for city_key, meta in cities_meta.items():
                if any(k in low for k in meta["keys"]):
                    city_counts[city_key] += 1
                    break
                    
        for city_key, count in city_counts.items():
            meta = cities_meta[city_key]
            geo_data.append({
                "city": city_key,
                "name_ru": meta["name_ru"],
                "name_en": meta["name_en"],
                "lat": meta["lat"],
                "lon": meta["lon"],
                "count": count
            })
        conn.close()
    except Exception as ex:
        print(f"Error querying geo data: {ex}")
    serialized_geo = json.dumps(geo_data, ensure_ascii=False)

    # --- VIS_011 Keyword Bubble Cloud Data ---
    bubble_data = []
    try:
        import csv
        c = defaultdict(int)
        with open("analytics_output/expanded_classification_deepseek.csv", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                val = row.get("meso_codes")
                if val:
                    for code in val.split('|'):
                        c[code.strip()] += 1
                        
        # clean names mapping
        clean_names = {
            "buddhist_studies": {"ru": "Буддология", "en": "Buddhist Studies"},
            "philosophy_epistemology": {"ru": "Философия и эпистемология", "en": "Philosophy & Epistemology"},
            "vedic_studies": {"ru": "Ведийские исследования", "en": "Vedic Studies"},
            "comparative_analysis": {"ru": "Сравнительный анализ", "en": "Comparative Analysis"},
            "tibetology_himalaya": {"ru": "Тибетология и Гималаи", "en": "Tibetology & Himalayas"},
            "epic_ramayana_mahabharata": {"ru": "Эпос (Рамаяна/Махабхарата)", "en": "Epic (Ramayana/Mahabharata)"},
            "dravidology_south_india": {"ru": "Дравидология и Южная Индия", "en": "Dravidology & South India"},
            "history_of_indology": {"ru": "История индологии", "en": "History of Indology"},
            "visual_material_culture": {"ru": "Визуальная культура", "en": "Visual Culture"},
            "ritual_studies": {"ru": "Исследования ритуалов", "en": "Ritual Studies"},
            "bengal": {"ru": "Бенгалистика", "en": "Bengali Studies"},
            "bhakti_vaishnava": {"ru": "Бхакти и вишнуизм", "en": "Bhakti & Vaishnavism"},
            "sanskrit_grammar_panini": {"ru": "Санскритская грамматика", "en": "Sanskrit Grammar"},
            "ethnography_performance": {"ru": "Этнография и театр", "en": "Ethnography & Performance"},
            "literary_studies": {"ru": "Литературоведение", "en": "Literary Studies"},
            "nepal_newar_kathmandu": {"ru": "Непал и долина Катманду", "en": "Nepal & Kathmandu"},
            "manuscripts_epigraphy": {"ru": "Рукописи и эпиграфика", "en": "Manuscripts & Epigraphy"},
            "translation_reception": {"ru": "Перевод и рецепция", "en": "Translation & Reception"},
            "modern_society_politics": {"ru": "Политика и общество", "en": "Politics & Society"},
            "colonial_encounters": {"ru": "Колониальный период", "en": "Colonial Encounters"}
        }
        
        for k, v in c.items():
            if k in clean_names:
                bubble_data.append({
                    "id": k,
                    "name_ru": clean_names[k]["ru"],
                    "name_en": clean_names[k]["en"],
                    "value": v
                })
    except Exception as ex:
        print(f"Error querying bubble data: {ex}")
    serialized_bubble = json.dumps(bubble_data, ensure_ascii=False)
"""

content = content.replace('    serialized_arc = json.dumps({"nodes": arc_nodes, "links": arc_links}, ensure_ascii=False)', '    serialized_arc = json.dumps({"nodes": arc_nodes, "links": arc_links}, ensure_ascii=False)\n' + py_logic)

# 2. HTML block to inject
html_block = """
        <!-- VIS_010_geographic_map -->
        <section class="viz-showcase-section" id="VIS_010_geographic_map">
            <h2>
                <span class="viz-id-badge">VIS_010</span>
                <span class="bilingual-text" data-ru="Географическая карта аффилиаций" data-en="Geospatial Affiliation Map">Географическая карта аффилиаций</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="География участников индологических конференций. Размер пузырьков отображает общее число докладов от исследователей из этих городов." data-en="Geography of Indology scholars. Bubble sizes represent the total number of presentations given by researchers based in these cities.">География участников индологических конференций.</p>
            <div id="geo-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:2rem;">
                <svg id="geo-svg" viewBox="0 0 800 450" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="geo-tooltip" style="position: absolute; background: rgba(18, 18, 24, 0.95); border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 8px; padding: 0.8rem 1rem; font-size: 0.85rem; color: #fff; pointer-events: none; opacity: 0; transition: opacity 0.15s ease; z-index: 1000; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5); backdrop-filter: blur(4px);"></div>
            </div>
        </section>

        <!-- VIS_011_keyword_bubble_cloud -->
        <section class="viz-showcase-section" id="VIS_011_keyword_bubble_cloud">
            <h2>
                <span class="viz-id-badge">VIS_011</span>
                <span class="bilingual-text" data-ru="Динамическое облако тем" data-en="Dynamic Theme Bubble Cloud">Динамическое облако тем</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Узкие исследовательские направления, упакованные по плотности. Размер пузырьков отражает общее количество докладов в этой области." data-en="Packed visualization of narrow research fields. Bubble sizes reflect the total number of presentations in each field.">Узкие исследовательские направления, упакованные по плотности.</p>
            <div id="bubble-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:2rem;">
                <svg id="bubble-svg" viewBox="0 0 800 500" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="bubble-tooltip" style="position: absolute; background: rgba(18, 18, 24, 0.95); border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 8px; padding: 0.8rem 1rem; font-size: 0.85rem; color: #fff; pointer-events: none; opacity: 0; transition: opacity 0.15s ease; z-index: 1000; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5); backdrop-filter: blur(4px);"></div>
            </div>
        </section>
"""

content = content.replace('        <hr style="border:0; border-top:1px solid rgba(255,255,255,0.08); margin:3rem 0 2rem;">', html_block + '\n        <hr style="border:0; border-top:1px solid rgba(255,255,255,0.08); margin:3rem 0 2rem;">')

# 3. JS Data & Rendering logic
js_logic = """
            const GEO_DATA = """ + '""" + serialized_geo + """' + """;
            const BUBBLE_DATA = """ + '""" + serialized_bubble + """' + """;

            function drawGeoMap() {
                const svg = document.getElementById('geo-svg');
                if (!svg || !GEO_DATA) return;
                svg.innerHTML = '';
                
                const width = 800;
                const height = 450;
                const padding = { top: 40, right: 40, bottom: 40, left: 60 };
                
                // Lon from 0 to 120, Lat from 25 to 65
                const minLon = 0, maxLon = 120;
                const minLat = 25, maxLat = 65;
                
                const getX = (lon) => padding.left + (lon - minLon) / (maxLon - minLon) * (width - padding.left - padding.right);
                const getY = (lat) => height - padding.bottom - (lat - minLat) / (maxLat - minLat) * (height - padding.top - padding.bottom);
                
                const tooltip = document.getElementById('geo-tooltip');
                
                // Draw grid lines
                for (let lon = 20; lon <= 100; lon += 20) {
                    const x = getX(lon);
                    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                    line.setAttribute('x1', x);
                    line.setAttribute('y1', padding.top);
                    line.setAttribute('x2', x);
                    line.setAttribute('y2', height - padding.bottom);
                    line.setAttribute('stroke', 'rgba(255,255,255,0.04)');
                    line.setAttribute('stroke-dasharray', '2,4');
                    svg.appendChild(line);
                    
                    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    label.setAttribute('x', x);
                    label.setAttribute('y', height - padding.bottom + 15);
                    label.setAttribute('fill', 'var(--muted)');
                    label.setAttribute('font-size', '9px');
                    label.setAttribute('text-anchor', 'middle');
                    label.textContent = lon + '°E';
                    svg.appendChild(label);
                }
                for (let lat = 30; lat <= 60; lat += 10) {
                    const y = getY(lat);
                    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                    line.setAttribute('x1', padding.left);
                    line.setAttribute('y1', y);
                    line.setAttribute('x2', width - padding.right);
                    line.setAttribute('y2', y);
                    line.setAttribute('stroke', 'rgba(255,255,255,0.04)');
                    line.setAttribute('stroke-dasharray', '2,4');
                    svg.appendChild(line);
                    
                    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    label.setAttribute('x', padding.left - 10);
                    label.setAttribute('y', y + 3);
                    label.setAttribute('fill', 'var(--muted)');
                    label.setAttribute('font-size', '9px');
                    label.setAttribute('text-anchor', 'end');
                    label.textContent = lat + '°N';
                    svg.appendChild(label);
                }
                
                // Draw Cities
                GEO_DATA.forEach(d => {
                    const cx = getX(d.lon);
                    const cy = getY(d.lat);
                    const r = 5 + Math.sqrt(d.count) * 2;
                    
                    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                    circle.setAttribute('cx', cx);
                    circle.setAttribute('cy', cy);
                    circle.setAttribute('r', r);
                    circle.setAttribute('fill', 'var(--accent2)');
                    circle.setAttribute('fill-opacity', '0.6');
                    circle.setAttribute('stroke', '#fff');
                    circle.setAttribute('stroke-width', '1');
                    circle.setAttribute('stroke-opacity', '0.4');
                    circle.style.cursor = 'pointer';
                    circle.style.transition = 'all 0.2s ease';
                    
                    circle.addEventListener('mouseenter', () => {
                        circle.setAttribute('fill-opacity', '0.9');
                        circle.setAttribute('stroke-width', '2');
                        circle.setAttribute('stroke-opacity', '1');
                        tooltip.style.opacity = '1';
                        const name = currentLang === 'ru' ? d.name_ru : d.name_en;
                        tooltip.innerHTML = `<strong>${name}</strong><br/>Координаты: ${d.lat.toFixed(2)}°N, ${d.lon.toFixed(2)}°E<br/>Докладов: ${d.count}`;
                    });
                    circle.addEventListener('mousemove', (e) => {
                        const container = document.getElementById('geo-wrapper').getBoundingClientRect();
                        tooltip.style.left = (e.clientX - container.left + 15) + 'px';
                        tooltip.style.top = (e.clientY - container.top - 30) + 'px';
                    });
                    circle.addEventListener('mouseleave', () => {
                        circle.setAttribute('fill-opacity', '0.6');
                        circle.setAttribute('stroke-width', '1');
                        circle.setAttribute('stroke-opacity', '0.4');
                        tooltip.style.opacity = '0';
                    });
                    svg.appendChild(circle);
                    
                    // Draw name label
                    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    label.setAttribute('x', cx);
                    label.setAttribute('y', cy - r - 5);
                    label.setAttribute('fill', 'rgba(255,255,255,0.85)');
                    label.setAttribute('font-size', '10px');
                    label.setAttribute('text-anchor', 'middle');
                    label.style.pointerEvents = 'none';
                    label.textContent = currentLang === 'ru' ? d.name_ru : d.name_en;
                    svg.appendChild(label);
                });
            }

            function drawBubbleCloud() {
                const svg = document.getElementById('bubble-svg');
                if (!svg || !BUBBLE_DATA) return;
                svg.innerHTML = '';
                
                const width = 800;
                const height = 500;
                const center = { x: width / 2, y: height / 2 };
                
                // scale & packing logic
                const bubbles = BUBBLE_DATA.map(d => ({
                    id: d.id,
                    name_ru: d.name_ru,
                    name_en: d.name_en,
                    value: d.value,
                    r: 15 + Math.sqrt(d.value) * 3
                })).sort((a, b) => b.r - a.r);
                
                const placed = [];
                bubbles.forEach(b => {
                    let angle = 0;
                    let radius = 0;
                    let found = false;
                    
                    while (!found && radius < 400) {
                        const cx = center.x + radius * Math.cos(angle);
                        const cy = center.y + radius * Math.sin(angle);
                        
                        let collision = false;
                        for (let i = 0; i < placed.length; i++) {
                            const other = placed[i];
                            const dx = cx - other.x;
                            const dy = cy - other.y;
                            const dist = Math.sqrt(dx*dx + dy*dy);
                            if (dist < b.r + other.r + 3) {
                                collision = true;
                                break;
                            }
                        }
                        
                        if (!collision) {
                            b.x = cx;
                            b.y = cy;
                            placed.push(b);
                            found = true;
                        }
                        angle += 0.15;
                        radius += 0.35;
                    }
                });
                
                const tooltip = document.getElementById('bubble-tooltip');
                const colors = ['#2b82c9', '#b83280', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#3b82f6'];
                
                placed.forEach((b, idx) => {
                    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
                    
                    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                    circle.setAttribute('cx', b.x);
                    circle.setAttribute('cy', b.y);
                    circle.setAttribute('r', b.r);
                    circle.setAttribute('fill', colors[idx % colors.length]);
                    circle.setAttribute('fill-opacity', '0.6');
                    circle.setAttribute('stroke', '#fff');
                    circle.setAttribute('stroke-width', '1.5');
                    circle.setAttribute('stroke-opacity', '0.3');
                    circle.style.cursor = 'pointer';
                    circle.style.transition = 'all 0.2s ease';
                    
                    circle.addEventListener('mouseenter', () => {
                        circle.setAttribute('fill-opacity', '0.85');
                        circle.setAttribute('stroke-opacity', '1');
                        tooltip.style.opacity = '1';
                        const name = currentLang === 'ru' ? b.name_ru : b.name_en;
                        tooltip.innerHTML = `<strong>${name}</strong><br/>Код: ${b.id}<br/>Докладов: ${b.value}`;
                    });
                    circle.addEventListener('mousemove', (e) => {
                        const container = document.getElementById('bubble-wrapper').getBoundingClientRect();
                        tooltip.style.left = (e.clientX - container.left + 15) + 'px';
                        tooltip.style.top = (e.clientY - container.top - 30) + 'px';
                    });
                    circle.addEventListener('mouseleave', () => {
                        circle.setAttribute('fill-opacity', '0.6');
                        circle.setAttribute('stroke-opacity', '0.3');
                        tooltip.style.opacity = '0';
                    });
                    
                    g.appendChild(circle);
                    
                    // Draw name inside bubble
                    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    text.setAttribute('x', b.x);
                    text.setAttribute('y', b.y + 4);
                    text.setAttribute('fill', '#fff');
                    text.setAttribute('font-size', b.r > 35 ? '10px' : '8px');
                    text.setAttribute('text-anchor', 'middle');
                    text.style.pointerEvents = 'none';
                    
                    const name = currentLang === 'ru' ? b.name_ru : b.name_en;
                    let label = name;
                    if (label.length * 5 > b.r * 2) {
                        label = label.substring(0, Math.floor(b.r*2 / 5) - 1) + '…';
                    }
                    text.textContent = label;
                    
                    g.appendChild(text);
                    svg.appendChild(g);
                });
            }
"""

content = content.replace("            function drawArc() {", js_logic + "\n            function drawArc() {")

content = content.replace("drawArc();", "drawArc();\n                drawGeoMap();\n                drawBubbleCloud();")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched VIS_010 and VIS_011 into " + path)
