import os
import sys
import time
import json
import urllib.request
import subprocess
import argparse
import importlib.util
from dotenv import load_dotenv
from neo4j import GraphDatabase
from datetime import datetime
from sync_graph import sync_codebase_to_neo4j

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"), override=True)

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+s://fae1ba87.databases.neo4j.io")
NEO4J_USER = os.getenv("NEO4J_USER", "fae1ba87")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "gLVMYFlAVVyfSSanVcoxbYB23WHMzz-TfXUUhFHLUUY")
WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", os.getenv("TEAMS_WEBHOOK_URL", ""))

TEST_ROUTER = {
    "auth": {"module": "test_auth.py", "func": "run_auth_test"},
    "editor": {"module": "test_editor.py", "func": "run_editor_test"},
    "settings": {"module": "test_settings.py", "func": "run_settings_test"}
}

def send_webhook_alert(run_metadata, results):
    """Sends real-time execution notification to Slack or Teams."""
    if not WEBHOOK_URL:
        print("[Webhook Log] No SLACK_WEBHOOK_URL or TEAMS_WEBHOOK_URL set. Skipping notification.")
        return

    status_icon = "🟢" if run_metadata['failed'] == 0 else "🔴"
    message_text = (
        f"{status_icon} *Blast Radius Test Execution Complete*\n"
        f"*Timestamp:* {run_metadata['timestamp']} | *Duration:* {run_metadata['total_duration']:.2f}s\n"
        f"*Total:* {run_metadata['total']} | *Passed:* {run_metadata['passed']} | *Failed:* {run_metadata['failed']}\n"
    )

    payload = json.dumps({"text": message_text}).encode("utf-8")
    req = urllib.request.Request(WEBHOOK_URL, data=payload, headers={"Content-Type": "application/json"})
    
    try:
        with urllib.request.urlopen(req) as resp:
            print("[Webhook Log] Notification sent successfully.")
    except Exception as e:
        print(f"[Webhook Error] Failed to send alert: {e}")

def generate_html_report(results, run_metadata):
    """Generates standalone HTML execution report with embedded failure screenshots."""
    reports_dir = os.path.join(BASE_DIR, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    report_path = os.path.join(reports_dir, "latest_report.html")

    rows = ""
    for r in results:
        status_color = "#10B981" if r["status"] == "PASSED" else "#EF4444"
        screenshot_html = ""
        if r.get("screenshot"):
            screenshot_html = f"""
            <br><details style="margin-top: 5px;">
                <summary style="cursor:pointer; color:#38bdf8;">View Failure Screenshot</summary>
                <img src="data:image/png;base64,{r['screenshot']}" style="max-width:100%; margin-top:8px; border:1px solid #334155; border-radius:6px;" />
            </details>
            """
            
        rows += f"""
        <tr>
            <td><strong>{r['test_id']}</strong></td>
            <td><code>{r['file']}</code></td>
            <td style="color: {status_color}; font-weight: bold;">{r['status']}</td>
            <td>{r['details']} {screenshot_html}</td>
            <td>{r['duration']:.2f}s</td>
        </tr>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Blast Radius Test Execution Report</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 2rem; }}
            .container {{ max-width: 900px; margin: 0 auto; background: #1e293b; padding: 2rem; border-radius: 10px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.5); }}
            h1 {{ border-bottom: 2px solid #334155; padding-bottom: 0.5rem; color: #38bdf8; }}
            .summary {{ display: flex; gap: 1rem; margin-bottom: 1.5rem; }}
            .card {{ background: #334155; padding: 1rem; border-radius: 6px; flex: 1; text-align: center; }}
            .card h3 {{ margin: 0; font-size: 0.9rem; color: #94a3b8; }}
            .card p {{ margin: 0.5rem 0 0 0; font-size: 1.5rem; font-weight: bold; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
            th, td {{ padding: 0.75rem; text-align: left; border-bottom: 1px solid #334155; vertical-align: top; }}
            th {{ background: #0f172a; color: #94a3b8; }}
            code {{ background: #0f172a; padding: 2px 6px; border-radius: 4px; color: #e2e8f0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Blast Radius Execution Report</h1>
            <p><strong>Timestamp:</strong> {run_metadata['timestamp']} | <strong>Total Duration:</strong> {run_metadata['total_duration']:.2f}s</p>
            <div class="summary">
                <div class="card"><h3>TOTAL TESTS</h3><p>{run_metadata['total']}</p></div>
                <div class="card"><h3>PASSED</h3><p style="color:#10B981">{run_metadata['passed']}</p></div>
                <div class="card"><h3>FAILED</h3><p style="color:#EF4444">{run_metadata['failed']}</p></div>
            </div>
            <table>
                <thead>
                    <tr><th>Test ID</th><th>File</th><th>Status</th><th>Details</th><th>Duration</th></tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
    </body>
    </html>
    """
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"\n[Report Log] HTML Summary Report saved to: {report_path}")

