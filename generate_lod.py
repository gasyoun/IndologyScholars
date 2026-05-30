import json
import os
import datetime

# Attempt to import rdflib, fallback to simple string generation if not installed
try:
    from rdflib import Graph, Literal, RDF, URIRef, Namespace
    from rdflib.namespace import FOAF, XSD
    RDFLIB_AVAILABLE = True
except ImportError:
    RDFLIB_AVAILABLE = False
    print("Warning: rdflib not installed. Will generate simple Turtle manually.")

OUTPUT_FILE = "indology_knowledge_graph.ttl"
SCHOLARS_FILE = "site_data_scholars.json"
BASE_URL = "https://gasyoun.github.io/IndologyScholars/"

def generate_lod_with_rdflib(scholars):
    g = Graph()
    
    # Namespaces
    SCHEMA = Namespace("http://schema.org/")
    WD = Namespace("http://www.wikidata.org/entity/")
    INDO = Namespace(BASE_URL + "lod/")
    
    g.bind("schema", SCHEMA)
    g.bind("foaf", FOAF)
    g.bind("wd", WD)
    g.bind("indo", INDO)
    
    # Static Entities (Series)
    zograf_uri = INDO["series/Zograf"]
    roerich_uri = INDO["series/Roerich"]
    
    g.add((zograf_uri, RDF.type, SCHEMA.EventSeries))
    g.add((zograf_uri, SCHEMA.name, Literal("Зографские чтения", lang="ru")))
    g.add((zograf_uri, SCHEMA.name, Literal("Zograf Readings", lang="en")))
    
    g.add((roerich_uri, RDF.type, SCHEMA.EventSeries))
    g.add((roerich_uri, SCHEMA.name, Literal("Рериховские чтения", lang="ru")))
    g.add((roerich_uri, SCHEMA.name, Literal("Roerich Readings", lang="en")))
    
    for s in scholars:
        scholar_uri = INDO["scholar/" + str(s["id"])]
        g.add((scholar_uri, RDF.type, FOAF.Person))
        g.add((scholar_uri, FOAF.name, Literal(s["name"], lang="ru")))
        if s.get("full_name_ru"):
            g.add((scholar_uri, SCHEMA.alternateName, Literal(s["full_name_ru"], lang="ru")))
        if s.get("full_name_en"):
            g.add((scholar_uri, SCHEMA.alternateName, Literal(s["full_name_en"], lang="en")))
            
        if s.get("birth_year"):
            g.add((scholar_uri, SCHEMA.birthDate, Literal(str(s["birth_year"]), datatype=XSD.gYear)))
        if s.get("death_year"):
            g.add((scholar_uri, SCHEMA.deathDate, Literal(str(s["death_year"]), datatype=XSD.gYear)))
            
        # Add talks
        for talk in s.get("talks", []):
            pres_uri = INDO["presentation/" + str(talk["presentation_id"])]
            g.add((pres_uri, RDF.type, SCHEMA.PresentationDigitalDocument))
            g.add((pres_uri, SCHEMA.name, Literal(talk["title"], lang="ru")))
            g.add((pres_uri, SCHEMA.author, scholar_uri))
            
            # Link to series
            series_uri = zograf_uri if "Zograf" in talk.get("series", "") else roerich_uri
            
            # Event occurrence
            event_uri = INDO[f"event/{talk['year']}/{'Zograf' if 'Zograf' in talk.get('series', '') else 'Roerich'}"]
            g.add((event_uri, RDF.type, SCHEMA.Event))
            g.add((event_uri, SCHEMA.startDate, Literal(str(talk["year"]), datatype=XSD.gYear)))
            g.add((event_uri, SCHEMA.superEvent, series_uri))
            
            g.add((pres_uri, SCHEMA.recordedAt, event_uri))
            
            # Affiliation
            if talk.get("affiliation"):
                org_uri = INDO["org/" + talk["affiliation"].replace(" ", "_").replace('"', '')]
                g.add((org_uri, RDF.type, SCHEMA.Organization))
                g.add((org_uri, SCHEMA.name, Literal(talk["affiliation"], lang="ru")))
                g.add((scholar_uri, SCHEMA.memberOf, org_uri))

    g.serialize(destination=OUTPUT_FILE, format="turtle")
    print(f"Generated {OUTPUT_FILE} using rdflib.")

def generate_lod_manual(scholars):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("@prefix schema: <http://schema.org/> .\n")
        f.write("@prefix foaf: <http://xmlns.com/foaf/0.1/> .\n")
        f.write("@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n")
        f.write(f"@prefix indo: <{BASE_URL}lod/> .\n\n")
        
        f.write('indo:series\\/Zograf a schema:EventSeries ;\n')
        f.write('    schema:name "Зографские чтения"@ru , "Zograf Readings"@en .\n\n')
        
        f.write('indo:series\\/Roerich a schema:EventSeries ;\n')
        f.write('    schema:name "Рериховские чтения"@ru , "Roerich Readings"@en .\n\n')
        
        for s in scholars:
            sid = s["id"]
            f.write(f'indo:scholar\\/{sid} a foaf:Person ;\n')
            f.write(f'    foaf:name "{s["name"]}"@ru ')
            
            if s.get("birth_year"):
                f.write(f';\n    schema:birthDate "{s["birth_year"]}"^^xsd:gYear ')
                
            # Affiliations (unique)
            affiliations = set()
            for talk in s.get("talks", []):
                if talk.get("affiliation"):
                    affiliations.add(talk["affiliation"])
            
            for aff in affiliations:
                clean_aff = aff.replace(" ", "_").replace('"', '').replace('/', '_').replace('\\', '')
                f.write(f';\n    schema:memberOf indo:org\\/{clean_aff} ')
                
            f.write(".\n\n")
            
            for talk in s.get("talks", []):
                tid = talk["presentation_id"]
                title = talk["title"].replace('"', '\\"').replace('\n', ' ')
                f.write(f'indo:presentation\\/{tid} a schema:PresentationDigitalDocument ;\n')
                f.write(f'    schema:name "{title}"@ru ;\n')
                f.write(f'    schema:author indo:scholar\\/{sid} ;\n')
                
                series_id = "Zograf" if "Zograf" in talk.get("series", "") else "Roerich"
                f.write(f'    schema:recordedAt indo:event\\/{talk["year"]}\\/{series_id} .\n\n')
                
        print(f"Generated {OUTPUT_FILE} manually.")

def main():
    if not os.path.exists(SCHOLARS_FILE):
        print(f"Error: {SCHOLARS_FILE} not found. Run generate_site_data.py first.")
        return
        
    with open(SCHOLARS_FILE, "r", encoding="utf-8") as f:
        scholars = json.load(f)
        
    if RDFLIB_AVAILABLE:
        generate_lod_with_rdflib(scholars)
    else:
        generate_lod_manual(scholars)

if __name__ == "__main__":
    main()
