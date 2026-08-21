import json
import os
import subprocess
import sys
from datetime import datetime
from neo4j import GraphDatabase
from sync_graph import detect_absence, sync_codebase_to_neo4j

# --- CONFIGURATION & ENV SETUP ---
NEO4J_URI = os.getenv("NEO4J_URI") or "neo4j+s://fae1ba87.databases.neo4j.io"
NEO4J_USER = os.getenv("NEO4J_USER") or "fae1ba87"
NEO4J_PASSWORD = (
    os.getenv("NEO4J_PASSWORD") or "gLVMYFlAVVyfSSanVcoxbYB23WHMzz-TfXUUhFHLUUY"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPORT_FILE = os.path.join(BASE_DIR, "latest_report.html")


def get_modified_components():
  """Detects modified/staged component files using git status.

  Filters out non-JS/TS files and extracts clean base filenames.
  """
  try:
    output = subprocess.check_output(
        ["git", "status", "--porcelain"], text=True
    )
    files = []
    valid_extensions = (".js", ".jsx", ".ts", ".tsx")

    for line in output.splitlines():
      line = line.strip()
      if not line:
        continue

      parts = line.split(maxsplit=1)
      if len(parts) == 2:
        raw_path = parts[1]

        # Filter for valid source components and ignore test files/pycache
        if raw_path.endswith(
            valid_extensions
        ) and not raw_path.startswith("tests/"):
          filename = os.path.basename(raw_path)
          files.append(filename)

    return list(set(files))
  except Exception as e:
    print(
        f"[Git] Warning: Failed to check git status ({e}). Falling back to"
        " empty list."
    )
    return []


def calculate_blast_radius(driver, modified_files, force_all=False):
  """Traverses Neo4j 3-Layer Graph to find impacted UI screens, at-risk

  requirements, and targeting test cases. Flags affected nodes as :Impacted so
  they render red in Neo4j Browser.
  """
  with driver.session() as session:
    # Step 1: Safely clear previous graph styling state
    clear_query = """
        MATCH (n)
        WHERE n.is_affected = true OR 'Impacted' IN labels(n)
        REMOVE n:Impacted
        SET n.is_affected = false
        """
    session.run(clear_query)

    # Step 2: Query blast radius and apply :Impacted label to affected graph entities
    if force_all or not modified_files:
      query = """
            MATCH (t:TestCase)-[:VERIFIES]->(r:Requirement)-[:EXPECTS_UI]->(s:Screen)
            OPTIONAL MATCH (s)-[:IMPLEMENTED_BY]->(c:Component)
            
            // Highlight all nodes in red
            WITH t, r, s, c
            UNWIND [t, r, s, c] AS node
            WITH node, t, r, s, c WHERE node IS NOT NULL
            SET node:Impacted, node.is_affected = true
            
            RETURN DISTINCT 
                t.id AS test_id, 
                t.file AS test_file, 
                r.title AS requirement, 
                s.route AS route, 
                coalesce(c.name, "Unlinked Component") AS component
            """
      params = {}
    else:
      query = """
            MATCH (c:Component)
            WHERE c.name IN $modified_files 
               OR c.full_path IN $modified_files
               OR toLower(c.name) IN [m IN $modified_files | toLower(m)]
               OR toLower(c.name) CONTAINS toLower(split($modified_files[0], '.')[0])
            
            OPTIONAL MATCH (parent:Component)-[:DEPENDS_ON*0..3]->(c)
            WITH c, parent
            MATCH (target:Component) WHERE target = c OR target = parent
            
            OPTIONAL MATCH (s:Screen)-[:IMPLEMENTED_BY]->(target)
            OPTIONAL MATCH (t:TestCase)-[:VERIFIES]->(r:Requirement)-[:EXPECTS_UI]->(s)
            
            // Highlight all matched & traversed nodes in red
            WITH c, parent, target, s, r, t
            UNWIND [c, parent, target, s, r, t] AS node
            WITH node, c, s, r, t WHERE node IS NOT NULL
            SET node:Impacted, node.is_affected = true
            
            RETURN DISTINCT 
                t.id AS test_id, 
                t.file AS test_file, 
                r.title AS requirement, 
                s.route AS route, 
                c.name AS component
            """
      params = {"modified_files": modified_files}

    results = session.run(query, **params).data()
  return results

def run_targeted_tests(impacted_tests):
  """Executes targeted Pytest/Playwright test suites for impacted paths."""
  if not impacted_tests:
    print("[Execution] No tests triggered.")
    return []

  test_files = list(
      set([t["test_file"] for t in impacted_tests if t.get("test_file")])
  )
  results = []

  print(
      f"\n[Execution] Triggering {len(test_files)} impacted test suite(s)..."
  )
  for test_file in test_files:
    target_path = os.path.join(BASE_DIR, test_file)
    if os.path.exists(target_path):
      print(f" ► Running: pytest {test_file}")
      res = subprocess.run(
          ["pytest", target_path], capture_output=True, text=True
      )
      status = "PASSED" if res.returncode == 0 else "FAILED"
      results.append(
          {"file": test_file, "status": status, "output": res.stdout}
      )
    else:
      print(f" ⚠️ Test file not found on disk: {test_file}")
      results.append(
          {"file": test_file, "status": "SKIPPED (File Not Found)", "output": ""}
      )

  return results


def generate_html_report(
    modified_files, impacted_tests, absence_report, execution_results
):
  """Generates a visual HTML report summarizing Blast Radius and Test Results."""
  now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

  html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>TestSigma Blast Radius & Execution Report</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 30px; background: #f8f9fa; color: #333; }}
            .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}
            h1 {{ color: #0d6efd; margin-top: 0; }}
            h2 {{ color: #495057; border-bottom: 2px solid #e9ecef; padding-bottom: 8px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ text-align: left; padding: 10px; border-bottom: 1px solid #dee2e6; }}
            th {{ background: #f1f3f5; }}
            .badge-pass {{ background: #d1e7dd; color: #0f5132; padding: 4px 8px; border-radius: 4px; font-weight: bold; }}
            .badge-fail {{ background: #f8d7da; color: #842029; padding: 4px 8px; border-radius: 4px; font-weight: bold; }}
            .badge-warn {{ background: #fff3cd; color: #664d03; padding: 4px 8px; border-radius: 4px; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🚀 TestSigma Autonomous Blast-Radius Engine</h1>
            <p><strong>Generated At:</strong> {now}</p>
            <p><strong>Modified Components:</strong> <code>{', '.join(modified_files) if modified_files else 'FORCE ALL RUN / NONE'}</code></p>
        </div>

        <div class="card">
            <h2>🎯 Impacted Blast Radius (3-Layer Graph Traversal)</h2>
            <table>
                <tr><th>Test ID</th><th>Requirement</th><th>Target Route</th><th>Component</th><th>Test File</th></tr>
    """

  if impacted_tests:
    for item in impacted_tests:
      html += f"""
                <tr>
                    <td><b>{item['test_id']}</b></td>
                    <td>{item['requirement']}</td>
                    <td><code>{item['route']}</code></td>
                    <td><code>{item['component']}</code></td>
                    <td><code>{item['test_file']}</code></td>
                </tr>
            """
  else:
    html += (
        "<tr><td colspan='5'>No impacted workflows identified for these"
        " changes.</td></tr>"
    )

  html += """
            </table>
        </div>

        <div class="card">
            <h2>⚠️ Absence Modeling Analysis</h2>
    """

  if absence_report:
    html += (
        "<table><tr><th>Requirement ID</th><th>Requirement Title</th><th>Expected"
        " Route</th></tr>"
    )
    for abs_item in absence_report:
      html += (
          f"<tr><td><span"
          f" class='badge-warn'>{abs_item['RequirementID']}</span></td><td>{abs_item['Title']}</td><td><code>{abs_item['MissingRoute']}</code></td></tr>"
      )
    html += "</table>"
  else:
    html += (
        "<p><span class='badge-pass'>✅ Perfect Coverage:</span> All defined"
        " specifications match captured live UI screens.</p>"
    )

  html += """
        </div>
    </body>
    </html>
    """

  with open(REPORT_FILE, "w", encoding="utf-8") as f:
    f.write(html)
  print(f"[Report] Visual HTML report updated: {REPORT_FILE}")


def run_blast_radius_engine(force_all=False):
  driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

  # 1. Sync 3-Layer Graph
  sync_codebase_to_neo4j(driver, BASE_DIR)

  # 2. Detect Modified Components
  modified_files = get_modified_components()

  print("\n================ BLAST RADIUS REPORT ================")
  print(
      f"Target Components Detected:"
      f" {modified_files if not force_all else 'FORCE ALL RUN'}"
  )
  print("====================================================")

  # 3. Calculate Graph Blast Radius and apply :Impacted label
  impacted_tests = calculate_blast_radius(
      driver, modified_files, force_all=force_all
  )

  if not impacted_tests:
    print("No impacted tests found in Knowledge Graph for these changes.")
  else:
    print(f"Found {len(impacted_tests)} impacted workflow(s):")
    for test in impacted_tests:
      print(
          f" • [{test['test_id']}] Requirement: '{test['requirement']}' -> Test:"
          f" {test['test_file']}"
      )

  # 4. Absence Modeling Check
  absence_data = detect_absence(driver)

  # 5. Targeted Execution & HTML Report Generation
  execution_results = run_targeted_tests(impacted_tests)
  generate_html_report(
      modified_files, impacted_tests, absence_data, execution_results
  )

  driver.close()


if __name__ == "__main__":
  force_flag = "--force-all" in sys.argv
  run_blast_radius_engine(force_all=force_flag)