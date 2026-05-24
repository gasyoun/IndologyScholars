import csv
import json
import os

def main():
    nodes_path = "analytics_output/network_nodes.csv"
    edges_path = "analytics_output/network_edges.csv"
    json_output_path = "analytics_output/network_data.json"
    
    if not os.path.exists(nodes_path) or not os.path.exists(edges_path):
        print("CSV files not found!")
        return
        
    nodes = []
    with open(nodes_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            nodes.append({
                "id": row["node_id"],
                "type": row["node_type"],
                "label": row["label"],
                "local_id": row["local_id"],
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
