import json
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
    print("=== TEMPORAL BARYCENTER TRAJECTORY MAP GENERATOR ===")
    
    site_data_path = "site_data.json"
    if not os.path.exists(site_data_path):
        print(f"Data file {site_data_path} not found. Please build it first.")
        return
        
    data = load_site_data(site_data_path)
    scholars = data.get("scholars", [])
    
    # Initialize dictionary to hold geocoded presentation coordinates by year
    # year -> list of coordinates [lat, lon]
    year_coordinates = {}
    
    for scholar in scholars:
        talks = scholar.get("talks", [])
        for talk in talks:
            year = talk.get("year")
            if not year:
                continue
            geo = talk.get("geography") or {}
            city = geo.get("ru")
            if not city or city in ("Не указана", "Not specified"):
                continue
            
            coords = CITY_COORDINATES.get(city.strip())
            if coords:
                year_coordinates.setdefault(int(year), [])
                year_coordinates[int(year)].append({
                    "coords": coords,
                    "title": talk.get("title") or "Untitled",
                    "speaker": scholar.get("name") or "Unknown",
                    "city": city.strip()
                })
                
    # Sort years
    sorted_years = sorted(year_coordinates.keys())
    
    # Compute the barycenter for each year
    barycenters = {}
    for year in sorted_years:
        items = year_coordinates[year]
        total_lat = 0.0
        total_lon = 0.0
        for item in items:
            total_lat += item["coords"][0]
            total_lon += item["coords"][1]
        
        mean_lat = total_lat / len(items)
        mean_lon = total_lon / len(items)
        
        # Determine the primary city focus (Moscow talks count vs SPb talks count)
        spb_count = sum(1 for item in items if item["city"] == "Санкт-Петербург")
        msk_count = sum(1 for item in items if item["city"] == "Москва")
        other_count = len(items) - spb_count - msk_count
        
        barycenters[year] = {
            "coords": [mean_lat, mean_lon],
            "total_talks": len(items),
            "spb_talks": spb_count,
            "msk_talks": msk_count,
            "other_talks": other_count
        }
        print(f"Year {year} | Barycenter: [{mean_lat:.4f}, {mean_lon:.4f}] | Total Presentations: {len(items)}")

    # Build interactive Leaflet page with a slider
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Temporal GIS: Indology Center of Gravity Trajectory</title>
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
            height: calc(100% - 100px);
            width: 100%;
        }}
        #header {{
            height: 50px;
            background: var(--panel);
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 1.5rem;
        }}
        #controls {{
            height: 50px;
            background: var(--panel);
            border-top: 1px solid var(--border);
            display: flex;
            align-items: center;
            gap: 1.5rem;
            padding: 0 1.5rem;
        }}
        h1 {{
            font-size: 1.15rem;
            margin: 0;
            color: #fff;
            font-weight: 600;
        }}
        .slider-container {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            flex-grow: 1;
        }}
        input[type="range"] {{
            flex-grow: 1;
            accent-color: var(--accent);
        }}
        .year-indicator {{
            font-weight: 700;
            font-size: 1.25rem;
            color: var(--accent);
            min-width: 60px;
        }}
        .leaflet-popup-content-wrapper {{
            background: var(--panel) !important;
            color: var(--text) !important;
            border: 1px solid var(--border);
            border-radius: 8px;
        }}
        .leaflet-popup-tip {{
            background: var(--panel) !important;
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
        }}
        .stat-badge {{
            display: inline-block;
            padding: 0.1rem 0.3rem;
            border-radius: 4px;
            font-size: 0.75rem;
            background: rgba(255,255,255,0.08);
            margin-right: 0.3rem;
        }}
    </style>
