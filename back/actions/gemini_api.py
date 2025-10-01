import base64
import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from the .env file in the project root
# Get the project root directory (3 levels up from this file)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)


def generate(prompt):
    api_key = os.getenv("NEXT_PUBLIC_GEMINI_API_KEY")
    if not api_key:
        return "Error: API key not found"

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')

    generation_config = {
        "response_mime_type": "text/plain",
    }

    # Note: Google Search tool is not available in the standard API
    # You may need to use a different approach for web search functionality
    response = model.generate_content(
        prompt,
        generation_config=generation_config
    )

    return response.text
