# back/actions/generate_analysis.py

from actions.gemini_api import generate
import json
import os

def send_report_and_filtered_posts_with_gemini(
    report_content,
    filtered_posts_data,
    user_prompt="Give me an analysis of these findings.",
):
    """
    Reads a markdown report and a list of filtered Reddit posts, then
    sends them (plus a user prompt) to the LLM for analysis.
    """

    # Build a single prompt
    prompt = f"""You are given:
    1. A markdown report.
    2. A list of filtered Reddit posts.
    3. A user prompt requesting additional analysis.
    \n\n--- START OF MARKDOWN REPORT ---\n
    {report_content}\n
    --- END OF MARKDOWN REPORT ---\n
    \n\n--- START OF FILTERED POSTS ---\n
    {json.dumps(filtered_posts_data, indent=2)}\n
    --- END OF FILTERED POSTS ---\n
    \n\nUSER PROMPT:\n{user_prompt}\n\n
    Please provide a detailed analysis based on all the provided information."""

    # Generate the analysis
    final_analysis = generate(prompt)

    return final_analysis
