import time
from urllib.parse import urlparse

from agents import build_search_agent, critic_chain, reader_chain, writer_chain
from tools import extract_urls, scrape_best_of

STEP_LABELS = {
    "search": "Search Agent",
    "reader": "Reader Agent",
    "writer": "Writer Chain",
    "critic": "Critic Chain",
}


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return url


def _friendly_error(e: Exception, step: str) -> str:
    """
    Turn raw OpenAI/LangChain exceptions into a message a user can actually
    act on, instead of a stack trace. This is the #1 cause of "the backend
    just doesn't work" reports — an expired/invalid/missing key throws deep
    inside the SDK and the raw message never says that plainly.
    """
    msg = str(e)
    low = msg.lower()

    if "401" in msg or "invalid_api_key" in low or "incorrect api key" in low or "authentication" in low:
        return (
            f"[{step}] Your Groq API key was rejected (401 Unauthorized).\n"
            "• Double-check GROQ_API_KEY in your .env — it should start with 'gsk_'\n"
            "• Make sure the key hasn't been revoked/rotated in console.groq.com\n"
            "• Make sure there's no extra space or quote marks around it in .env"
        )
    if "429" in msg or "rate limit" in low or "rate_limit" in low:
        return (
            f"[{step}] Groq's free-tier rate limit was hit (429).\n"
            "• Groq's free tier allows ~30 requests/minute — wait a few seconds and try again\n"
            "• If this keeps happening, you may be hitting the daily request cap — try again later"
        )
    if "tavily" in low and ("401" in msg or "unauthorized" in low or "invalid" in low):
        return (
            f"[{step}] Your Tavily API key was rejected.\n"
            "• Double-check TAVILY_API_KEY in your .env — it should start with 'tvly-'\n"
            "• Free Tavily keys have a monthly search cap — check you haven't hit it"
        )
    if "timeout" in low or "timed out" in low:
        return f"[{step}] The request timed out. Check your internet connection and try again."

    return f"[{step}] {msg}"


def run_research_pipeline_stream(topic: str):
    """
    Runs the 4-step research pipeline and yields (step_name, output, meta)
    after each step completes. `meta` is a dict with at least `elapsed`
    (seconds, float) and `detail` (a short human-readable status line used
    by the UI). Single source of truth for the pipeline logic.
    """
    state = {}

    # ── Step 1 — Search ────────────────────────────────────────────────
    t0 = time.time()
    try:
        search_agent = build_search_agent()
        search_result = search_agent.invoke({
            "messages": [("user", f"Find recent, reliable and detailed information about: {topic}")]
        })
        state["search"] = search_result["messages"][-1].content
    except Exception as e:
        raise RuntimeError(_friendly_error(e, "Search Agent")) from e

    if not state["search"] or "SEARCH_ERROR" in state["search"]:
        raise RuntimeError(
            f"Search step failed to return usable results.\n\n{state['search']}"
        )

    urls = extract_urls(state["search"])
    if not urls:
        raise RuntimeError(
            "Search step completed, but no source URLs could be found in the results. "
            "Try a more specific topic."
        )

    yield "search", state["search"], {
        "elapsed": time.time() - t0,
        "detail": f"Found {len(urls)} candidate source{'s' if len(urls) != 1 else ''}",
    }

    # ── Step 2 — Reader (deterministic scrape + LLM summarize) ─────────
    t0 = time.time()
    try:
        winning_url, raw_content = scrape_best_of(urls, max_tries=4)
    except RuntimeError as e:
        raise RuntimeError(f"Reader step failed — every candidate source was unreachable.\n\n{e}")

    try:
        state["reader"] = reader_chain.invoke({
            "source_url": winning_url,
            "raw_content": raw_content,
            "topic": topic,
        })
    except Exception as e:
        raise RuntimeError(_friendly_error(e, "Reader Agent")) from e
    state["reader_source"] = winning_url

    yield "reader", state["reader"], {
        "elapsed": time.time() - t0,
        "detail": f"Read {_domain(winning_url)}",
    }

    # ── Step 3 — Writer ──────────────────────────────────────────────
    t0 = time.time()
    research_combined = (
        f"SEARCH RESULTS:\n{state['search']}\n\n"
        f"DETAILED CONTENT FROM {winning_url}:\n{state['reader']}"
    )
    try:
        state["writer"] = writer_chain.invoke({"topic": topic, "research": research_combined})
    except Exception as e:
        raise RuntimeError(_friendly_error(e, "Writer Chain")) from e

    yield "writer", state["writer"], {
        "elapsed": time.time() - t0,
        "detail": f"{len(state['writer'].split())} words drafted",
    }

    # ── Step 4 — Critic ──────────────────────────────────────────────
    t0 = time.time()
    try:
        state["critic"] = critic_chain.invoke({"report": state["writer"]})
    except Exception as e:
        raise RuntimeError(_friendly_error(e, "Critic Chain")) from e

    yield "critic", state["critic"], {
        "elapsed": time.time() - t0,
        "detail": "Review complete",
    }


def run_research_pipeline(topic: str) -> dict:
    """Non-streaming convenience wrapper — collects all steps into one dict."""
    state = {}
    for step_name, output, meta in run_research_pipeline_stream(topic):
        state[step_name] = output
    return state


if __name__ == "__main__":
    topic = input("\nEnter a research topic: ")
    for step_name, output, meta in run_research_pipeline_stream(topic):
        print(f"\n{'=' * 50}\n{STEP_LABELS[step_name]} complete ({meta['elapsed']:.1f}s) — {meta['detail']}\n{'=' * 50}")
        print(output)