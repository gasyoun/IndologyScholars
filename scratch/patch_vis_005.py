import re

path = 'generate_publication_pages.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

py_logic = """
    # --- VIS_005 Scholar Forest Data ---
    forest_data = []
    top_scholars = []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get top 40 scholars
        cursor.execute(\"\"\"
            SELECT per.display_name, COUNT(p.presentation_id) as total
            FROM presentation p
            JOIN presentation_person pp ON p.presentation_id = pp.presentation_id
            JOIN person per ON pp.person_id = per.person_id
            GROUP BY per.person_id
            ORDER BY total DESC
            LIMIT 40
        \"\"\")
        top_scholars = [row[0] for row in cursor.fetchall()]
        
        # Get counts per year for these scholars
        cursor.execute(\"\"\"
            SELECT per.display_name, e.year, COUNT(p.presentation_id)
            FROM presentation p
            JOIN presentation_person pp ON p.presentation_id = pp.presentation_id
            JOIN person per ON pp.person_id = per.person_id
            JOIN session s ON p.session_id = s.session_id
            JOIN event_day_venue edv ON s.event_day_venue_id = edv.event_day_venue_id
            JOIN event_day ed ON edv.event_day_id = ed.event_day_id
            JOIN event e ON ed.event_id = e.event_id
            WHERE per.display_name IN ({seq})
            GROUP BY per.person_id, e.year
        \"\"\".format(seq=','.join(['?']*len(top_scholars))), top_scholars)
        
        for name, year, count in cursor.fetchall():
            forest_data.append({"s": name, "y": year, "c": count})
            
        conn.close()
    except Exception as ex:
        print(f"Error querying forest data: {ex}")
        
    serialized_forest = json.dumps({"scholars": top_scholars, "years": all_years, "data": forest_data}, ensure_ascii=False)
"""

content = content.replace("    serialized_alluvial = json.dumps({\"nodes\": alluvial_nodes, \"links\": alluvial_links}, ensure_ascii=False)", "    serialized_alluvial = json.dumps({\"nodes\": alluvial_nodes, \"links\": alluvial_links}, ensure_ascii=False)\n" + py_logic)

html_block = """
        <!-- VIS_005_scholar_forest -->
        <section class="viz-showcase-section" id="VIS_005_scholar_forest">
            <h2>
                <span class="viz-id-badge">VIS_005</span>
                <span class="bilingual-text" data-ru="«Лес» активности исследователей" data-en="Scholar Activity Forest">«Лес» активности исследователей</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Жизненный цикл академических карьер топ-40 самых активных докладчиков за всю историю конференций." data-en="The academic lifecycle of the top 40 most active speakers across the history of the conferences.">Жизненный цикл академических карьер топ-40 самых активных докладчиков за всю историю конференций.</p>
            <div id="forest-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:2rem;">
                <svg id="forest-svg" viewBox="0 0 800 800" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="forest-tooltip" style="position: absolute; background: rgba(18, 18, 24, 0.95); border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 8px; padding: 0.8rem 1rem; font-size: 0.85rem; color: #fff; pointer-events: none; opacity: 0; transition: opacity 0.15s ease; z-index: 1000; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5); backdrop-filter: blur(4px);"></div>
            </div>
        </section>
"""

# Insert HTML after alluvial block
content = content.replace('            <div id="alluvial-wrapper" style="position:relative; width:100%; overflow:hidden;">', html_block + '\n            <div id="alluvial-wrapper" style="position:relative; width:100%; overflow:hidden;">')

