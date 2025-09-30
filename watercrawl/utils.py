from SimplerLLM.tools.generic_loader import load_content
from goose3 import Goose
from goose3.configuration import Configuration
import re
import logging
import requests
from datetime import datetime
import json
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import random

# List of diverse user agents to rotate through
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/91.0.864.59",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.14; rv:89.0) Gecko/20100101 Firefox/89.0"
]

def get_random_user_agent():
    """Get a random user agent from the list"""
    return random.choice(USER_AGENTS)

logging.getLogger("goose3.crawler").setLevel(logging.CRITICAL)
logging.getLogger("goose3").setLevel(logging.CRITICAL)


config = Configuration()
config.browser_user_agent = get_random_user_agent()
g = Goose(config)




logging.basicConfig(level=logging.INFO)

def extract_json(text):
    try:
        # Find first { and last }
        start = text.find('{')
        end = text.rfind('}')

        if start == -1 or end == -1:
            return None

        # Extract potential JSON string
        json_str = text[start:end + 1]

        # Try to parse it
        return json.loads(json_str)

    except json.JSONDecodeError:
        return None
    except Exception:
        return None


def searxng_fun_demand(demands, max_links=10):
    url = "https://searxng-981965473376.europe-central2.run.app/search"
    filtered_results = []
    articles = []

    params = {
        "q": demands,
        "format": "json"

    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        results = response.json().get("results", [])

        for res in results:
            article_url = res.get("url")
            if not article_url:
                continue
            if "youtube" in article_url:
                continue
            title = res.get("title")

            # Try to extract content, but don't skip the article if extraction fails
            content = extract_content(article_url)

            # If content extraction fails or is too short, use the snippet/body instead
            if not content or len(content.strip()) < 500:
                content = res.get("body", "") or res.get("content", "")
                if not content or len(content.strip()) < 100:
                    print(f"Skipping article '{title}' - insufficient content")
                    continue

            articles.append({
                'date': datetime.now().isoformat(),
                'title': title,
                'body': res.get("body", ""),
                'url': article_url,
                'image': res.get("image", ""),
                'source': res.get("source", ""),
                'content': content,
                'possible_query_used': demands
            })
            if len(articles) == max_links:
                break

        return articles

    except Exception as e:
        print(f"Error with query '{demands}': {e}")
        return []


def extract_content(url):

    # Rewrite Medium URLs
    if url.startswith("https://medium.com"):
        url = f"https://freedium.cfd/{url}"

    # Define extraction functions with better error handling
    extractors = [
        lambda u: g.extract(url=u).cleaned_text,
        lambda u: load_content(u).content
    ]

    content = None

    with ThreadPoolExecutor(max_workers=len(extractors)) as executor:
        futures = {executor.submit(ext, url): ext for ext in extractors}
        for future in as_completed(futures):
            try:
                content = future.result()
                if content and len(content.strip()) > 100:  # Ensure we have substantial content
                    return content
            except Exception as e:
                # Log the error but don't fail completely
                print(f"Extractor failed for {url}: {str(e)}")
                continue

    # If all extractors fail, try a simple requests approach as fallback
    try:
        headers = {
            'User-Agent': get_random_user_agent()
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        # Simple text extraction using BeautifulSoup as last resort
        soup = BeautifulSoup(response.content, 'html.parser')

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        text = soup.get_text()
        # Clean up the text
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)

        if len(text.strip()) > 100:
            return text

    except Exception as e:
        print(f"Fallback extraction failed for {url}: {str(e)}")

    return content

def preprocessing(text):
    text = re.sub(r'[@#]\w+', '', text)

    text = re.sub(r'http\S+|www\S+|https\S+', '', text)

    return text

def fetch_and_process_article(item):
    url = item.get('url')
    article_content = extract_content(url)
    if article_content:
        article_content = preprocessing(article_content)
        item['article_content'] = article_content

    if 'date' not in item or not item['date']:
        item['date'] = datetime.utcnow().strftime('%Y-%m-%d')

    return item
