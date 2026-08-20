import os
import re
from neo4j import GraphDatabase

NEO4J_URI = os.getenv("NEO4J_URI") or "neo4j+s://fae1ba87.databases.neo4j.io"
NEO4J_USER = os.getenv("NEO4J_USER") or "fae1ba87"
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD") or "gLVMYFlAVVyfSSanVcoxbYB23WHMzz-TfXUUhFHLUUY"

# Simple RegEx AST parser for JS/JSX/TS/TSX ES6 imports
IMPORT_REGEX = re.compile(r'import\s+.*?\s+from\s+[\'"](.*?)[\'"]', re.MULTILINE)

def parse_component_dependencies(source_dir):
    """
    Scans JS/JSX/TS/TSX files for relative imports 
    and returns a list of (parent_file, imported_file) pairs.
    """
    dependencies = []
    
    if not os.path.exists(source_dir):
        return dependencies

    for root, _, files in os.walk(source_dir):
        for file in files:
            if file.endswith(('.js', '.jsx', '.ts', '.tsx')):
                full_path = os.path.join(root, file)
                parent_comp = os.path.basename(file)
                
                try:
                    with open(full_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    matches = IMPORT_REGEX.findall(content)
                    for import_path in matches:
                        # Extract relative component imports (e.g. ./Input -> Input.js)
                        if import_path.startswith('.'):
                            imported_comp = os.path.basename(import_path)
                            if not imported_comp.endswith(('.js', '.jsx', '.ts', '.tsx')):
                                imported_comp += '.js' # Default extension assumption
                                
                            dependencies.append({
                                "parent": parent_comp,
                                "child": imported_comp
                            })
                except Exception as e:
                    print(f"[AST] Warning: Failed to parse {file}: {e}")

    return dependencies

def sync_ast_to_neo4j(driver, source_dir="src"):
    """
    Links child dependencies to parent components in Neo4j.
    """
    deps = parse_component_dependencies(source_dir)
    if not deps:
        print("[AST] No JS/JSX components found to parse (or directory 'src' does not exist).")
        return

    with driver.session() as session:
        for dep in deps:
            session.run("""
                MERGE (p:Component {name: $parent})
                MERGE (c:Component {name: $child})
                MERGE (p)-[:DEPENDS_ON]->(c)
            """, parent=dep["parent"], child=dep["child"])
            
    print(f"[AST] Synced {len(deps)} component dependency relationship(s) into Knowledge Graph.")

if __name__ == "__main__":
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    sync_ast_to_neo4j(driver)
    driver.close()