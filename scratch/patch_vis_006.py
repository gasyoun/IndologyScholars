import re

path = 'generate_publication_pages.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

py_logic = """
    # --- VIS_006 Thematic Hierarchy Data ---
    hierarchy_data = {"name": "Все доклады", "children": []}
    try:
        import csv
        from collections import defaultdict
        
        # Build tree: Series -> L1 Theme -> Meso
        tree = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        
        with open("analytics_output/expanded_classification_deepseek.csv", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                series = row.get("series")
                theme = row.get("theme_l1")
                meso = row.get("meso_codes") or row.get("proposed_meso")
                
                if not series: series = "Unknown"
                if not theme or theme == "unspecified": theme = "Unknown"
                if not meso or meso == "unspecified": meso = "Other"
                
                series_group = "Zograf" if "zograf" in series.lower() else "Roerich"
                meso = meso.split(',')[0].strip()
                
                tree[series_group][theme][meso] += 1
                
        for s_name, themes in tree.items():
            s_node = {"name": s_name, "children": []}
            for t_name, mesos in themes.items():
                t_node = {"name": t_name, "children": []}
                for m_name, count in mesos.items():
                    if count >= 3: # filter out very small blocks
                        t_node["children"].append({"name": m_name, "value": count})
                if t_node["children"]:
                    s_node["children"].append(t_node)
            if s_node["children"]:
                hierarchy_data["children"].append(s_node)
                
    except Exception as ex:
        print(f"Error querying hierarchy data: {ex}")
        
    serialized_hierarchy = json.dumps(hierarchy_data, ensure_ascii=False)
"""

content = content.replace("    serialized_forest = json.dumps({\"scholars\": top_scholars, \"years\": all_years, \"data\": forest_data}, ensure_ascii=False)", "    serialized_forest = json.dumps({\"scholars\": top_scholars, \"years\": all_years, \"data\": forest_data}, ensure_ascii=False)\n" + py_logic)

html_block = """
        <!-- VIS_006_thematic_hierarchy -->
        <section class="viz-showcase-section" id="VIS_006_thematic_hierarchy">
            <h2>
                <span class="viz-id-badge">VIS_006</span>
                <span class="bilingual-text" data-ru="Иерархия тематических направлений" data-en="Thematic Hierarchy (Icicle Chart)">Иерархия тематических направлений</span>
            </h2>
            <p class="bilingual-text" style="color:var(--muted); font-size:0.9rem;" data-ru="Детальное распределение объема докладов по сериям чтений, основным темам и узким мезо-кластерам. Чем шире блок, тем больше докладов в этой теме." data-en="A detailed breakdown of presentation volume across conference series, main themes, and narrow meso-clusters. The wider the block, the more presentations belong to that theme.">Детальное распределение объема докладов по сериям чтений, основным темам и узким мезо-кластерам. Чем шире блок, тем больше докладов в этой теме.</p>
            <div id="hierarchy-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:2rem;">
                <svg id="hierarchy-svg" viewBox="0 0 800 400" style="width:100%; height:auto; background:rgba(0,0,0,0.15); border-radius:8px;"></svg>
                <div id="hierarchy-tooltip" style="position: absolute; background: rgba(18, 18, 24, 0.95); border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 8px; padding: 0.8rem 1rem; font-size: 0.85rem; color: #fff; pointer-events: none; opacity: 0; transition: opacity 0.15s ease; z-index: 1000; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5); backdrop-filter: blur(4px);"></div>
            </div>
        </section>
"""

# Insert HTML after forest block
content = content.replace('            <div id="forest-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:2rem;">', html_block + '\n            <div id="forest-wrapper" style="position:relative; width:100%; overflow:hidden; margin-top:2rem;">')


js_injection = """
            const HIERARCHY_DATA = """ + '""" + serialized_hierarchy + """' + """;

            function drawHierarchy() {
                const svg = document.getElementById('hierarchy-svg');
                if (!svg || !HIERARCHY_DATA.children) return;
                svg.innerHTML = '';
                
                const width = 800;
                const height = 400;
                
                // Calculate values bottom-up
                function calcValue(node) {
                    if (node.children) {
                        node.value = node.children.reduce((sum, child) => sum + calcValue(child), 0);
                    }
                    return node.value || 0;
                }
                calcValue(HIERARCHY_DATA);
                
                const totalValue = HIERARCHY_DATA.value;
                if(totalValue === 0) return;
                
                const tooltip = document.getElementById('hierarchy-tooltip');
                
                const levels = 4; // Root, Series, Theme, Meso
                const rowH = height / levels;
                
                const colors = {
                    'Zograf': '#2b82c9',
                    'Roerich': '#b83280',
                    'Default': '#6b7280'
                };
                
                function drawNode(node, x, y, w, h, level, parentColor) {
                    if (w < 1) return; // don't draw tiny blocks
                    
                    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                    rect.setAttribute('x', x);
                    rect.setAttribute('y', y);
                    rect.setAttribute('width', w);
                    rect.setAttribute('height', h - 2); // 2px gap
                    
                    let fillColor = parentColor;
                    if (level === 0) fillColor = '#4b5563';
                    if (level === 1) fillColor = colors[node.name] || colors.Default;
                    
                    rect.setAttribute('fill', fillColor);
                    rect.setAttribute('stroke', '#1e1e24');
                    rect.setAttribute('stroke-width', '1');
                    
                    if(level > 0) {
                        // varying opacity by level
                        rect.setAttribute('fill-opacity', 1 - (level-1)*0.25);
                        rect.setAttribute('cursor', 'pointer');
                        rect.style.transition = 'opacity 0.2s';
                        
                        rect.addEventListener('mouseenter', () => {
                            rect.setAttribute('fill-opacity', '1');
                            tooltip.style.opacity = '1';
                            tooltip.innerHTML = `<strong>${node.name}</strong><br/>Докладов: ${node.value}`;
                        });
                        rect.addEventListener('mousemove', (e) => {
                            const container = document.getElementById('hierarchy-wrapper').getBoundingClientRect();
                            tooltip.style.left = (e.clientX - container.left + 15) + 'px';
                            tooltip.style.top = (e.clientY - container.top - 30) + 'px';
                        });
                        rect.addEventListener('mouseleave', () => {
                            rect.setAttribute('fill-opacity', 1 - (level-1)*0.25);
                            tooltip.style.opacity = '0';
                        });
                    }
                    
                    svg.appendChild(rect);
                    
                    // Draw text if enough space
                    if (w > 30) {
                        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                        text.setAttribute('x', x + 5);
                        text.setAttribute('y', y + h/2 + 4);
                        text.setAttribute('fill', '#fff');
                        text.setAttribute('font-size', '11px');
                        text.style.pointerEvents = 'none';
                        let label = node.name;
                        if (label.length * 6 > w) { // approximate width
                            label = label.substring(0, Math.floor(w/6) - 1) + '…';
                        }
                        text.textContent = label;
                        svg.appendChild(text);
                    }
                    
                    // Recurse children
                    if (node.children) {
                        let cx = x;
                        node.children.forEach(child => {
                            const cw = (child.value / node.value) * w;
                            drawNode(child, cx, y + rowH, cw, rowH, level + 1, fillColor);
                            cx += cw;
                        });
                    }
                }
                
                drawNode(HIERARCHY_DATA, 0, 0, width, rowH, 0, '#4b5563');
            }
"""

content = content.replace("const FOREST_DATA = ", js_injection + "\n            const FOREST_DATA = ")

content = content.replace("drawForest();", "drawForest();\n                drawHierarchy();")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Patched VIS_006 into " + path)