def execute_dynamically(test_info, headed=False):
    """Dynamically resolves and runs target test script."""
    file_path = test_info["file"].lower()
    
    target_config = None
    for key, config in TEST_ROUTER.items():
        if key in file_path:
            target_config = config
            break
            
    if not target_config:
        target_config = TEST_ROUTER["auth"]

    script_path = os.path.join(BASE_DIR, "tests", target_config["module"])
    
    if not os.path.exists(script_path):
        return {"status": "FAILED", "details": "Test script file missing.", "screenshot": None}

    spec = importlib.util.spec_from_file_location("dynamic_test", script_path)
    test_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(test_module)
    
    runner_func = getattr(test_module, target_config["func"])
    try:
        return runner_func(headed=headed)
    except TypeError:
        return runner_func()

def record_test_result(driver, test_id, status, details):
    """Writes status and timestamp back to Neo4j."""
    update_query = """
    MATCH (t:TestCase {id: $test_id})
    SET t.last_execution_status = $status,
        t.last_execution_time = $timestamp,
        t.last_execution_details = $details
    RETURN t.id AS id
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with driver.session() as session:
        session.run(update_query, test_id=test_id, status=status, timestamp=timestamp, details=details)
        print(f"[Neo4j Log] Updated '{test_id}' with Status: {status} at {timestamp}")

def get_git_changed_files():
    try:
        result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True)
        if not result.stdout.strip():
            return []
        lines = result.stdout.strip().split("\n")
        return [os.path.basename(l.strip().split()[-1]) for l in lines if l.strip().endswith(('.js', '.ts', '.jsx', '.tsx'))]
    except Exception:
        return []

def get_all_test_cases(driver):
    query = "MATCH (t:TestCase) RETURN t.id AS TestID, t.file AS TestFile"
    with driver.session() as session:
        result = session.run(query)
        return [{"test_id": row["TestID"], "file": row["TestFile"]} for row in result]

def get_blast_radius(driver, modified_components):
    impact_query = """
    UNWIND $comp_names AS comp_name
    MATCH (c:Component)
    WHERE toLower(c.name) = toLower(comp_name)
    MATCH (c)<-[:USES_COMPONENT]-(rt:Route)<-[:IMPLEMENTED_BY]-(r:Requirement)<-[:VERIFIES]-(t:TestCase)
    RETURN DISTINCT t.id AS TestID, t.file AS TestFile, r.title AS Requirement, c.name AS Component
    """
    with driver.session() as session:
        result = session.run(impact_query, comp_names=modified_components)
        records = list(result)
        
        print(f"\n================ BLAST RADIUS REPORT ================")
        print(f"Target Components: {modified_components}")
        print(f"====================================================")
        
        if not records:
            print("No impacted tests found in Knowledge Graph for these changes.")
            return []
            
        test_info = []
        for row in records:
            print(f"-> Impacted Requirement: {row['Requirement']}")
            print(f"-> Selected Test File:   {row['TestFile']}")
            test_info.append({"test_id": row['TestID'], "file": row['TestFile']})
            
        return test_info

def execute_impacted_tests(driver, test_list, headed=False):
    print("\n================ EXECUTING TARGETED TESTS ================")
    
    start_time = time.time()
    results = []
    passed_count = 0
    failed_count = 0

    for test in test_list:
        test_start = time.time()
        print(f"Executing: {test['test_id']} ({test['file']})")
        
        res = execute_dynamically(test, headed=headed)
        duration = time.time() - test_start
        
        record_test_result(driver, test['test_id'], res['status'], res['details'])
        
        if res['status'] == 'PASSED':
            passed_count += 1
        else:
            failed_count += 1

        results.append({
            "test_id": test['test_id'],
            "file": test['file'],
            "status": res['status'],
            "details": res['details'],
            "screenshot": res.get("screenshot"),
            "duration": duration
        })

    total_duration = time.time() - start_time
    run_metadata = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(test_list),
        "passed": passed_count,
        "failed": failed_count,
        "total_duration": total_duration
    }

    print("\n================ EXECUTION DASHBOARD ================")
    print(f"Total Duration: {total_duration:.2f}s")
    print(f"Total: {len(test_list)} | Passed: {passed_count} | Failed: {failed_count}")
    print("=====================================================")

    generate_html_report(results, run_metadata)
    send_webhook_alert(run_metadata, results)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TestSigma AI Blast Radius Engine")
    parser.add_argument("--headed", action="store_true", help="Run Playwright browser visually in headed mode")
    parser.add_argument("--force-all", action="store_true", help="Bypass blast radius and run all test cases in graph")
    parser.add_argument("--file", type=str, help="Manually specify a changed component file")
    parser.add_argument("--skip-sync", action="store_true", help="Skip AST Neo4j code sync")
    
    args = parser.parse_args()
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    if not args.skip_sync:
        sync_codebase_to_neo4j(driver, BASE_DIR)

    if args.force_all:
        print("\n[CLI Override] Running ALL test cases in Knowledge Graph...")
        impacted_tests = get_all_test_cases(driver)
    elif args.file:
        print(f"\n[CLI Override] Targeting specified component file: {args.file}")
        impacted_tests = get_blast_radius(driver, [args.file])
    else:
        changed_files = get_git_changed_files()
        if not changed_files:
            changed_files = ["AuthForm.js"]
        impacted_tests = get_blast_radius(driver, changed_files)
        
    if impacted_tests:
        execute_impacted_tests(driver, impacted_tests, headed=args.headed)
        
    driver.close()