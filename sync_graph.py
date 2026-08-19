import os
import json
from neo4j import GraphDatabase

# Environment setup with fallbacks
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+s://fae1ba87.databases.neo4j.io")
NEO4J_USER = os.getenv("NEO4J_USER", "fae1ba87")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "gLVMYFlAVVyfSSanVcoxbYB23WHMzz-TfXUUhFHLUUY")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARTIFACTS_FILE = os.path.join(BASE_DIR, "artifacts", "crawler_artifacts.json")
MAPPING_FILE = os.path.join(BASE_DIR, "app_mapping.json")

def sync_3layer_graph(driver, base_dir=None):
    """
    Ingests Requirements, Crawler UI Artifacts, and Code Components
    into a unified 3-Layer Neo4j Knowledge Graph.
    """
    # Rest of function remains the same...
    with driver.session() as session:
        # Clear existing graph for clean sync
        session.run("MATCH (n) DETACH DELETE n")

        # --- LAYER 1: Ingest Requirements & Product Spec ---
        if os.path.exists(MAPPING_FILE):
            with open(MAPPING_FILE, "r", encoding="utf-8") as f:
                mapping = json.load(f)
            
            for item in mapping.get("mappings", []):
                session.run("""
                    MERGE (r:Requirement {id: $test_id})
                    SET r.title = $requirement, 
                        r.expected_route = $route
                    MERGE (c:Component {name: $component})
                    MERGE (t:TestCase {id: $test_id, file: $test_file})
                    MERGE (t)-[:VERIFIES]->(r)
                """, **item)
            print("[Graph] Layer 1 (Requirements & Test Mappings) Synced.")

        # --- LAYER 2: Ingest DOM / UI Crawled Artifacts ---
        if os.path.exists(ARTIFACTS_FILE):
            with open(ARTIFACTS_FILE, "r", encoding="utf-8") as f:
                crawl_data = json.load(f)

            # Insert Screens & Elements
            for screen in crawl_data.get("screens", []):
                session.run("""
                    MERGE (s:Screen {route: $route})
                    SET s.title = $title, s.screenshot = $screenshot_file
                    
                    WITH s
                    OPTIONAL MATCH (r:Requirement {expected_route: $route})
                    FOREACH (_ IN CASE WHEN r IS NOT NULL THEN [1] ELSE [] END |
                        MERGE (r)-[:EXPECTS_UI]->(s)
                    )
                """, **screen)

                # Connect Screen to UI Elements
                for elem in screen.get("elements", []):
                    session.run("""
                        MATCH (s:Screen {route: $route})
                        MERGE (e:UIElement {id: $element_id, selector: $selector})
                        SET e.tag = $tag, e.text = $text, e.type = $type
                        MERGE (s)-[:HAS_ELEMENT]->(e)
                    """, route=screen["route"], **elem)

            # Insert Interaction Transitions
            for trans in crawl_data.get("transitions", []):
                session.run("""
                    MATCH (from:Screen {route: $from_route})
                    MATCH (to:Screen {route: $to_route})
                    MERGE (from)-[t:TRANSITIONS_TO {by: $triggered_by}]->(to)
                    SET t.label = $trigger_text
                """, **trans)
                
            print("[Graph] Layer 2 (DOM / UI Crawled Artifacts & Transitions) Synced.")

        # --- LAYER 3: Connect Code Components to UI / Requirements ---
        if os.path.exists(MAPPING_FILE):
            with open(MAPPING_FILE, "r", encoding="utf-8") as f:
                mapping = json.load(f)
            for item in mapping.get("mappings", []):
                session.run("""
                    MATCH (c:Component {name: $component})
                    MATCH (s:Screen {route: $route})
                    MERGE (s)-[:IMPLEMENTED_BY]->(c)
                """, **item)
            print("[Graph] Layer 3 (Code Components to UI) Linked.")

def detect_absence(driver):
    """
    Identifies requirements defined in spec that are missing 
    from the captured live DOM/UI crawl (Modeling Absence).
    """
    query = """
    MATCH (r:Requirement)
    OPTIONAL MATCH (r)-[:EXPECTS_UI]->(s:Screen)
    WITH r, s
    WHERE s IS NULL
    RETURN r.id AS RequirementID, 
           r.title AS Title, 
           coalesce(r.expected_route, "Not Specified") AS MissingRoute
    """
    with driver.session() as session:
        results = session.run(query).data()
        
    print("\n================ ABSENCE ANALYSIS REPORT ================")
    if results:
        print(f"⚠️  Found {len(results)} Uncovered Requirement(s) (Missing in Live UI Crawl):")
        for res in results:
            print(f" • [{res['RequirementID']}] {res['Title']} -> Expected Route: {res['MissingRoute']}")
    else:
        print("✅ All defined requirements have corresponding live UI screens.")
    print("=========================================================\n")
    return results
def sync_codebase_to_neo4j(driver, *args, **kwargs):
    """Wrapper to maintain backwards compatibility with TestSigma_App.py."""
    print("[Graph] Triggering 3-Layer Knowledge Graph Sync...")
    sync_3layer_graph(driver)
if __name__ == "__main__":
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    sync_3layer_graph(driver)
    detect_absence(driver)
    driver.close()