import os
import re
from dotenv import load_dotenv
from neo4j import GraphDatabase

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"), override=True)

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+s://fae1ba87.databases.neo4j.io")
NEO4J_USER = os.getenv("NEO4J_USER", "fae1ba87")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "gLVMYFlAVVyfSSanVcoxbYB23WHMzz-TfXUUhFHLUUY")

def parse_js_imports(file_path):
    """Scans a JavaScript file for imported components using AST-like regex patterns."""
    dependencies = []
    
    # Regex to capture named or default imports: import Component from './Component'
    import_pattern = re.compile(r'import\s+(?:\{?[^}]*\}?|\w+)\s+from\s+[\'"]\.\/([^\'"]+)[\'"]')
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            matches = import_pattern.findall(content)
            for m in matches:
                # Ensure .js extension is attached
                comp_name = m if m.endswith('.js') else f"{m}.js"
                dependencies.append(comp_name)
    except Exception as e:
        print(f"[AST Error] Could not parse {file_path}: {e}")
        
    return dependencies

def sync_codebase_to_neo4j(driver, repo_dir):
    """Scans repository files and updates component relationships in Neo4j."""
    print("\n================ AST CODE-TO-GRAPH SYNC ================")
    
    components_found = 0
    relationships_created = 0
    
    for root, _, files in os.walk(repo_dir):
        for file in files:
            if file.endswith(('.js', '.jsx', '.ts', '.tsx')):
                components_found += 1
                source_comp = file
                file_path = os.path.join(root, file)
                
                dependencies = parse_js_imports(file_path)
                
                with driver.session() as session:
                    # 1. Merge the Component Node
                    session.run(
                        "MERGE (c:Component {name: $name})",
                        name=source_comp
                    )
                    
                    # 2. Merge dependency edges: (ParentComponent)-[:DEPENDS_ON]->(ChildComponent)
                    for dep in dependencies:
                        session.run("""
                            MERGE (parent:Component {name: $parent_name})
                            MERGE (child:Component {name: $child_name})
                            MERGE (parent)-[:DEPENDS_ON]->(child)
                        """, parent_name=source_comp, child_name=dep)
                        relationships_created += 1
                        print(f"-> Synced Link: ({source_comp}) -[:DEPENDS_ON]-> ({dep})")

    print(f"=======================================================")
    print(f"Sync Complete: Processed {components_found} components and updated {relationships_created} dependency relationships in Neo4j.")

if __name__ == "__main__":
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    sync_codebase_to_neo4j(driver, BASE_DIR)
    driver.close()