js_injection = """
            const FOREST_DATA = """ + '""" + serialized_forest + """' + """;

            function drawForest() {
                const svg = document.getElementById('forest-svg');
                if (!svg || !FOREST_DATA.scholars) return;
                svg.innerHTML = '';
                
                const width = 800;
                const height = 800;
                const padding = { top: 40, right: 30, bottom: 40, left: 160 };
                
                const years = FOREST_DATA.years;
                const minYear = Math.min(...years);
                const maxYear = Math.max(...years);
                const scholars = FOREST_DATA.scholars;
                
                const cellW = (width - padding.left - padding.right) / (maxYear - minYear);
                const rowH = (height - padding.top - padding.bottom) / scholars.length;
                
                // Draw X Axis (Years)
                for (let y = minYear; y <= maxYear; y++) {
                    const x = padding.left + (y - minYear) * cellW;
                    if (y % 2 === 0) {
                        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                        text.setAttribute('x', x);
                        text.setAttribute('y', padding.top - 10);
                        text.setAttribute('text-anchor', 'middle');
                        text.setAttribute('fill', 'var(--muted)');
                        text.setAttribute('font-size', '10px');
                        text.textContent = y;
                        svg.appendChild(text);
                        
                        // Grid line
                        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                        line.setAttribute('x1', x);
                        line.setAttribute('y1', padding.top);
                        line.setAttribute('x2', x);
                        line.setAttribute('y2', height - padding.bottom);
                        line.setAttribute('stroke', 'rgba(255,255,255,0.05)');
                        line.setAttribute('stroke-dasharray', '4,4');
                        svg.appendChild(line);
                    }
                }
                
                const tooltip = document.getElementById('forest-tooltip');
                
                // Draw rows
                scholars.forEach((scholar, idx) => {
                    const cy = padding.top + idx * rowH + rowH / 2;
                    
                    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    label.setAttribute('x', padding.left - 10);
                    label.setAttribute('y', cy + 4);
                    label.setAttribute('text-anchor', 'end');
                    label.setAttribute('fill', 'rgba(255,255,255,0.7)');
                    label.setAttribute('font-size', '11px');
                    // simple truncation if too long
                    label.textContent = scholar.length > 25 ? scholar.substring(0,22) + '...' : scholar;
                    svg.appendChild(label);
                    
                    // Base line
                    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                    line.setAttribute('x1', padding.left);
                    line.setAttribute('y1', cy);
                    line.setAttribute('x2', width - padding.right);
                    line.setAttribute('y2', cy);
                    line.setAttribute('stroke', 'rgba(255,255,255,0.05)');
                    svg.appendChild(line);
                    
                    // Draw activity points
                    const points = FOREST_DATA.data.filter(d => d.s === scholar);
                    let pathD = `M ${padding.left} ${cy}`;
                    
                    for (let y = minYear; y <= maxYear; y++) {
                        const pt = points.find(p => p.y === y);
                        const count = pt ? pt.c : 0;
                        const x = padding.left + (y - minYear) * cellW;
                        
                        if (count > 0) {
                            const r = Math.min(rowH * 0.8, 3 + count * 2);
                            const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                            circle.setAttribute('cx', x);
                            circle.setAttribute('cy', cy);
                            circle.setAttribute('r', r);
                            circle.setAttribute('fill', 'var(--accent)');
                            circle.setAttribute('fill-opacity', '0.6');
                            circle.setAttribute('cursor', 'pointer');
                            circle.style.transition = 'all 0.2s';
                            
                            circle.addEventListener('mouseenter', () => {
                                circle.setAttribute('fill-opacity', '1');
                                circle.setAttribute('stroke', '#fff');
                                tooltip.style.opacity = '1';
                                tooltip.innerHTML = `<strong>${scholar}</strong><br/>Год: ${y}<br/>Докладов: ${count}`;
                            });
                            circle.addEventListener('mousemove', (e) => {
                                const container = document.getElementById('forest-wrapper').getBoundingClientRect();
                                tooltip.style.left = (e.clientX - container.left + 15) + 'px';
                                tooltip.style.top = (e.clientY - container.top - 30) + 'px';
                            });
                            circle.addEventListener('mouseleave', () => {
                                circle.setAttribute('fill-opacity', '0.6');
                                circle.removeAttribute('stroke');
                                tooltip.style.opacity = '0';
                            });
                            
                            svg.appendChild(circle);
                        }
                    }
                });
            }
"""

content = content.replace("const ALLUVIAL_DATA = ", js_injection + "\n            const ALLUVIAL_DATA = ")

content = content.replace("drawHeatmap();", "drawHeatmap();\n                drawForest();")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched VIS_005 into " + path)
