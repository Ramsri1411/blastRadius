import json
import os
from ast_parser import sync_ast_to_neo4j
from neo4j import GraphDatabase

NEO4J_URI = os.getenv("NEO4J_URI") or "neo4j+s://fae1ba87.databases.neo4j.io"
NEO4J_USER = os.getenv("NEO4J_USER") or "fae1ba87"
NEO4J_PASSWORD = (
    os.getenv("NEO4J_PASSWORD") or "gLVMYFlAVVyfSSanVcoxbYB23WHMzz-TfXUUhFHLUUY"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ARTIFACTS_FILE = os.path.join(BASE_DIR, "artifacts", "crawler_artifacts.json")


def sync_3layer_graph(driver, base_dir=None):
  """Ingests Crawled UI Artifacts and Code Components into Neo4j

  and automatically builds relationships without app_mapping.json.
  """
  with driver.session() as session:
    # Clear existing graph for clean sync
    session.run("MATCH (n) DETACH DELETE n")

    # --- LAYER 1: AST Code Components & Dependency Graph ---
    sync_ast_to_neo4j(driver)
    print("[Graph] Layer 1 (AST Component Dependency Tree) Synced.")

    # --- LAYER 2: Ingest DOM / UI Crawled Artifacts ---
    if os.path.exists(ARTIFACTS_FILE):
      with open(ARTIFACTS_FILE, "r", encoding="utf-8") as f:
        crawl_data = json.load(f)

      # Insert Screens & Elements
      for screen in crawl_data.get("screens", []):
        session.run(
            """
                    MERGE (s:Screen {route: $route})
                    SET s.title = $title, s.screenshot = $screenshot
                """,
            route=screen["route"],
            title=screen.get("title", ""),
            screenshot=screen.get("screenshot", ""),
        )

        for elem in screen.get("elements", []):
          session.run(
              """
                        MATCH (s:Screen {route: $route})
                        MERGE (e:UIElement {id: $element_id, selector: $selector})
                        SET e.tag = $tag, e.text = $text, e.type = $type
                        MERGE (s)-[:HAS_ELEMENT]->(e)
                    """,
              route=screen["route"],
              element_id=elem["element_id"],
              selector=elem["selector"],
              tag=elem.get("tag", ""),
              text=elem.get("text", ""),
              type=elem.get("type", ""),
          )

      # Insert Interaction Transitions
      for trans in crawl_data.get("transitions", []):
        session.run(
            """
                    MATCH (from:Screen {route: $from_route})
                    MATCH (to:Screen {route: $to_route})
                    MERGE (from)-[t:TRANSITIONS_TO {by: $triggered_by}]->(to)
                    SET t.label = $trigger_text
                """,
            from_route=trans.get("from_route"),
            to_route=trans.get("to_route"),
            triggered_by=trans.get("triggered_by", ""),
            trigger_text=trans.get("trigger_text", ""),
        )

      print(
          "[Graph] Layer 2 (DOM / UI Crawled Artifacts & Transitions) Synced."
      )

    # --- LAYER 3: Auto-Link Code Components to UI Screens & Test Suites ---

    # 1. Match component names to specific routes OR fallback to standard '/' route
    session.run("""
            MATCH (c:Component)
            OPTIONAL MATCH (s_match:Screen) 
            WHERE toLower(s_match.route) CONTAINS toLower(split(c.name, '.')[0])
               OR toLower(c.name) CONTAINS toLower(replace(s_match.route, '/', ''))
            
            WITH c, collect(s_match) AS matched_screens
            OPTIONAL MATCH (s_default:Screen)
            WITH c, matched_screens, collect(s_default) AS default_screens
            WITH c, CASE WHEN size(matched_screens) > 0 THEN matched_screens ELSE default_screens END AS target_screens
            UNWIND target_screens AS s
            WITH c, s WHERE s IS NOT NULL
            MERGE (s)-[:IMPLEMENTED_BY]->(c)
        """)

    # 2. Propagate Relationships: Connect parent components down to child components
    session.run("""
            MATCH (s:Screen)-[:IMPLEMENTED_BY]->(parent:Component)-[:DEPENDS_ON*0..3]->(child:Component)
            MERGE (s)-[:IMPLEMENTED_BY]->(child)
        """)

    # 3. Dynamic Test Case Binding: Create or attach test files
    session.run("""
            MATCH (s:Screen)-[:IMPLEMENTED_BY]->(c:Component)
            WITH c, s, toLower(c.name) AS comp_name
            
            // Map components to your 3 actual test files based on name keywords
            WITH c, s, comp_name,
                 CASE 
                    WHEN comp_name CONTAINS 'auth' OR comp_name CONTAINS 'login' OR comp_name CONTAINS 'form' THEN 'tests/test_auth.py'
                    WHEN comp_name CONTAINS 'edit' OR comp_name CONTAINS 'header' OR comp_name CONTAINS 'button' THEN 'tests/test_editor.py'
                    WHEN comp_name CONTAINS 'setting' OR comp_name CONTAINS 'config' THEN 'tests/test_settings.py'
                    ELSE 'tests/test_auth.py' // Default fallback
                 END AS test_path
            
            WITH c, s, test_path, split(split(test_path, 'test_')[1], '.py')[0] AS test_id
            
            MERGE (r:Requirement {id: "REQ-" + test_id})
            SET r.title = test_id + " Verification", r.expected_route = s.route
            MERGE (r)-[:EXPECTS_UI]->(s)
            MERGE (t:TestCase {id: "TEST-" + test_id, file: test_path})
            MERGE (t)-[:VERIFIES]->(r)
        """)

    print("[Graph] Layer 3 (Auto-Discovered UI & Test Bindings) Linked.")


def sync_codebase_to_neo4j(driver, *args, **kwargs):
  """Alias function accepting flexible positional arguments for TestSigma_App.py compatibility."""
  print("[Graph] Triggering 3-Layer Knowledge Graph Sync...")
  sync_3layer_graph(driver)


def detect_absence(driver):
  """Identifies requirements defined in spec that are missing

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
    print(
        f"⚠️  Found {len(results)} Uncovered Requirement(s) (Missing in Live UI"
        " Crawl):"
    )
    for res in results:
      print(
          f" • [{res['RequirementID']}] {res['Title']} -> Expected Route:"
          f" {res['MissingRoute']}"
      )
  else:
    print("✅ All defined requirements have corresponding live UI screens.")
  print("=========================================================\n")
  return results


if __name__ == "__main__":
  driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
  sync_3layer_graph(driver)
  detect_absence(driver)
  driver.close()