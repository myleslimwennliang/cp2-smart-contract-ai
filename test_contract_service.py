import asyncio
from AgreementSchema import ClauseType
from ContractService import ContractSearchService
import os

async def test_contract_service():
    # Initialize service
    uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
    user = os.getenv("NEO4J_USERNAME", "neo4j")
    pwd = os.getenv("NEO4J_PASSWORD")
    
    service = ContractSearchService(uri, user, pwd)
    
    # Test get_contract
    print("=== Testing get_contract(contract_id=1) ===")
    contract = await service.get_contract(contract_id=1)
    print(contract)
    
    # Test get_contracts by organization
    org_name = "Cybergy"  # example
    print(f"\n=== Testing get_contracts(organization_name='{org_name}') ===")
    contracts = await service.get_contracts(organization_name=org_name)
    for c in contracts:
        print(c)
    
    # Test get_contracts_with_clause_type for all clause types
    print("\n=== Testing get_contracts_with_clause_type for all ClauseType members ===")
    for clause_type in ClauseType:
        try:
            contracts = await service.get_contracts_with_clause_type(clause_type)
            print(f"\nClause Type: {clause_type.value}, Contracts Found: {len(contracts)}")
            for c in contracts:
                print(c)
        except Exception as e:
            print(f"Error testing clause type {clause_type.value}: {e}")
    
    # Test get_contracts_without_clause
    print("\n=== Testing get_contracts_without_clause for all ClauseType members ===")
    for clause_type in ClauseType:
        try:
            contracts = await service.get_contracts_without_clause(clause_type)
            print(f"\nClause Type: {clause_type.value}, Contracts Found: {len(contracts)}")
        except Exception as e:
            print(f"Error testing clause type {clause_type.value}: {e}")

if __name__ == "__main__":
    asyncio.run(test_contract_service())
