import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from tools import web_search

load_dotenv()

if not os.getenv("GROQ_API_KEY"):
    raise RuntimeError(
        "GROQ_API_KEY is missing. Add it to your .env file — get a free key at console.groq.com."
    )

# ── Model ─────────────────────────────────────────────────────────────────
llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0)


# ── Agent 1: Search ──────────────────────────────────────────────────────
def build_search_agent():
    return create_agent(
        model=llm,
        tools=[web_search],
        system_prompt=(
            "You are a research search specialist. Call web_search exactly once with "
            "a well-formed query for the user's topic, then summarize what you found "
            "in a few sentences, keeping every URL you were given intact and unchanged."
        ),
    )


# ── Agent 2: Reader (summarizes deterministically-scraped content) ──────
# NOTE: URL selection + scraping now happens in pipeline.py via
# tools.extract_urls / tools.scrape_best_of — deterministic Python, not the
# LLM retyping a URL from memory (that was the main source of silent
# scrape failures). This chain only summarizes the text that was already
# successfully fetched.
reader_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a careful research reader. Extract and organize the most useful facts from raw page text."),
    ("human", """The text below was scraped from: {source_url}

Raw page content:
{raw_content}

Summarize the most relevant facts, figures, and claims from this page related to the topic "{topic}". Write 5-8 concise bullet points. Do not invent information that isn't in the text."""),
])
reader_chain = reader_prompt | llm | StrOutputParser()


def build_reader_agent():
    """Kept for backwards compatibility / CLI use; pipeline.py uses reader_chain directly."""
    return reader_chain


# ── Writer chain ──────────────────────────────────────────────────────────
writer_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert research writer. Write clear, structured and insightful reports."),
    ("human", """Write a detailed research report on the topic below.

Topic: {topic}

Research Gathered:
{research}

Structure the report as:
- Introduction
- Key Findings (minimum 3 well-explained points)
- Conclusion
- Sources (list all URLs found in the research)

Be detailed, factual and professional."""),
])
writer_chain = writer_prompt | llm | StrOutputParser()


# ── Critic chain ────────────────────────────────────────────────────────
critic_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a sharp and constructive research critic. Be honest and specific."),
    ("human", """Review the research report below and evaluate it strictly.

Report:
{report}

Respond in this exact format:

Score: X/10

Strengths:
- ...
- ...

Areas to Improve:
- ...
- ...

One line verdict:
..."""),
])
critic_chain = critic_prompt | llm | StrOutputParser()