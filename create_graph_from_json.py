#!/usr/bin/env python3
import os
import json
import sys
from neo4j import GraphDatabase, exceptions

# -------------------------
# Cypher and constants
# -------------------------
CREATE_GRAPH_STATEMENT = """
WITH $data AS data
WITH data.agreement as a
MERGE (agreement:Agreement {contract_id: a.contract_id})
ON CREATE SET 
  agreement.name = a.agreement_name,
  agreement.effective_date = a.effective_date,
  agreement.expiration_date = a.expiration_date,
  agreement.agreement_type = a.agreement_type,
  agreement.renewal_term = a.renewal_term,
  agreement.most_favored_country = a.governing_law.most_favored_country

MERGE (gl_country:Country {name: a.governing_law.country})
MERGE (agreement)-[gbl:GOVERNED_BY_LAW]->(gl_country)
SET gbl.state = a.governing_law.state

FOREACH (party IN a.parties |
  MERGE (p:Organization {name: party.name})
  MERGE (p)-[ipt:IS_PARTY_TO]->(agreement)
  SET ipt.role = party.role
  MERGE (country_of_incorporation:Country {name: party.incorporation_country})
  MERGE (p)-[incorporated:INCORPORATED_IN]->(country_of_incorporation)
  SET incorporated.state = party.incorporation_state
)

WITH a, agreement, [clause IN a.clauses WHERE clause.exists = true] AS valid_clauses
FOREACH (clause IN valid_clauses |
  CREATE (cl:ContractClause {type: clause.clause_type})
  MERGE (agreement)-[clt:HAS_CLAUSE]->(cl)
  SET clt.type = clause.clause_type
  FOREACH (excerpt IN clause.excerpts |
    MERGE (cl)-[:HAS_EXCERPT]->(e:Excerpt {text: excerpt})
  )
  MERGE (clType:ClauseType{name: clause.clause_type})
  MERGE (cl)-[:HAS_TYPE]->(clType)
)
"""

CREATE_VECTOR_INDEX_STATEMENT = """
CREATE VECTOR INDEX excerpt_embedding IF NOT EXISTS 
    FOR (e:Excerpt) ON (e.embedding) 
    OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`:'cosine'}} 
"""

CREATE_FULL_TEXT_INDICES = [
    ("excerptTextIndex", "CREATE FULLTEXT INDEX excerptTextIndex IF NOT EXISTS FOR (e:Excerpt) ON EACH [e.text]"),
    ("agreementTypeTextIndex", "CREATE FULLTEXT INDEX agreementTypeTextIndex IF NOT EXISTS FOR (a:Agreement) ON EACH [a.agreement_type]"),
    ("clauseTypeNameTextIndex", "CREATE FULLTEXT INDEX clauseTypeNameTextIndex IF NOT EXISTS FOR (ct:ClauseType) ON EACH [ct.name]"),
    ("clauseNameTextIndex", "CREATE FULLTEXT INDEX contractClauseTypeTextIndex IF NOT EXISTS FOR (c:ContractClause) ON EACH [c.type]"),
    ("organizationNameTextIndex", "CREATE FULLTEXT INDEX organizationNameTextIndex IF NOT EXISTS FOR (o:Organization) ON EACH [o.name]"),
    ("contractIdIndex","CREATE INDEX agreementContractId IF NOT EXISTS FOR (a:Agreement) ON (a.contract_id) ")
]

EMBEDDINGS_STATEMENT = """
MATCH (e:Excerpt) 
WHERE e.text is not null and e.embedding is null
SET e.embedding = genai.vector.encode(e.text, "OpenAI", { 
                    token: $token, model: "text-embedding-3-small", dimensions: 1536
                  })
"""

# -------------------------
# Helpers
# -------------------------
def index_exists(driver, index_name):
    check_index_query = "SHOW INDEXES WHERE name = $index_name"
    result = driver.execute_query(check_index_query, {"index_name": index_name})
    return len(result.records) > 0

def create_full_text_indices(driver):
    for index_name, create_query in CREATE_FULL_TEXT_INDICES:
        try:
            if not index_exists(driver, index_name):
                print(f"Creating index: {index_name}")
                driver.execute_query(create_query)
            else:
                print(f"Index {index_name} already exists.")
        except Exception as ex:
            print(f"[WARN] Could not ensure index {index_name}: {ex}")

