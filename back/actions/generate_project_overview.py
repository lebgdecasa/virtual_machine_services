import base64
import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)


def create_overview_prompt(key_trends, description, final_analysis):
    return f"""
You are a business analyst helping founders summarize their venture ideas.

You will receive:
- A **product description** describing what the product is or does
- A **key trends** section summarizing market dynamics, behaviors, or macro shifts
- A **final analysis** section containing deeper insights, goals, pain points, or opportunities

Based on these, output a JSON object with the following keys:

- "Problem": A concise description of the core pain point being solved
- "Solution": How the product solves the problem
- "Competition": Existing tools, services, or market alternatives
- "Target_Market": Who this product is for (user personas, segments, or industries)
- "Business_Model": How the business intends to make money
- "Marketing_Strategy": How the product will reach its market
- "Unique_selling_point": What makes this product stand out compared to others

Only respond with a JSON object. Do not add any extra explanation.

---
**Key Trends:**
{key_trends}

**Product Description:**
{description}

**Final Analysis:**
{final_analysis}
"""

def generate_project_overview(prompt):
    api_key = os.environ.get("NEXT_PUBLIC_GEMINI_API_KEY")
    if not api_key:
        return {"error": "API key not found"}

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash-exp')

    generation_config = {
        "temperature": 0.6,
        "response_mime_type": "application/json",
    }

    response = model.generate_content(
        prompt,
        generation_config=generation_config
    )

    try:
        return json.loads(response.text)
    except json.JSONDecodeError:
        # Fallback to raw string if the model returns malformed JSON
        return response.text

if __name__ == "__main__":
    generate_project_overview()
