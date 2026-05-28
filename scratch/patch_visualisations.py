import re

path = 'generate_publication_pages.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Insert Python data extraction logic
py_logic = """
    # --- VIS_003 Heatmap Data ---
    heatmap_data = []
    all_years = []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(\"\"\"
            SELECT e.year, es.series_name_en, COUNT(m.media_id)
            FROM presentation p
            JOIN session s ON p.session_id = s.session_id
            JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
            JOIN event_day ed ON edv.event_day_id = ed.event_day_id
            JOIN event e ON ed.event_id = e.event_id
            JOIN event_series es ON e.event_series_id = es.event_series_id
            JOIN media m ON m.attached_to_id = p.presentation_id AND m.attached_to_type = 'presentation'
            WHERE m.media_type = 'video' OR m.media_type = 'youtube'
            GROUP BY e.year, es.series_name_en
        \"\"\")
        for year, series, count in cursor.fetchall():
            group = "zograf" if "zograf" in series.lower() else "roerich"
            heatmap_data.append({"y": year, "g": group, "c": count})
            
        cursor.execute("SELECT DISTINCT year FROM event ORDER BY year")
        all_years = [r[0] for r in cursor.fetchall()]
        conn.close()
    except Exception as ex:
        print(f"Error querying heatmap data: {ex}")
        
    serialized_heatmap = json.dumps({"years": all_years, "data": heatmap_data}, ensure_ascii=False)

    # --- VIS_004 Alluvial Data ---
    alluvial_nodes = []
    alluvial_links = []
    try:
        period_theme_links = defaultdict(int)
        theme_meso_links = defaultdict(int)
        with open("analytics_output/expanded_classification_deepseek.csv", encoding="utf-8") as f:
            import csv
            reader = csv.DictReader(f)
            for row in reader:
                period = row.get("period_l2")
                theme = row.get("theme_l1")
                meso = row.get("meso_codes") or row.get("proposed_meso")
                
                if not period or period == "unspecified": period = "Unknown"
                if not theme or theme == "unspecified": theme = "Unknown"
                if not meso or meso == "unspecified": meso = "Other"
                
                meso = meso.split(',')[0].strip()
                period_theme_links[(period, theme)] += 1
                theme_meso_links[(theme, meso)] += 1

        node_indices = {}
        def get_node(name, group):
            key = (name, group)
            if key not in node_indices:
                node_indices[key] = len(alluvial_nodes)
                alluvial_nodes.append({"name": name, "group": group})
            return node_indices[key]

        for (p, t), v in period_theme_links.items():
            if v >= 2:
                alluvial_links.append({"source": get_node(p, "period"), "target": get_node(t, "theme"), "value": v})
        for (t, m), v in theme_meso_links.items():
            if v >= 5:
                alluvial_links.append({"source": get_node(t, "theme"), "target": get_node(m, "meso"), "value": v})
    except Exception as ex:
        print(f"Error reading alluvial data: {ex}")
        
    serialized_alluvial = json.dumps({"nodes": alluvial_nodes, "links": alluvial_links}, ensure_ascii=False)
"""

content = content.replace("    serialized_opacity = json.dumps(opacity_data, ensure_ascii=False)", "    serialized_opacity = json.dumps(opacity_data, ensure_ascii=False)\n" + py_logic)

# 2. Replace HTML placeholders
heatmap_html = """
            <div id="heatmap-wrapper" style="position:relative; width:100%; overflow:hidden;">
                <svg id="heatmap-svg" viewBox="0 0 800 250" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="heatmap-tooltip" style="position: absolute; background: rgba(18, 18, 24, 0.95); border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 8px; padding: 0.8rem 1rem; font-size: 0.85rem; color: #fff; pointer-events: none; opacity: 0; transition: opacity 0.15s ease; z-index: 1000; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5); backdrop-filter: blur(4px);"></div>
            </div>
            <div class="legend-container">
                <div class="legend-item">
                    <span class="legend-color" style="background:#2b82c9;"></span>
                    <span class="bilingual-text" data-ru="Зографские чтения" data-en="Zograf Readings">Зографские чтения</span>
                </div>
                <div class="legend-item">
                    <span class="legend-color" style="background:#b83280;"></span>
                    <span class="bilingual-text" data-ru="Рериховские чтения" data-en="Roerich Readings">Рериховские чтения</span>
                </div>
            </div>
"""

alluvial_html = """
            <div id="alluvial-wrapper" style="position:relative; width:100%; overflow:hidden;">
                <svg id="alluvial-svg" viewBox="0 0 800 500" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="alluvial-tooltip" style="position: absolute; background: rgba(18, 18, 24, 0.95); border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 8px; padding: 0.8rem 1rem; font-size: 0.85rem; color: #fff; pointer-events: none; opacity: 0; transition: opacity 0.15s ease; z-index: 1000; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5); backdrop-filter: blur(4px);"></div>
            </div>
"""

