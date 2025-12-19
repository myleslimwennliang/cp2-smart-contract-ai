from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import os
import asyncio
import fitz
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
from semantic_kernel.contents import ChatHistory
from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings
from ContractPlugin import ContractPlugin
from ContractService import ContractSearchService

# -----------------------------
# Streamlit setup
# -----------------------------
st.set_page_config(layout="wide")
st.title("📄 Contract Q&A Chatbot")

# Load OpenAI key
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_KEY:
    st.error("OPENAI_API_KEY not set in environment!")
    st.stop()

# Initialize Kernel & Session State
if "semantic_kernel" not in st.session_state:
    kernel = Kernel()
    contract_service = ContractSearchService("bolt://localhost:7687", "neo4j", os.getenv("NEO4J_PASSWORD"))
    
    # Add LLM service
    llm = OpenAIChatCompletion(ai_model_id="gpt-4o-mini", api_key=OPENAI_KEY)
    kernel.add_service(llm)
    
    # Add ContractPlugin
    contract_plugin = ContractPlugin(contract_search_service=contract_service, llm=llm)
    kernel.add_plugin(contract_plugin, plugin_name="contract_search")
    
    st.session_state.semantic_kernel = kernel
    st.session_state.contract_plugin = contract_plugin
    st.session_state.chat_history = []
    st.session_state.selected_contract = None

# -----------------------------
# Contract Upload
# -----------------------------
st.subheader("Upload a Contract")
uploaded_file = st.file_uploader("Choose a PDF", type=["pdf"])
contract_name_input = st.text_input("Contract Name:")

if st.button("Upload Contract"):
    if uploaded_file and contract_name_input.strip() != "":
        result = st.session_state.contract_plugin.upload_contract(contract_name_input, uploaded_file)
        st.success(f"Contract uploaded: {contract_name_input}")
        st.json(result)
    else:
        st.error("Please provide both a contract file and a name.")

# -----------------------------
# List and Select Contracts
# -----------------------------
st.subheader("Available Contracts")
contracts = st.session_state.contract_plugin.get_all_contracts()
if contracts:
    contract_names = [c["name"] for c in contracts]
    selected_name = st.selectbox("Select a contract to ask about:", contract_names)
    st.session_state.selected_contract = next((c for c in contracts if c["name"] == selected_name), None)
else:
    st.info("No contracts available yet.")

# -----------------------------
# Summarize Selected Contract
# -----------------------------
if st.session_state.selected_contract:
    if st.button("Summarize Selected Contract"):
        summary = st.session_state.contract_plugin.summarize_contract(st.session_state.selected_contract["file_path"])
        st.markdown("**Summary:**")
        st.write(summary)

# -----------------------------
# Ask Questions About Contract
# -----------------------------
st.subheader("Ask About Contract")
question_input = st.text_input("Your question:")

async def ask_question(question, contract_path):
    """
    Sends question and contract text to LLM for answer.
    """
    plugin = st.session_state.contract_plugin
    # Extract text from PDF
    try:
        text_content = ""
        with fitz.open(contract_path) as doc:
            for page in doc:
                text_content += page.get_text()
        if not text_content.strip():
            return "Contract is empty or could not extract text."
    except Exception as e:
        return f"Failed to read PDF: {e}"

    prompt = f"Answer this question simply for a non-expert. Contract:\n{text_content}\n\nQuestion: {question}"
    settings = OpenAIChatPromptExecutionSettings()
    chat_history = ChatHistory()
    chat_history.add_user_message(prompt)
    result = await plugin._llm.get_chat_message_contents(
        chat_history=chat_history,
        settings=settings,
        kernel=None
    )
    return result[0].content if result else "No answer generated."

if st.button("Ask Question") and question_input.strip() != "" and st.session_state.selected_contract:
    answer = asyncio.run(ask_question(question_input, st.session_state.selected_contract["file_path"]))
    st.markdown("**Answer:**")
    st.write(answer)

# Footer
st.markdown("---")
st.write("© 2025 SmartContractAI.")
