from neo4j import GraphDatabase

URI = "neo4j+s://fae1ba87.databases.neo4j.io"
USER = "fae1ba87"  # <-- Change from "neo4j" to "fae1ba87"
PASSWORD = "gLVMYFlAVVyfSSanVcoxbYB23WHMzz-TfXUUhFHLUUY"

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

try:
    driver.verify_connectivity()
    print("SUCCESS: Connected to Neo4j successfully!")
except Exception as e:
    print(f"FAILED: {e}")
finally:
    driver.close()