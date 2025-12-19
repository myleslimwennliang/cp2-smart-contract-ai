import os
import json
from openai import OpenAI
from openai.types.beta.threads.message_create_params import Attachment, AttachmentToolFileSearch
from Utils import read_text_file, save_json_string_to_file, extract_json_from_string

# --------------------------
# 1. Initialize OpenAI client
# --------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("Please set the OPENAI_API_KEY environment variable.")

client = OpenAI(api_key=OPENAI_API_KEY)

# --------------------------
# 2. Load prompts
# --------------------------
system_instruction = read_text_file('./prompts/system_prompt.txt')
extraction_prompt = read_text_file('./prompts/contract_extraction_prompt.txt')

# --------------------------
# 3. Create the assistant
# --------------------------
MODEL_NAME = "gpt-4o-mini" 

pdf_assistant = client.beta.assistants.create(
    model=MODEL_NAME,
    description="An assistant to extract the information from contracts in PDF format.",
    tools=[{"type": "file_search"}],
    name="PDF assistant",
    instructions=system_instruction,
)

# --------------------------
# 4. Process a single PDF
# --------------------------
def process_pdf(pdf_path):
    # Create a thread for this PDF
    thread = client.beta.threads.create()

    # Upload the PDF
    file = client.files.create(file=open(pdf_path, "rb"), purpose="assistants")

    # Send a message to the assistant with the PDF attached
    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=extraction_prompt,
        attachments=[
            Attachment(
                file_id=file.id,
                tools=[AttachmentToolFileSearch(type="file_search")]
            )
        ],
    )

    # Run the assistant on the thread
    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread.id,
        assistant_id=pdf_assistant.id,
        timeout=1000
    )

    if run.status != "completed":
        raise Exception(f"Run failed: {run.status}")

    # Retrieve messages from thread
    messages_cursor = client.beta.threads.messages.list(thread_id=thread.id)
    messages = [msg for msg in messages_cursor]

    # Return the assistant's first text output
    return messages[0].content[0].text.value

# --------------------------
# 5. Main script
# --------------------------
def main():
    input_dir = './data/input/'
    debug_dir = './data/debug/'
    output_dir = './data/output/'

    os.makedirs(debug_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    pdf_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.pdf')]
    if not pdf_files:
        print("No PDF files found in", input_dir)
        return

    for pdf_filename in pdf_files:
        pdf_path = os.path.join(input_dir, pdf_filename)
        print(f"Processing {pdf_filename} with model {MODEL_NAME}...")

        try:
            complete_response = process_pdf(pdf_path)

            # Save raw response for debugging
            save_json_string_to_file(
                complete_response,
                os.path.join(debug_dir, f'complete_response_{pdf_filename}.json')
            )

            # Try to parse JSON
            contract_json = extract_json_from_string(complete_response)
            if contract_json:
                save_json_string_to_file(
                    contract_json,
                    os.path.join(output_dir, f'{pdf_filename}.json')
                )
                print(f"Saved extracted JSON for {pdf_filename}")
            else:
                print(f"No valid JSON extracted from {pdf_filename}")

        except Exception as e:
            print(f"Error processing {pdf_filename}: {e}")

# --------------------------
# 6. Entry point
# --------------------------
if __name__ == "__main__":
    main()