</head>
<body>
    <div id="header">
        <h1>Indological Center of Gravity Shift (2004–2026)</h1>
        <div style="font-size: 0.85rem; color: #8fa098;">Temporal geographical mean of all presentations</div>
    </div>
    <div id="map"></div>
    <div id="controls">
        <div class="slider-container">
            <span style="font-size: 0.85rem; font-weight: 600;">TIMELINE:</span>
            <input type="range" id="time-slider" min="0" max="{len(sorted_years) - 1}" value="0">
            <span class="year-indicator" id="year-indicator">2004</span>
        </div>
        <div id="barycenter-info" style="font-size: 0.85rem; min-width: 320px; text-align: right;"></div>
    </div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        const map = L.map('map').setView([57.5, 34.0], 6);
        
        L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 20
        }}).addTo(map);

        const sortedYears = {json.dumps(sorted_years)};
        const barycenters = {json.dumps(barycenters, ensure_ascii=False)};
        
        // Define Static Venue Anchors
        const spbMarker = L.circleMarker([59.9343, 30.3351], {{
            radius: 8, color: '#2563eb', fillColor: '#2563eb', fillOpacity: 0.6
        }}).addTo(map).bindPopup('<strong>Санкт-Петербург (Зографские чтения)</strong>');

        const mskMarker = L.circleMarker([55.7558, 37.6173], {{
            radius: 8, color: '#dc2626', fillColor: '#dc2626', fillOpacity: 0.6
        }}).addTo(map).bindPopup('<strong>Москва (Рериховские чтения)</strong>');

        // Draw static baseline path representing the historical trajectory line
        const pathCoords = sortedYears.map(y => barycenters[y].coords);
        const trajectoryPath = L.polyline(pathCoords, {{
            color: '#c59a56',
            weight: 3,
            opacity: 0.35,
            dashArray: '5, 10'
        }}).addTo(map);

        // Highlight Active Year Barycenter Circle
        let activeBarycenterMarker = L.circleMarker(barycenters[sortedYears[0]].coords, {{
            radius: 12,
            color: '#5db093',
            fillColor: '#5db093',
            fillOpacity: 0.8,
            weight: 3
        }}).addTo(map);

        // Function to update visualization for selected year
        function updateYear(index) {{
            const year = sortedYears[index];
            const data = barycenters[year];
            
            document.getElementById('year-indicator').innerText = year;
            
            // Move marker to active barycenter coordinate
            activeBarycenterMarker.setLatLng(data.coords);
            
            // Build details panel
            const infoText = `<strong>Presentations:</strong> ${{data.total_talks}} (<span style="color: #60a5fa;">SPb: ${{data.spb_talks}}</span> / <span style="color: #f87171;">Msk: ${{data.msk_talks}}</span> / Other: ${{data.other_talks}})`;
            document.getElementById('barycenter-info').innerHTML = infoText;

            // Update popup
            const popupContent = `
                <div class="popup-title">Center of Gravity: ${{year}}</div>
                <div class="popup-item"><strong>Coordinates:</strong> ${{data.coords[0].toFixed(4)}}°N, ${{data.coords[1].toFixed(4)}}°E</div>
                <div class="popup-item"><strong>Total Papers:</strong> ${{data.total_talks}}</div>
                <div class="popup-item">
                    <span class="stat-badge" style="color: #93c5fd;">SPb: ${{data.spb_talks}}</span>
                    <span class="stat-badge" style="color: #fca5a5;">Msk: ${{data.msk_talks}}</span>
                    <span class="stat-badge">Other: ${{data.other_talks}}</span>
                </div>
            `;
            activeBarycenterMarker.bindPopup(popupContent).openPopup();
        }}

        // Slider handler
        const slider = document.getElementById('time-slider');
        slider.addEventListener('input', (e) => {{
            updateYear(e.target.value);
        }});

        // Initialize with first year
        updateYear(0);
    </script>
</body>
</html>
"""

    output_path = "scratch/temporal_gis.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"Successfully generated Temporal Barycenter Map at: {output_path}")

if __name__ == '__main__':
    main()
