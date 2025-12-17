from dotenv import load_dotenv
load_dotenv()

import os
import asyncio
import nest_asyncio
nest_asyncio.apply()  # Fix for Streamlit + asyncio multiple runs

import streamlit as st
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
from semantic_kernel.contents.chat_history import ChatHistory
from ContractPlugin import ContractPlugin
from ContractService import ContractSearchService
from semantic_kernel.connectors.ai.chat_completion_client_base import ChatCompletionClientBase
from semantic_kernel.connectors.ai.open_ai.prompt_execution_settings.open_ai_prompt_execution_settings import (
    OpenAIChatPromptExecutionSettings)
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.functions.kernel_arguments import KernelArguments
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)

# Get info from environment
OPENAI_KEY = os.getenv('OPENAI_API_KEY')
NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USER = os.getenv('NEO4J_USERNAME', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')
service_id = "contract_search"

# Streamlit app configuration
st.set_page_config(layout="wide")
st.title("📄 Q&A Chatbot for Contract Review")

# Initialize Kernel, Chat History, and Settings in Session State
if 'semantic_kernel' not in st.session_state:
    kernel = Kernel()
    contract_search_neo4j = ContractSearchService(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    kernel.add_plugin(ContractPlugin(contract_search_service=contract_search_neo4j), plugin_name="contract_search")
    kernel.add_service(OpenAIChatCompletion(ai_model_id="gpt-4o", api_key=OPENAI_KEY, service_id=service_id))

    settings: OpenAIChatPromptExecutionSettings = kernel.get_prompt_execution_settings_from_service_id(service_id=service_id)
    settings.function_choice_behavior = FunctionChoiceBehavior.Auto(filters={"included_plugins": ["contract_search"]})

    st.session_state.semantic_kernel = kernel
    st.session_state.kernel_settings = settings
    st.session_state.chat_history = ChatHistory()
    st.session_state.ui_chat_history = []

if 'user_question' not in st.session_state:
    st.session_state.user_question = ""

# Async agent response function
async def get_agent_response(user_input):
    kernel = st.session_state.semantic_kernel
    history = st.session_state.chat_history
    settings = st.session_state.kernel_settings

    history.add_user_message(user_input)
    st.session_state.ui_chat_history.append({"role": "user", "content": user_input})

    retry_attempts = 3
    for attempt in range(retry_attempts):
        try:
            chat_completion: OpenAIChatCompletion = kernel.get_service(type=ChatCompletionClientBase)
            result = (await chat_completion.get_chat_message_contents(
                chat_history=history,
                settings=settings,
                kernel=kernel,
            ))[0]

            history.add_message(result)
            st.session_state.ui_chat_history.append({"role": "agent", "content": str(result)})
            return
        except Exception as e:
            if attempt < retry_attempts - 1:
                time.sleep(0.2)
            else:
                st.session_state.ui_chat_history.append({"role": "agent", "content": f"Error: {str(e)}"})

# Synchronous wrapper to safely call async function in Streamlit
def run_agent_response(user_input):
    return asyncio.get_event_loop().run_until_complete(get_agent_response(user_input))

# Container for chat history
chat_placeholder = st.container()

def display_chat():
    with chat_placeholder:
        for chat in st.session_state.ui_chat_history:
            if chat['role'] == 'user':
                st.markdown(f"**User:** {chat['content']}")
            else:
                st.markdown(f"**Agent:** {chat['content']}")

# Form for user input
with st.form(key="user_input_form"):
    user_question = st.text_input("Enter your question:", value=st.session_state.user_question, key="user_question_")
    send_button = st.form_submit_button("Send")

if send_button and user_question.strip() != "":
    st.session_state.user_question = user_question
    run_agent_response(st.session_state.user_question)  # Use sync wrapper
    st.session_state.user_question = ""
    display_chat()
elif send_button:
    st.error("Please enter a question before sending.")

# Footer
st.markdown("---")
st.write("© 2025 SmartContractAI. All rights reserved.")
