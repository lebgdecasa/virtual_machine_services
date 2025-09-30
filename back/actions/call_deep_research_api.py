import requests

def run_research_api(query: str, breadth: int = 3, depth: int = 3):
    """
    Call the Deep Research API with the given query, breadth, and depth.

    :param query: The research question to ask.
    :param breadth: How wide the search should go (default: 3).
    :param depth: How deep the search should go (default: 3).
    :return: Dictionary with answer, learnings, and visited URLs.
    """
    url = "https://deep-research-api-981965473376.us-central1.run.app/api/research"
    payload = {
        "query": query,
        "breadth": breadth,
        "depth": depth
    }

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["answer"]

    except requests.RequestException as e:
        print(f"API call failed: {e}")
        return None
