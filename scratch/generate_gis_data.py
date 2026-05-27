import json
import math
import os
import sys
from pathlib import Path

# Reconfigure stdout to force UTF-8 printing
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Approximate geographical coordinates for key cities in our corpus
CITY_COORDINATES = {
    "Санкт-Петербург": [59.9343, 30.3351],
    "Москва": [55.7558, 37.6173],
    "Обнинск": [55.0968, 36.6103],
    "Краснодар": [45.0355, 38.9753],
    "Лозанна": [46.5197, 6.6323],
    "Вильнюс": [54.6872, 25.2797],
    "Рига": [56.9496, 24.1052],
    "Дели": [28.6139, 77.2090],
    "Новосибирск": [55.0084, 82.9357],
    "Владивосток": [43.1198, 131.8869],
    "Казань": [55.8304, 49.0661],
    "Улан-Удэ": [51.8292, 107.6063],
    "Кяхта": [50.3621, 106.2167],
    "Элиста": [46.3078, 44.2558],
    "Лондон": [51.5074, -0.1278],
    "Париж": [48.8566, 2.3522],
    "Лейден": [52.1601, 4.4970]
}

def load_site_data(path="site_data.json"):
    text = Path(path).read_text(encoding="utf-8").strip()
    prefix = "const CONFERENCE_DATA = "
    if text.startswith(prefix):
        text = text[len(prefix):]
    if text.endswith(";"):
        text = text[:-1]
    return json.loads(text)

def main():
    print("=== WEB GIS FLOW MAP GENERATOR ===")
    
    site_data_path = "site_data.json"
    if not os.path.exists(site_data_path):
        print(f"Data file {site_data_path} not found. Please run the build pipeline first.")
        return
        
    data = load_site_data(site_data_path)
    scholars = data.get("scholars", [])
    print(f"Loaded {len(scholars)} scholars from site_data.json.")
    
    flows = {} # (origin_city, destination_city) -> list of presentations
    city_stats = {} # city -> {presenters: set, talks: int}
    
    for scholar in scholars:
        speaker = scholar.get("name") or scholar.get("full_name_ru") or "Unknown"
        talks = scholar.get("talks", [])
        
        for talk in talks:
            geo = talk.get("geography") or {}
            city = geo.get("ru")
            if not city or city in ("Не указана", "Not specified"):
                continue
                
            origin = city.strip()
            # Series name tells us the destination
            series = talk.get("series_id") or ""
            destination = "Санкт-Петербург" if "zograf" in series.lower() else "Москва"
            
            if origin == destination:
                # Local presenter
                city_stats.setdefault(origin, {"presenters": set(), "talks": 0})
                city_stats[origin]["presenters"].add(speaker)
                city_stats[origin]["talks"] += 1
                continue
                
            key = (origin, destination)
            flows.setdefault(key, [])
            flows[key].append({
                "title": talk.get("title") or "Untitled",
                "speaker": speaker,
                "year": talk.get("year") or "",
                "series": "Зографские чтения" if "zograf" in series.lower() else "Рериховские чтения"
            })
            
            # Aggregate stats
            city_stats.setdefault(origin, {"presenters": set(), "talks": 0})
            city_stats[origin]["presenters"].add(speaker)
            city_stats[origin]["talks"] += 1
            
            city_stats.setdefault(destination, {"presenters": set(), "talks": 0})
            city_stats[destination]["presenters"].add(speaker)
            city_stats[destination]["talks"] += 1

    # Format flow features for Leaflet
    flow_features = []
    for (origin, destination), talks_list in flows.items():
        orig_coords = CITY_COORDINATES.get(origin)
        dest_coords = CITY_COORDINATES.get(destination)
        
        if not orig_coords or not dest_coords:
            continue
            
        flow_features.append({
            "origin": origin,
            "origin_coords": orig_coords,
            "destination": destination,
            "destination_coords": dest_coords,
            "count": len(talks_list),
            "details": talks_list[:5] # Sample talks
        })

    # Prepare city nodes metadata
    node_features = []
    for city, stats in city_stats.items():
        coords = CITY_COORDINATES.get(city)
        if not coords:
            continue
        node_features.append({
            "city": city,
            "coords": coords,
            "presenter_count": len(stats["presenters"]),
            "talk_count": stats["talks"]
        })

    # Build Web GIS HTML page utilizing Leaflet
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Web GIS: Academic Migration & Presenter Flow Map</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        :root {{
            --bg: #0f1412;
            --panel: #161f1c;
            --border: #283731;
            --text: #e2e9e5;
            --accent: #5db093;
        }}
        body, html {{
            margin: 0; padding: 0; height: 100%;
            background: var(--bg);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}
        #map {{
            height: calc(100% - 60px);
            width: 100%;
        }}
        #header {{
            height: 60px;
            background: var(--panel);
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 1.5rem;
        }}
        h1 {{
            font-size: 1.25rem;
            margin: 0;
            color: #fff;
            font-weight: 600;
        }}
        .meta {{
            font-size: 0.85rem;
            color: #8fa098;
        }}
        .leaflet-popup-content-wrapper {{
            background: var(--panel) !important;
            color: var(--text) !important;
            border: 1px solid var(--border);
            border-radius: 8px;
        }}
        .leaflet-popup-tip {{
            background: var(--panel) !important;
            border: 1px solid var(--border);
        }}
        .popup-title {{
            font-weight: 700;
            font-size: 1rem;
            border-bottom: 1px solid var(--border);
            padding-bottom: 0.3rem;
            margin-bottom: 0.5rem;
            color: #fff;
        }}
        .popup-item {{
            font-size: 0.82rem;
            margin: 0.25rem 0;
            line-height: 1.4;
        }}
        .popup-badge {{
            display: inline-block;
            padding: 0.1rem 0.3rem;
            border-radius: 4px;
            font-size: 0.72rem;
            background: rgba(93,176,147,0.18);
            color: var(--accent);
            margin-right: 0.3rem;
        }}
    </style>