# -------------------------
# Configure runtime paths and env
# -------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_CONTRACT_FOLDER = os.path.join(BASE_DIR, "data", "output")

# Prefer explicit IPv4 to avoid localhost -> ::1 resolution issues
NEO4J_URI = (os.getenv("NEO4J_URI") or "bolt://127.0.0.1:7687").strip()
NEO4J_USER = (os.getenv("NEO4J_USERNAME") or "neo4j").strip()
NEO4J_PASSWORD = (os.getenv("NEO4J_PASSWORD") or "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not NEO4J_PASSWORD:
    print("ERROR: NEO4J_PASSWORD environment variable not set. Set it and re-run.")
    sys.exit(1)

# -------------------------
# Create driver and verify
# -------------------------
print(f"Connecting to Neo4j at {NEO4J_URI} as user '{NEO4J_USER}' ...")
try:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    # quick connectivity check to give a clear, immediate error if DB is unreachable
    driver.verify_connectivity()
    print("Successfully connected to Neo4j.")
except exceptions.ServiceUnavailable as svc_ex:
    print("ERROR: Could not reach Neo4j service. ServiceUnavailable:", svc_ex)
    print(" - Make sure Neo4j is running and listening on the URL above.")
    print(" - If using 'localhost', try setting NEO4J_URI to 'bolt://127.0.0.1:7687' explicitly.")
    sys.exit(1)
except exceptions.AuthError as auth_ex:
    print("ERROR: Authentication to Neo4j failed:", auth_ex)
    sys.exit(1)
except Exception as e:
    print("ERROR: Unexpected error creating Neo4j driver:", type(e).__name__, e)
    sys.exit(1)

# -------------------------
# Validate input folder
# -------------------------
if not os.path.isdir(JSON_CONTRACT_FOLDER):
    print(f"ERROR: JSON folder not found at {JSON_CONTRACT_FOLDER}")
    print(" - Ensure the folder exists and contains JSON contract files.")
    sys.exit(1)

json_contracts = [f for f in os.listdir(JSON_CONTRACT_FOLDER) if f.lower().endswith(".json")]
if not json_contracts:
    print(f"No JSON contract files found in {JSON_CONTRACT_FOLDER}. Nothing to import.")
    sys.exit(0)

# -------------------------
# Ingest JSON files
# -------------------------
contract_id = 1
for json_contract in json_contracts:
    file_path = os.path.join(JSON_CONTRACT_FOLDER, json_contract)
    print(f"Importing {file_path} ...")
    try:
        with open(file_path, "r", encoding="utf-8") as fh:
            json_data = json.load(fh)
    except Exception as e:
        print(f"Failed to read/parse {file_path}: {e}")
        continue

    # add a contract_id if missing
    agreement = json_data.get("agreement", {})
    if "contract_id" not in agreement:
        agreement["contract_id"] = contract_id
        # ensure the change is present in the param map we pass to the query
        json_data["agreement"] = agreement

    try:
        driver.execute_query(CREATE_GRAPH_STATEMENT, data=json_data)
        print(f"Inserted graph data for {json_contract}")
    except exceptions.ServiceUnavailable as svc_ex:
        print(f"[ERROR] Neo4j ServiceUnavailable while inserting {json_contract}: {svc_ex}")
        print(" - Check that Neo4j is still running and reachable.")
        break
    except Exception as e:
        print(f"[ERROR] Failed to execute graph statement for {json_contract}: {e}")
        # continue processing other files
    contract_id += 1

# -------------------------
# Create indices & embeddings
# -------------------------
try:
    create_full_text_indices(driver)
    print("Ensuring vector index (this may fail if your Neo4j version doesn't support vector indexes)...")
    try:
        driver.execute_query(CREATE_VECTOR_INDEX_STATEMENT)
    except Exception as e:
        print(f"[WARN] Could not create vector index: {e}")

    print("Generating embeddings for excerpts (if any)...")
    if OPENAI_API_KEY:
        try:
            driver.execute_query(EMBEDDINGS_STATEMENT, token=OPENAI_API_KEY)
            print("Embeddings job submitted.")
        except Exception as e:
            print(f"[WARN] Could not execute embeddings statement: {e}")
    else:
        print("[INFO] OPENAI_API_KEY not set — skipping embeddings.")
except Exception as e:
    print("[WARN] Error while creating indices or embeddings:", e)

print("Done.")
