from neo4j import GraphDatabase
import os

uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
user = os.getenv("NEO4J_USERNAME", "neo4j")
pwd = os.getenv("NEO4J_PASSWORD")

print("Trying", uri, "user:", user)
try:
    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    driver.verify_connectivity()
    print("OK: Connected and authenticated")
    driver.close()
except Exception as e:
    print("CONNECT/AUTH ERROR:", type(e).__name__, e)
