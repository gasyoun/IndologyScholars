import re

path = 'generate_publication_pages.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

py_logic = """
    # --- VIS_007 Arc Diagram Data ---
    arc_nodes = []
    arc_links = []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(\"\"\"
            SELECT per.display_name, COUNT(p.presentation_id) as total
            FROM presentation p
            JOIN presentation_person pp ON p.presentation_id = pp.presentation_id
            JOIN person per ON pp.person_id = per.person_id
            GROUP BY per.person_id
            ORDER BY total DESC
            LIMIT 50
        \"\"\")
        top_50 = [row[0] for row in cursor.fetchall()]
        top_set = set(top_50)
        
        for name in top_50:
            arc_nodes.append({"id": name, "group": 1})
            
        cursor.execute(\"\"\"
            SELECT p.session_id, per.display_name
            FROM presentation p
            JOIN presentation_person pp ON p.presentation_id = pp.presentation_id
            JOIN person per ON pp.person_id = per.person_id
        \"\"\")
        sess_people = defaultdict(set)
        for s_id, name in cursor.fetchall():
            if name in top_set:
                sess_people[s_id].add(name)
                
        edges = defaultdict(int)
        for s_id, people in sess_people.items():
            plist = list(people)
            for i in range(len(plist)):
                for j in range(i+1, len(plist)):
                    p1, p2 = sorted([plist[i], plist[j]])
                    edges[(p1, p2)] += 1
                    
        for (p1, p2), count in edges.items():
            if count >= 2:
                arc_links.append({"source": p1, "target": p2, "value": count})
                
        conn.close()
    except Exception as ex:
        print(f"Error querying arc data: {ex}")
        
    serialized_arc = json.dumps({"nodes": arc_nodes, "links": arc_links}, ensure_ascii=False)
"""

content = content.replace("    serialized_hierarchy = json.dumps(hierarchy_data, ensure_ascii=False)", "    serialized_hierarchy = json.dumps(hierarchy_data, ensure_ascii=False)\n" + py_logic)

html_block = """
        <!-- VIS_007_network_arc -->
        <section class="viz-showcase-section" id="VIS_007_network_arc">
            <h2>
                <span class="viz-id-badge">VIS_007</span>
                <span class="bilingual-text" data-ru="Сеть соавторства и пересечений (Дуговая диаграмма)" data-en="Co-authorship Network (Arc Diagram)">Сеть соавторства и пересечений (Дуговая диаграмма)</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Граф связей 50 самых активных ученых. Дуги соединяют докладчиков, выступавших в одних и тех же секциях как минимум дважды. Толщина линии означает плотность связей." data-en="A network graph of the 50 most active scholars. Arcs connect speakers who have presented in the same sessions at least twice. Line thickness represents tie strength.">Граф связей 50 самых активных ученых. Дуги соединяют докладчиков, выступавших в одних и тех же секциях как минимум дважды. Толщина линии означает плотность связей.</p>
            <div id="arc-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:2rem;">
                <svg id="arc-svg" viewBox="0 0 1000 600" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="arc-tooltip" style="position: absolute; background: rgba(18, 18, 24, 0.95); border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 8px; padding: 0.8rem 1rem; font-size: 0.85rem; color: #fff; pointer-events: none; opacity: 0; transition: opacity 0.15s ease; z-index: 1000; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5); backdrop-filter: blur(4px);"></div>
            </div>
        </section>
"""

# Insert HTML after hierarchy block
content = content.replace('            <div id="hierarchy-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:2rem;">', html_block + '\n            <div id="hierarchy-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:2rem;">')


js_injection = """
            const ARC_DATA = """ + '""" + serialized_arc + """' + """;

            function drawArc() {
                const svg = document.getElementById('arc-svg');
                if (!svg || !ARC_DATA.nodes) return;
                svg.innerHTML = '';
                
                const width = 1000;
                const height = 600;
                const baselineY = height - 150;
                const padding = { left: 50, right: 50 };
                
                const nodes = ARC_DATA.nodes;
                const links = ARC_DATA.links;
                
                const step = (width - padding.left - padding.right) / (nodes.length - 1);
                
                // assign x coords
                const nodeX = {};
                nodes.forEach((n, i) => {
                    n.x = padding.left + i * step;
                    nodeX[n.id] = n.x;
                });
                
                const tooltip = document.getElementById('arc-tooltip');
                
                // Draw base line
                const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
                line.setAttribute('x1', padding.left - 20);
                line.setAttribute('y1', baselineY);
                line.setAttribute('x2', width - padding.right + 20);
                line.setAttribute('y2', baselineY);
                line.setAttribute('stroke', 'rgba(255,255,255,0.1)');
                svg.appendChild(line);
                
                // Draw Links
                links.forEach(l => {
                    const x1 = Math.min(nodeX[l.source], nodeX[l.target]);
                    const x2 = Math.max(nodeX[l.source], nodeX[l.target]);
                    
                    if (x1 === undefined || x2 === undefined || x1 === x2) return;
                    
                    const r = (x2 - x1) / 2;
                    const cx = x1 + r;
                    
                    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                    const d = `M ${x1} ${baselineY} A ${r} ${r} 0 0 1 ${x2} ${baselineY}`;
                    
                    path.setAttribute('d', d);
                    path.setAttribute('fill', 'none');
                    path.setAttribute('stroke', 'var(--accent)');
                    path.setAttribute('stroke-opacity', Math.min(0.1 + l.value * 0.1, 0.6));
                    path.setAttribute('stroke-width', Math.min(1 + l.value * 0.5, 5));
                    path.style.cursor = 'pointer';
                    path.style.transition = 'stroke-opacity 0.2s, stroke-width 0.2s';
                    
                    path.addEventListener('mouseenter', () => {
                        path.setAttribute('stroke-opacity', '1');
                        path.setAttribute('stroke-width', Math.min(3 + l.value * 0.5, 7));
                        tooltip.style.opacity = '1';
                        tooltip.innerHTML = `<strong>${l.source} ↔ ${l.target}</strong><br/>Совместных сессий: ${l.value}`;
                    });
                    path.addEventListener('mousemove', (e) => {
                        const container = document.getElementById('arc-wrapper').getBoundingClientRect();
                        tooltip.style.left = (e.clientX - container.left + 15) + 'px';
                        tooltip.style.top = (e.clientY - container.top - 30) + 'px';
                    });
                    path.addEventListener('mouseleave', () => {
                        path.setAttribute('stroke-opacity', Math.min(0.1 + l.value * 0.1, 0.6));
                        path.setAttribute('stroke-width', Math.min(1 + l.value * 0.5, 5));
                        tooltip.style.opacity = '0';
                    });
                    
                    svg.appendChild(path);
                });
                
                // Draw Nodes
                nodes.forEach(n => {
                    const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                    circle.setAttribute('cx', n.x);
                    circle.setAttribute('cy', baselineY);
                    circle.setAttribute('r', 3);
                    circle.setAttribute('fill', '#fff');
                    svg.appendChild(circle);
                    
                    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    text.setAttribute('x', n.x);
                    text.setAttribute('y', baselineY + 15);
                    text.setAttribute('fill', 'rgba(255,255,255,0.7)');
                    text.setAttribute('font-size', '10px');
                    text.setAttribute('transform', `rotate(45, ${n.x}, ${baselineY + 15})`);
                    text.textContent = n.id;
                    svg.appendChild(text);
                });
            }
"""

content = content.replace("const HIERARCHY_DATA = ", js_injection + "\n            const HIERARCHY_DATA = ")

content = content.replace("drawHierarchy();", "drawHierarchy();\n                drawArc();")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched VIS_007 into " + path)
