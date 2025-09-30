# llm_checks.py
import os
import json
import traceback
from typing import Dict, List, Any
from typing_extensions import TypedDict
import google.generativeai as genai
import logging
import re
from dotenv import load_dotenv

# Load environment variables from the .env file in the project root
# Get the project root directory (3 levels up from this file)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class DimensionInfo(TypedDict):
    id: str
    name: str
    description: str
    # prompt: str # Prompt field might not be needed for the check itself
    # keywords: List[str] # Keywords are no longer used for checking

class DimensionStatus(TypedDict):
    dimension_id: str
    status: str # Expect "answered" or "not answered"

def check_pitch_dimensions_with_llm(
    user_description: str,
    dimensions: List[DimensionInfo]
) -> Dict[str, bool]:
    """
    Calls the Gemini API to check which dimensions are covered by the description.

    Args:
        user_description: The user's pitch text.
        dimensions: A list of dimensions (id, name, description) to check against.

    Returns:
        A dictionary mapping dimension_id to boolean (True if 'answered').
    """
    results: Dict[str, bool] = {dim['id']: False for dim in dimensions} # Default to False

    if not user_description or not dimensions:
        log.info("No description or dimensions provided for LLM check.")
        return results

    # --- 1) Build the dynamic prompt ---
    dimension_list_str = ""
    for i, dim in enumerate(dimensions):
        dimension_list_str += f"{i+1}. ID: \"{dim['id']}\", Name: \"{dim['name']}\", Description: \"{dim['description']}\"\n"

    prompt_str = f"""
You are an expert pitch deck analyst. You need to determine if the user's project description adequately addresses several key dimensions.

Here are the dimensions to check:
--- DIMENSIONS START ---
{dimension_list_str}
--- DIMENSIONS END ---

Here is the user's project description:
--- DESCRIPTION START ---
{user_description}
--- DESCRIPTION END ---

Rules for deciding if a dimension is "answered":
- The description must contain specific, relevant information directly addressing the dimension's description or name.
- A simple mention of a related keyword is NOT enough; the substance of the dimension must be discussed.
- If the information is present and addresses the core of the dimension, mark it as "answered".
- Otherwise, mark it as "not answered".

Rules for output:
- Return ONLY a valid JSON array containing an object for EACH dimension listed above.
- Each object MUST have the exact keys "dimension_id" (matching the ID from the list) and "status" (with the value "answered" or "not answered").
- Do NOT include any other text, commentary, or explanations outside the JSON array.
- Ensure the output is a single, valid JSON array.

Example JSON object format within the array:
{{ "dimension_id": "some_id_from_list", "status": "answered" }}
{{ "dimension_id": "another_id", "status": "not answered" }}

Required output format: A JSON array of objects like the examples above.
"""

    # --- 2) Initialize the Gemini client ---
    api_key = os.getenv("NEXT_PUBLIC_GEMINI_API_KEY")
    if not api_key:
        log.error("NEXT_PUBLIC_GEMINI_API_KEY environment variable not set.")
        return results # Return defaults on API key error

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash-lite')
    except Exception as e:
        log.error(f"Failed to initialize Gemini client: {e}")
        return results

    # --- 3) Prepare the generation config ---
    generation_config = {
        "temperature": 0.1,
        "response_mime_type": "application/json",
    }

    # --- 4) Call the API ---
    response_str = ""
    log.info(f"Sending pitch description (length: {len(user_description)}) and {len(dimensions)} dimensions for analysis.")
    try:
        response = model.generate_content(
            prompt_str,
            generation_config=generation_config
        )
        response_str = response.text
        log.info(f"Collected response from Gemini (length: {len(response_str)}).")
    except Exception as e:
        log.error(f"Error calling Gemini API: {e}\n{traceback.format_exc()}")
        return results


    # --- 6) Parse the JSON response ---
    try:
        # Use regex to find JSON content enclosed by either a ```json block or the first '[' and last ']'
        json_match = re.search(r"```json\s*(\[.*\])\s*```|(\[.*\])", response_str, re.DOTALL | re.MULTILINE)
        if json_match:
            json_content = json_match.group(1) if json_match.group(1) else json_match.group(2)
            log.info("Successfully extracted JSON block from the response.")
        else:
            log.error("Could not find a valid JSON array in the response.")
            return results

        data = json.loads(json_content)
        if not isinstance(data, list):
            log.error("Extracted content is not a JSON array.")
            return results

        # --- 7) Convert to the result dictionary ---
        processed_ids = set()
        for item in data:
            if isinstance(item, dict) and "dimension_id" in item and "status" in item:
                dim_id = item["dimension_id"]
                if dim_id in results:  # Ensure the ID is valid (exists in the input dimensions)
                    results[dim_id] = (item["status"].strip().lower() == "answered")
                    processed_ids.add(dim_id)
                else:
                    log.warning(f"Received unknown dimension_id '{dim_id}' from LLM response.")
            else:
                log.warning(f"Received invalid item format in LLM response array: {item}")

        missing_ids = set(results.keys()) - processed_ids
        if missing_ids:
            log.warning(f"LLM response did not include status for dimensions: {missing_ids}")
    except json.JSONDecodeError:
        log.error(f"Gemini response is not valid JSON. Received: {response_str}")
    except Exception as e:
        log.error(f"Error processing Gemini response: {e}\n{traceback.format_exc()}")

    log.info(f"Final dimension check results: {results}")
    return results

if __name__ == "__main__":
    # Example test data
    test_dimensions = [
        {"id": "dim1", "name": "Market Opportunity", "description": "Details about the market size and growth potential."},
        {"id": "dim2", "name": "Business Model", "description": "Explanation of how the company plans to make money."}
    ]
    test_description = "Our startup targets a market with 1M potential customers. We plan to monetize with a subscription model."

    results = check_pitch_dimensions_with_llm(test_description, test_dimensions)
    print("Dimension Check Results:")
    print(json.dumps(results, indent=2))