content = re.sub(r'<div class="placeholder-viz">\s*<span class="bilingual-text" data-ru="\[ Тепловая карта покрытия в процессе разработки \]".*?</span>\s*</div>', heatmap_html, content, flags=re.DOTALL)
content = re.sub(r'<div class="placeholder-viz">\s*<span class="bilingual-text" data-ru="\[ Аллювиальная диаграмма потоков в процессе разработки \]".*?</span>\s*</div>', alluvial_html, content, flags=re.DOTALL)


# 3. Insert JS logic
js_injection = """
            const HEATMAP_DATA = """ + '""" + serialized_heatmap + """' + """;
            const ALLUVIAL_DATA = """ + '""" + serialized_alluvial + """' + """;

            function drawHeatmap() {
                const svg = document.getElementById('heatmap-svg');
                if (!svg || !HEATMAP_DATA.years) return;
                svg.innerHTML = '';
                
                const width = 800;
                const height = 250;
                const padding = { top: 30, right: 30, bottom: 40, left: 100 };
                
                const years = HEATMAP_DATA.years;
                const minYear = Math.min(...years);
                const maxYear = Math.max(...years);
                
                const cellW = (width - padding.left - padding.right) / (maxYear - minYear + 1);
                const cellH = (height - padding.top - padding.bottom) / 2;
                
                // Labels
                const yLabels = [
                    { id: 'zograf', name: currentLang === 'ru' ? 'Зограф' : 'Zograf', y: padding.top + cellH * 0.5 },
                    { id: 'roerich', name: currentLang === 'ru' ? 'Рерих' : 'Roerich', y: padding.top + cellH * 1.5 }
                ];
                yLabels.forEach(lbl => {
                    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    text.setAttribute('x', padding.left - 15);
                    text.setAttribute('y', lbl.y + 4);
                    text.setAttribute('text-anchor', 'end');
                    text.setAttribute('fill', 'var(--muted)');
                    text.setAttribute('font-size', '12px');
                    text.textContent = lbl.name;
                    svg.appendChild(text);
                });
                
                const tooltip = document.getElementById('heatmap-tooltip');
                
                // Draw cells
                for (let y = minYear; y <= maxYear; y++) {
                    const x = padding.left + (y - minYear) * cellW;
                    
                    // Year label (every 2 years)
                    if (y % 2 === 0) {
                        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                        text.setAttribute('x', x + cellW/2);
                        text.setAttribute('y', height - padding.bottom + 20);
                        text.setAttribute('text-anchor', 'middle');
                        text.setAttribute('fill', 'var(--muted)');
                        text.setAttribute('font-size', '10px');
                        text.textContent = y;
                        svg.appendChild(text);
                    }
                    
                    ['zograf', 'roerich'].forEach((group, idx) => {
                        const cy = padding.top + idx * cellH;
                        const dataPoint = HEATMAP_DATA.data.find(d => d.y === y && d.g === group);
                        const count = dataPoint ? dataPoint.c : 0;
                        
                        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                        rect.setAttribute('x', x + 2);
                        rect.setAttribute('y', cy + 2);
                        rect.setAttribute('width', cellW - 4);
                        rect.setAttribute('height', cellH - 4);
                        rect.setAttribute('rx', 4);
                        
                        if (count > 0) {
                            rect.setAttribute('fill', group === 'zograf' ? '#2b82c9' : '#b83280');
                            rect.setAttribute('fill-opacity', 0.2 + Math.min(count / 10, 0.8));
                            rect.setAttribute('cursor', 'pointer');
                            
                            rect.addEventListener('mouseenter', () => {
                                rect.setAttribute('stroke', '#fff');
                                tooltip.style.opacity = '1';
                                tooltip.innerHTML = `<strong>${group === 'zograf' ? 'Зографские чтения' : 'Рериховские чтения'} (${y})</strong><br/>Видеозаписей: ${count}`;
                            });
                            rect.addEventListener('mousemove', (e) => {
                                const container = document.getElementById('heatmap-wrapper').getBoundingClientRect();
                                tooltip.style.left = (e.clientX - container.left + 15) + 'px';
                                tooltip.style.top = (e.clientY - container.top - 30) + 'px';
                            });
                            rect.addEventListener('mouseleave', () => {
                                rect.removeAttribute('stroke');
                                tooltip.style.opacity = '0';
                            });
                        } else {
                            rect.setAttribute('fill', 'rgba(255,255,255,0.03)');
                        }
                        
                        svg.appendChild(rect);
                    });
                }
            }

            function drawAlluvial() {
                const svg = document.getElementById('alluvial-svg');
                if (!svg || !ALLUVIAL_DATA.nodes) return;
                svg.innerHTML = '';
                
                const width = 800;
                const height = 500;
                const padding = { top: 40, right: 120, bottom: 20, left: 120 };
                
                const nodes = ALLUVIAL_DATA.nodes.map(n => ({...n, value: 0, sourceLinks: [], targetLinks: []}));
                const links = ALLUVIAL_DATA.links.map(l => ({...l}));
                
                links.forEach(l => {
                    nodes[l.source].sourceLinks.push(l);
                    nodes[l.target].targetLinks.push(l);
                    nodes[l.source].value += l.value;
                    nodes[l.target].value += l.value;
                });
                
                const groups = ['period', 'theme', 'meso'];
                const groupX = {
                    'period': padding.left,
                    'theme': width / 2,
                    'meso': width - padding.right
                };
                
                const yOffsets = { 'period': padding.top, 'theme': padding.top, 'meso': padding.top };
                const nodeHeightFactor = 3;
                
                // Group nodes and assign positions
                groups.forEach(g => {
                    const gNodes = nodes.filter(n => n.group === g).sort((a,b) => b.value - a.value);
                    gNodes.forEach(n => {
                        n.x = groupX[g];
                        n.y = yOffsets[g];
                        n.dy = n.value * nodeHeightFactor;
                        yOffsets[g] += n.dy + 15; // gap
                    });
                    
                    // Center vertically
                    const totalH = yOffsets[g] - padding.top - 15;
                    const shiftY = (height - padding.top - padding.bottom - totalH) / 2;
                    gNodes.forEach(n => n.y += Math.max(0, shiftY));
                });
                
                // Link positions
                nodes.forEach(n => {
                    let sy = n.y;
                    n.sourceLinks.sort((a,b) => nodes[b.target].y - nodes[a.target].y).forEach(l => {
                        l.sy = sy;
                        sy += l.value * nodeHeightFactor;
                    });
                    let ty = n.y;
                    n.targetLinks.sort((a,b) => nodes[b.source].y - nodes[a.source].y).forEach(l => {
                        l.ty = ty;
                        ty += l.value * nodeHeightFactor;
                    });
                });
                
                const tooltip = document.getElementById('alluvial-tooltip');
                
                // Draw Links
                links.forEach(l => {
                    const s = nodes[l.source];
                    const t = nodes[l.target];
                    const lWidth = l.value * nodeHeightFactor;
                    
                    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                    const curve = (s.x + 10 + t.x) / 2;
                    const d = `M ${s.x + 10} ${l.sy + lWidth/2} C ${curve} ${l.sy + lWidth/2}, ${curve} ${l.ty + lWidth/2}, ${t.x} ${l.ty + lWidth/2}`;
                    
                    path.setAttribute('d', d);
                    path.setAttribute('fill', 'none');
                    path.setAttribute('stroke', 'rgba(255,255,255,0.15)');
                    path.setAttribute('stroke-width', Math.max(1, lWidth));
                    path.setAttribute('class', 'alluvial-link');
                    path.style.cursor = 'pointer';
                    path.style.transition = 'stroke 0.2s';
                    
                    path.addEventListener('mouseenter', () => {
                        path.setAttribute('stroke', 'var(--accent)');
                        path.setAttribute('stroke-opacity', '0.6');
                        tooltip.style.opacity = '1';
                        tooltip.innerHTML = `<strong>${s.name} → ${t.name}</strong><br/>Связей: ${l.value}`;
                    });
                    path.addEventListener('mousemove', (e) => {
                        const container = document.getElementById('alluvial-wrapper').getBoundingClientRect();
                        tooltip.style.left = (e.clientX - container.left + 15) + 'px';
                        tooltip.style.top = (e.clientY - container.top - 30) + 'px';
                    });
                    path.addEventListener('mouseleave', () => {
                        path.setAttribute('stroke', 'rgba(255,255,255,0.15)');
                        tooltip.style.opacity = '0';
                    });
                    
                    svg.appendChild(path);
                });
                
                // Draw Nodes
                nodes.forEach(n => {
                    if (n.value === 0) return;
                    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                    rect.setAttribute('x', n.x);
                    rect.setAttribute('y', n.y);
                    rect.setAttribute('width', 10);
                    rect.setAttribute('height', n.dy);
                    rect.setAttribute('fill', 'var(--accent2)');
                    rect.setAttribute('rx', 2);
                    svg.appendChild(rect);
                    
                    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    text.setAttribute('y', n.y + n.dy / 2 + 4);
                    text.setAttribute('fill', '#fff');
                    text.setAttribute('font-size', '11px');
                    
                    if (n.group === 'meso') {
                        text.setAttribute('x', n.x + 15);
                        text.setAttribute('text-anchor', 'start');
                    } else if (n.group === 'period') {
                        text.setAttribute('x', n.x - 5);
                        text.setAttribute('text-anchor', 'end');
                    } else {
                        text.setAttribute('x', n.x + 15);
                        text.setAttribute('text-anchor', 'start');
                    }
                    
                    text.textContent = n.name;
                    svg.appendChild(text);
                });
            }
"""

content = content.replace("const OPACITY_DATA = ", js_injection + "\n            const OPACITY_DATA = ")

# Wait, drawOpacityChart(); is at the end of setLanguage. Let's find exactly the pattern inside `generate_publication_pages.py`.
# Let's replace:
old_set_language_call = """drawScatter();
                drawOpacityChart();
            }"""

new_set_language_call = """drawScatter();
                drawOpacityChart();
                drawHeatmap();
                drawAlluvial();
            }"""

if old_set_language_call in content:
    content = content.replace(old_set_language_call, new_set_language_call)
else:
    print("WARNING: Could not find setLanguage calls to inject new draw functions.")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched " + path)
