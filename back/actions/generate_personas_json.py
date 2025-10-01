import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from the .env file in the project root
# Get the project root directory (3 levels up from this file)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)

def generate_personas(product_description: str, final_analysis: str, number: int= 4, output_file: str = "personas_output.json"): # Here, instead of saving to a JSON maybe we can save it in a variable.
    # Load analysis_final.md from the local directory
    # with open("analysis_final.md", "r", encoding="utf-8") as file:
    #     analysis_text = file.read()

    # Format the prompt
    prompt = f"""
You are an AI trained to generate highly detailed, realistic consumer personas based on user-provided product descriptions and domain-specific market insights.

Product Description:
{product_description}

Domain Insights (from netnographic research):
{final_analysis}

Your task is to generate {number} distinct personas representing potential target customers. Each persona must be derived from the product context and reflect actual market needs, frustrations, desires, and patterns observed in relevant online communities (e.g., Reddit, YouTube, HackerNews). The goal is to help an entrepreneur understand who their end-users could be, what they need, and how best to reach them.

Output format: JSON array of {number} objects.
Each object represents one persona and should include the following fields:

{{
  "name": "Persona Name",
  "education": "e.g., Recent college graduate in communications",
  "abilities_or_passions": "e.g., Sees beauty in storytelling, quick to adopt AI tools",
  "hobbies": "e.g., Editing YouTube videos, browsing AI forums, watching Netflix in multiple languages",
  "job": "e.g., Freelance voice actor, YouTuber, Localization Project Manager",
  "why_important": "Explain why this persona is valuable to target, referencing trends like global content consumption, growing creator economy, etc.",
  "needs": "Describe what this persona wants to achieve—functionally, emotionally, socially. Include references to goals like expanding global reach or improving workflow efficiency.",
  "population_notes": "Estimate size, segment scope, or mention unknowns. Include relevance across markets or geographies, if known.",
  "relationship_channels": "Where to find them or build trust (e.g., r/VoiceActing, YouTube creator Discords, localization Slack groups)",
  "salary_range": "e.g., $35,000–$75,000 annually",
  "demographics": "e.g., Age range 25–40, tech-savvy, mostly US/Europe-based",
  "pain_points": "Top 2–3 frustrations (e.g., robotic AI output, loss of authenticity, workflow inefficiency)",
  "jobs_to_be_done": "Summarize their primary 'Jobs to Be Done' (e.g., achieve high-quality multilingual content with minimal technical overhead)"
}}

Additional context:
- Use social listening data to ensure authenticity.
- Personas should reflect diversity in profession and user intent (e.g., influencer, voice actor, marketer, content creator).
- Balance emotional, social, and functional motivations.
- Connect their pain points and needs to trends from the domain (e.g., authenticity, ethical AI use, efficiency).
"""

    # Configure Gemini client
    api_key = os.environ.get("NEXT_PUBLIC_GEMINI_API_KEY")
    if not api_key:
        print("Error: API key not found")
        return []

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')

    generation_config = {
        "temperature": 0,
        "response_mime_type": "application/json",
    }

    # Generate content
    response = model.generate_content(
        prompt,
        generation_config=generation_config
    )
    json_output_string = response.text

    # Attempt to parse JSON (Gemini might return array or object depending on response style)
    try:
        # Clean the output in case the LLM added markdown fences
        if json_output_string.strip().startswith("```json"):
            json_output_string = json_output_string.strip()[7:]
            if json_output_string.endswith("```"):
                json_output_string = json_output_string[:-3]
        elif json_output_string.strip().startswith("```"):
             json_output_string = json_output_string.strip()[3:]
             if json_output_string.endswith("```"):
                 json_output_string = json_output_string[:-3]


        persona_data_list = json.loads(json_output_string.strip())
        if not isinstance(persona_data_list, list):
            print("ERROR: Generated persona data is not a JSON list.")
            return []

        print(f"Successfully generated and parsed {len(persona_data_list)} personas in memory.")
        return persona_data_list

    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse generated persona JSON: {e}")
        print(f"LLM Output causing error:\n---\n{json_output_string}\n---")
        return [] # Return empty list on failure
    except Exception as e:
        print(f"ERROR: An unexpected error occurred during persona generation: {e}")
        return []
