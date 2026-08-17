"""
Tools used by the ResearchMind agents: live web search (Tavily) and
page scraping (requests + BeautifulSoup).
"""
import os
import re
import time

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from langchain.tools import tool
from tavily import TavilyClient

load_dotenv()

_tavily_key = os.getenv("TAVILY_API_KEY")
if not _tavily_key:
    raise RuntimeError(
        "TAVILY_API_KEY is missing. Add it to your .env file — see .env.example."
    )

tavily = TavilyClient(api_key=_tavily_key)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


@tool
def web_search(query: str) -> str:
    """Search the web for recent and reliable information on a topic. Returns Title, URL and Snippet for each result."""
    try:
        results = tavily.search(query=query, max_results=6, search_depth="advanced")
    except Exception as e:
        return f"SEARCH_ERROR: Tavily search failed — {e}"

    hits = results.get("results", [])
    if not hits:
        return f"SEARCH_ERROR: No results found for '{query}'."

    out = []
    for r in hits:
        out.append(
            f"Title: {r.get('title', 'Untitled')}\n"
            f"URL: {r.get('url', '')}\n"
            f"Snippet: {r.get('content', '')[:400]}\n"
        )
    return "\n----\n".join(out)


def extract_urls(text: str) -> list[str]:
    """Pull URLs out of a block of text (e.g. web_search output), in order, deduped."""
    urls = re.findall(r"https?://[^\s\)\]\"'>]+", text)
    seen, ordered = set(), []
    for u in urls:
        u = u.rstrip(".,;:")
        if u not in seen:
            seen.add(u)
            ordered.append(u)
    return ordered


def _fetch(url: str, timeout: int = 10) -> str:
    """Fetch a single URL and return cleaned text, or raise on failure."""
    resp = requests.get(url, timeout=timeout, headers=HEADERS, allow_redirects=True)
    resp.raise_for_status()  # <-- was missing: 403/404/paywall pages used to pass through silently

    content_type = resp.headers.get("Content-Type", "")
    if "text/html" not in content_type and "application/xhtml" not in content_type:
        raise ValueError(f"Not an HTML page (Content-Type: {content_type or 'unknown'})")

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "form", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) < 200:
        raise ValueError("Page returned almost no readable text (likely JS-rendered or blocked)")

    return text[:4000]


@tool
def scrape_url(url: str) -> str:
    """Scrape and return clean text content from a given URL for deeper reading."""
    try:
        return _fetch(url)
    except requests.exceptions.HTTPError as e:
        return f"SCRAPE_ERROR: {url} returned HTTP {e.response.status_code}"
    except requests.exceptions.Timeout:
        return f"SCRAPE_ERROR: {url} timed out"
    except Exception as e:
        return f"SCRAPE_ERROR: Could not scrape {url} — {e}"


def scrape_best_of(urls: list[str], max_tries: int = 3) -> tuple[str, str]:
    """
    Try scraping candidate URLs in order until one succeeds.
    Returns (winning_url, text). Raises RuntimeError if all candidates fail.
    This removes the old single-point-of-failure where the LLM had to
    retype one URL correctly with no fallback.
    """
    errors = []
    for url in urls[:max_tries]:
        try:
            return url, _fetch(url)
        except Exception as e:
            errors.append(f"{url} — {e}")
            time.sleep(0.3)
    raise RuntimeError(
        "All candidate sources failed to scrape:\n" + "\n".join(errors)
    )