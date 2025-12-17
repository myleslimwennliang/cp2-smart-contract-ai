import base64
import re
import json

def open_as_bytes(pdf_filename: str) -> str:
    with open(pdf_filename, 'rb') as pdf_file:
        pdf_bytes = pdf_file.read()
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')  # decode to string
    return pdf_base64

def read_text_file(file_path):
    # Open the file in read mode
    with open(file_path, 'r') as file:
        file_content = file.read()
    return file_content

def extract_json_from_string(input_string):
    try:
        # Remove ```json block markers if present
        input_string = re.sub(r'^```json\s*|\s*```$', '', input_string, flags=re.DOTALL)
        return json.loads(input_string)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        return None


def save_json_string_to_file(data, file_path):
    """
    Saves a Python dict or a JSON string to a file.
    """
    with open(file_path, 'w', encoding='utf-8') as file:
        if isinstance(data, dict):
            json.dump(data, file, indent=4)
        elif isinstance(data, str):
            file.write(data)
        else:
            raise TypeError(f"Cannot save object of type {type(data)}")