</head>
<body>
    <div id="header">
        <h1>Russian Indological Archive: Scholar Flow Map (Web GIS)</h1>
        <div class="meta">Visualizing geographical academic migration to Zograf (SPb) & Roerich (Msk) Readings</div>
    </div>
    <div id="map"></div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        // Initialize Map in premium Dark mode (using CartoDB Dark Matter tiles)
        const map = L.map('map').setView([55.0, 45.0], 4);
        
        L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 20
        }}).addTo(map);

        // Core data payload compiled dynamically from SQLite database
        const flows = {json.dumps(flow_features, ensure_ascii=False)};
        const nodes = {json.dumps(node_features, ensure_ascii=False)};

        // Draw animated curved canvas paths representing travel flow
        const canvasRenderer = L.canvas({{ padding: 0.5 }}).addTo(map);

        // Function to draw curved arcs between cities
        function drawCurve(startLatlng, endLatlng, count, label) {{
            const points = [];
            const startPoint = map.latLngToContainerPoint(startLatlng);
            const endPoint = map.latLngToContainerPoint(endLatlng);
            
            // Calculate a control point to create a nice bezier arc curve
            const midX = (startPoint.x + endPoint.x) / 2;
            const midY = (startPoint.y + endPoint.y) / 2;
            const len = Math.sqrt(Math.pow(endPoint.x - startPoint.x, 2) + Math.pow(endPoint.y - startPoint.y, 2));
            
            // Offset the curve perpendicular to the line path
            const offsetX = -1 * (endPoint.y - startPoint.y) * 0.15;
            const offsetY = (endPoint.x - startPoint.x) * 0.15;
            const controlPoint = L.point(midX + offsetX, midY + offsetY);
            
            // Calculate curve points
            for (let t = 0; t <= 1; t += 0.05) {{
                const x = Math.pow(1 - t, 2) * startPoint.x + 2 * (1 - t) * t * controlPoint.x + Math.pow(t, 2) * endPoint.x;
                const y = Math.pow(1 - t, 2) * startPoint.y + 2 * (1 - t) * t * controlPoint.y + Math.pow(t, 2) * endPoint.y;
                points.push(map.containerPointToLatLng(L.point(x, y)));
            }}

            const weight = Math.min(2 + count * 0.5, 8);
            const polyline = L.polyline(points, {{
                color: '#5db093',
                weight: weight,
                opacity: 0.5,
                lineCap: 'round',
                renderer: canvasRenderer
            }}).addTo(map);
            
            return polyline;
        }}

        // Draw flows
        flows.forEach(flow => {{
            const curve = drawCurve(L.latLng(flow.origin_coords), L.latLng(flow.destination_coords), flow.count, flow.origin);
            
            // Generate popups listing presentations along this path
            let popupContent = `<div class="popup-title">Flow: ${{flow.origin}} ➔ ${{flow.destination}}</div>`;
            popupContent += `<div class="popup-item"><strong>Total Presentations:</strong> ${{flow.count}}</div>`;
            flow.details.forEach(talk => {{
                popupContent += `<div class="popup-item">
                    <span class="popup-badge">${{talk.year}}</span>
                    <strong>${{talk.speaker}}</strong>: "${{talk.title}}" (${{talk.series}})
                </div>`;
            }});
            
            curve.bindPopup(popupContent);
        }});

        // Draw nodes (city circles)
        nodes.forEach(node => {{
            const size = Math.min(6 + node.talk_count * 0.8, 22);
            const circle = L.circleMarker(node.coords, {{
                radius: size,
                color: '#c59a56',
                fillColor: '#c59a56',
                fillOpacity: 0.65,
                weight: 2
            }}).addTo(map);

            let popupContent = `<div class="popup-title">${{node.city}}</div>`;
            popupContent += `<div class="popup-item"><strong>Presenters:</strong> ${{node.presenter_count}}</div>`;
            popupContent += `<div class="popup-item"><strong>Total Presentations:</strong> ${{node.talk_count}}</div>`;
            circle.bindPopup(popupContent);
        }});
    </script>
</body>
</html>
"""
    
    output_path = "scratch/gis_map.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"Successfully generated Web GIS Flow Map at: {output_path}")

if __name__ == '__main__':
    main()
