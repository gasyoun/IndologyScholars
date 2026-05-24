import csv
import json
import os

def main():
    nodes_path = "analytics_output/network_nodes.csv"
    edges_path = "analytics_output/network_edges.csv"
    json_output_path = "analytics_output/network_data.json"
    site_data_path = "site_data.json"
    
    if not os.path.exists(nodes_path) or not os.path.exists(edges_path):
        print("CSV files not found!")
        return
        
    # Load url_slug mapping from site_data.json to ensure network links use canonical Latin slugs
    slug_map = {}
    if os.path.exists(site_data_path):
        try:
            with open(site_data_path, mode='r', encoding='utf-8') as f:
                text = f.read().strip()
                prefix = "const CONFERENCE_DATA = "
                if text.startswith(prefix):
                    text = text[len(prefix):]
                if text.endswith(";"):
                    text = text[:-1]
                site_data = json.loads(text)
                for scholar in site_data.get("scholars", []):
                    if scholar.get("id") and scholar.get("url_slug"):
                        slug_map[scholar["id"]] = scholar["url_slug"]
            print(f"Loaded {len(slug_map)} slug mappings from site_data.json")
        except Exception as e:
            print(f"Warning: Could not load site_data.json for slug mapping: {e}")
    else:
        print("Warning: site_data.json not found! Falling back to raw IDs.")
        
    nodes = []
    with open(nodes_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            local_id = row["local_id"]
            slug = slug_map.get(local_id, local_id) if row["node_type"] == "person" else None
            
            nodes.append({
                "id": row["node_id"],
                "type": row["node_type"],
                "label": row["label"],
                "local_id": local_id,
                "slug": slug,
                "weight": float(row["weight"]) if row["weight"] else 1.0
            })
            
    edges = []
    with open(edges_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            edges.append({
                "source": row["source"],
                "target": row["target"],
                "type": row["edge_type"],
                "year": int(row["year"]) if row["year"] else None,
                "series": row["series"] if row["series"] else None,
                "weight": float(row["weight"]) if row["weight"] else 1.0
            })
            
    data = {
        "nodes": nodes,
        "edges": edges
    }
    
    with open(json_output_path, mode='w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print(f"Successfully compiled {len(nodes)} nodes and {len(edges)} edges to {json_output_path}")

if __name__ == "__main__":
    main()
