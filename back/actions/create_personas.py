# create_personas.py

import json
import time

# def load_personas(filename):
#     """
#     Loads persona data from a JSON file.
#     Each persona should have attributes like:
#       'name', 'education', 'abilities_or_passions', 'hobbies',
#       'job', 'why_important', 'needs', 'population_notes',
#       'relationship_channels', 'salary_range', 'demographics',
#       'pain_points', 'jobs_to_be_done', etc.
#     """
#     with open(filename, 'r', encoding='utf-8') as f:
#         data = json.load(f)
#     return data

def create_persona_system_prompt(persona: dict, product_description: str) -> str:
    """
    Given a persona dictionary, this returns a string that can act
    as a 'system' prompt or any structured text describing
    how that persona should respond or what its role is.
    """
    name = persona.get("name", "Unknown Persona")
    job = persona.get("job", "No job specified")
    education = persona.get("education", "No education specified")
    abilities_or_passions = persona.get("abilities_or_passions", "No abilities or passions specified")
    hobbies = persona.get("hobbies", "No hobbies specified")
    why_important = persona.get("why_important", "No info")
    needs = persona.get("needs", "No info")
    relationship_channels = persona.get("relationship_channels", "No info")
    population_notes = persona.get("population_notes", "No info")
    salary_range = persona.get("salary_range", "No info")
    demographics = persona.get("demographics", "No info")
    pain_points = persona.get("pain_points", "No info")
    jobs_to_be_done = persona.get("jobs_to_be_done", "No info")

    system_prompt = f"""
You are {name}, a virtual persona.

## Background

- **Education**: {education}
- **Abilities or Passions**: {abilities_or_passions}
- **Hobbies**: {hobbies}
- **Job**: {job}
- **Why You're Important**: {why_important}
- **Needs**: {needs}
- **Population Notes**: {population_notes}
- **Relationship Channels**: {relationship_channels}
- **Salary Range**: {salary_range}
- **Demographics**: {demographics}
- **Pain Points**: {pain_points}
- **Jobs To Be Done**: {jobs_to_be_done}

## Purpose

You will receive a product description from the user (shown below). Your task is to:
1. React and respond **as {name}** would, leveraging your unique background, motivations, and context.
2. Evaluate and discuss the product’s potential, limitations, and value **through the lens of your persona**.
3. Provide honest insights, suggestions, or critiques relevant to your role, pain points, and goals but keep the answers concise, it should feel like a normal conversation.

## Product Description

{product_description}

## Guidelines

1. **Stay in-character** as {name}. Your responses should reflect your needs, pain points, and personal interests.
2. **Ask clarifying questions** about the product if needed, focusing on how it aligns with your persona’s needs and challenges (e.g., cost, usability, authenticity, cultural sensitivity).
3. **Offer constructive feedback** that someone with your background might give. For example, if you are an influencer, you might express concerns about brand consistency or audience trust; if you are a developer, you’d focus on technical feasibility, etc.
4. **Maintain empathy and authenticity** in your responses. If user trust is important to you, mention why and how certain product features or capabilities might help or hinder that trust.
5. **Use your “Jobs to Be Done”** to frame your feedback. If a key job is to grow your audience globally, you might emphasize how well the product addresses language or cultural barriers.
6. **Always keep in mind** the ultimate value you seek from this product, whether it’s saving time and money, expanding reach, preserving authenticity, etc.

When you’re ready, produce a final answer or response as {name}, integrating all relevant aspects of your persona.
"""
    return system_prompt.strip()

def generate_persona_prompts_and_details(
    persona_data_list: list[dict],
    product_description: str
) -> list[dict]:
    """
    Generates system prompts and extracts card details for each persona.

    Args:
        persona_data_list: The list of persona dictionaries generated previously.
        product_description: The product description to include in prompts.

    Returns:
        A list of dictionaries, each containing 'name', 'prompt', 'card_details', and 'original_data'.
    """
    all_persona_info = []

    if not persona_data_list:
         print("Warning: Received empty persona data list in generate_persona_prompts_and_details.")
         return []

    for persona in persona_data_list:
        if not isinstance(persona, dict):
             print(f"Warning: Skipping invalid item in persona data list: {persona}")
             continue

        persona_prompt = create_persona_system_prompt(persona, product_description)
        persona_name = persona.get("name", "Unknown Persona")

        # Extract specific details needed for the card display
        card_details = {
            "name": persona_name,
            "education": persona.get("education", "N/A"),
            "hobbies": persona.get("hobbies", "N/A"),
            "job": persona.get("job", "N/A"),
            "salary_range": persona.get("salary_range", "N/A"),
            "why_important": persona.get("why_important", "N/A"),
            "needs": persona.get("needs", "N/A"),
            "relationship_channels": persona.get("relationship_channels", "N/A"),
            "company": "Not specified",  # Add this if needed
        }

        all_persona_info.append({
            "name": persona_name,
            "prompt": persona_prompt,
            "card_details": card_details,
            "original_data": persona  # ✅ Preserve original persona data
        })

    return all_persona_info
