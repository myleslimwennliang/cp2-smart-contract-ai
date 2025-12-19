import tempfile
import fitz
import os
from typing import List, Dict, Optional, Annotated
from AgreementSchema import Agreement, ClauseType
from semantic_kernel.functions import kernel_function
from ContractService import ContractSearchService
import asyncio
from semantic_kernel.contents import ChatHistory
from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings
from semantic_kernel.connectors.ai.chat_completion_client_base import ChatCompletionClientBase

class ContractPlugin:
    def __init__(self, contract_search_service: ContractSearchService, llm: Optional[ChatCompletionClientBase] = None):
        self.contract_search_service = contract_search_service
        self._llm = llm

    @kernel_function
    async def get_contract(self, contract_id: int) -> Annotated[Agreement, "A contract"]:
        return await self.contract_search_service.get_contract(contract_id)

    @kernel_function
    async def get_contracts(self, organization_name: str) -> Annotated[List[Agreement], "A list of contracts"]:
        return await self.contract_search_service.get_contracts(organization_name)

    @kernel_function
    async def get_contracts_without_clause(self, clause_type: ClauseType) -> Annotated[List[Agreement], "Contracts without a clause"]:
        return await self.contract_search_service.get_contracts_without_clause(clause_type=clause_type)

    @kernel_function
    async def get_contracts_with_clause_type(self, clause_type: ClauseType) -> Annotated[List[Agreement], "Contracts with a clause"]:
        return await self.contract_search_service.get_contracts_with_clause_type(clause_type=clause_type)

    @kernel_function
    async def get_contracts_similar_text(self, clause_text: str) -> Annotated[List[Agreement], "Contracts with similar text in a clause"]:
        return await self.contract_search_service.get_contracts_similar_text(clause_text=clause_text)

    @kernel_function
    async def answer_aggregation_question(self, user_question: str) -> Annotated[str, "Answer to a user question"]:
        return await self.contract_search_service.answer_aggregation_question(user_question=user_question)

    @kernel_function
    async def get_contract_excerpts(self, contract_id: int) -> Annotated[Agreement, "A contract with excerpts"]:
        return await self.contract_search_service.get_contract_excerpts(contract_id=contract_id)

    # --- Streamlit helpers ---

    def upload_contract(self, contract_name: str, uploaded_file) -> Dict:
        """
        Upload PDF contract to persistent storage and register metadata.
        """
        contracts_dir = os.path.join(os.getcwd(), "data/contracts")
        os.makedirs(contracts_dir, exist_ok=True)

        # Save temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.getbuffer())
            tmp_path = tmp.name

        dest_path = self.contract_search_service.add_contract(contract_name, tmp_path)
        return {"status": "success", "contract_name": contract_name, "file_path": dest_path}
    
    def get_all_contracts(self) -> List[Dict]:
        """
        Return all PDF contracts in persistent storage.
        """
        contracts_dir = os.path.join(os.getcwd(), "data/contracts")
        os.makedirs(contracts_dir, exist_ok=True)
        contracts = []
        for fname in os.listdir(contracts_dir):
            if fname.endswith(".pdf"):
                contracts.append({"name": fname, "file_path": os.path.join(contracts_dir, fname)})
        return contracts
    
    def summarize_contract(self, contract_path: str) -> str:
        """
        Extract text from PDF and generate a very short, simple summary for non-experts.
        """
        if not contract_path or not contract_path.endswith(".pdf"):
            return "Invalid contract file."

        # Step 1: Extract text
        try:
            text_content = ""
            with fitz.open(contract_path) as doc:
                for page in doc:
                    text_content += page.get_text()
            if not text_content.strip():
                return "Contract is empty or could not extract text."
        except Exception as e:
            return f"Failed to read PDF: {e}"

        # Step 2: Summarize using LLM
        if self._llm:
            try:
                prompt = f"Summarize the following contract very briefly in simple English so anyone can understand it. Only include main points:\n\n{text_content}"
                async def summarize_async():
                    settings = OpenAIChatPromptExecutionSettings()
                    chat_history = ChatHistory()
                    chat_history.add_user_message(prompt)
                    result = await self._llm.get_chat_message_contents(
                        chat_history=chat_history,
                        settings=settings,
                        kernel=None
                    )
                    return result[0].content if result else "Summary could not be generated."
                return asyncio.run(summarize_async())
            except Exception as e:
                return f"Failed to summarize with LLM: {e}"

        # Step 3: Fallback: first 1000 chars
        return text_content[:1000] + ("..." if len(text_content) > 1000 else "")
