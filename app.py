import re
import time
from datetime import datetime

import streamlit as st

from pipeline import run_research_pipeline_stream

import base64
from pathlib import Path

ASSETS_DIR = Path(__file__).parent / "assets"

def load_mascot(name: str) -> str:
    svg_bytes = (ASSETS_DIR / f"robot_{name}.svg").read_bytes()
    b64 = base64.b64encode(svg_bytes).decode()
    return f'<img src="data:image/svg+xml;base64,{b64}" style="width:100%;height:100%;object-fit:contain;" />'

MASCOTS = {key: load_mascot(key) for key in ["search", "reader", "writer", "critic"]}

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ResearchMind · AI Research Desk",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Each agent gets its own color identity + emoji avatar — used everywhere
# (pipeline cards, squad grid, tabs) so the whole app reads as one system.
STEPS = [
    ("01", "search", "Search Agent", "Queries the live web via Tavily to surface recent, reliable sources.",
     "🔎", "#38bdf8", "#0ea5e9", "rgba(56,189,248,0.14)"),
    ("02", "reader", "Reader Agent", "Fetches the strongest source and extracts the substance of the page.",
     "📖", "#34d399", "#10b981", "rgba(52,211,153,0.14)"),
    ("03", "writer", "Writer Chain", "Synthesizes everything gathered into a structured, cited report.",
     "🖋️", "#fbbf24", "#f59e0b", "rgba(251,191,36,0.14)"),
    ("04", "critic", "Critic Chain", "Independently scores the report and flags strengths and gaps.",
     "🧭", "#f472b6", "#ec4899", "rgba(244,114,182,0.14)"),
]
TIPS = [
    "Specific topics beat broad ones — \"EU AI Act enforcement 2026\" beats \"AI regulation\".",
    "The Critic Chain scores the report independently — a low score doesn't mean the run failed.",
    "Reader Agent always reads real, successfully-fetched page text — never a guessed URL.",
    "You can re-run the same topic — Search Agent often surfaces a different top source each time.",
    "Every report ships with a Sources tab so you can verify claims yourself.",
]

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700;9..144,900&family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

:root {
    --bg: #0a0716;
    --surface: #150f2b;
    --surface-2: #1c1438;
    --border: rgba(255,255,255,0.09);
    --border-strong: rgba(255,255,255,0.18);
    --text-1: #f6f3ff;
    --text-2: #b7aed6;
    --text-3: #7d72a0;
    --accent: #a855f7;
    --accent-2: #ec4899;
    --accent-soft: rgba(168,85,247,0.16);
    --good: #34d399;
    --good-soft: rgba(52,211,153,0.14);
    --error: #fb7185;
    --error-soft: rgba(251,113,133,0.14);
}

* { box-sizing: border-box; }
html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: var(--text-1); }

.stApp {
    background: var(--bg);
    background-image:
        radial-gradient(ellipse 55% 40% at 6% -8%, rgba(168,85,247,0.22) 0%, transparent 60%),
        radial-gradient(ellipse 50% 38% at 98% 6%, rgba(56,189,248,0.16) 0%, transparent 55%),
        radial-gradient(ellipse 45% 35% at 50% 105%, rgba(236,72,153,0.14) 0%, transparent 55%);
}
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 0 3rem 5rem; max-width: 1220px; }

/* ── Top bar ── */
.topbar { display: flex; align-items: center; justify-content: space-between; padding: 1.5rem 0; border-bottom: 1px solid var(--border); margin-bottom: 2.6rem; }
.topbar-brand { display: flex; align-items: center; gap: 0.75rem; }
.topbar-logo { width: 36px; height: 36px; border-radius: 10px; flex-shrink: 0; background: linear-gradient(135deg, var(--accent), var(--accent-2)); display: flex; align-items: center; justify-content: center; font-size: 1.15rem; box-shadow: 0 0 22px rgba(168,85,247,0.45); }
.topbar-name { font-family: 'Fraunces', serif; font-weight: 700; font-size: 1.2rem; letter-spacing: -0.01em; background: linear-gradient(90deg, #f6f3ff, #c9b8f5); -webkit-background-clip: text; background-clip: text; color: transparent; }
.topbar-status { display: flex; align-items: center; gap: 0.5rem; font-family: 'JetBrains Mono', monospace; font-size: 0.68rem; letter-spacing: 0.08em; color: var(--text-3); text-transform: uppercase; }
.status-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--good); box-shadow: 0 0 9px var(--good); animation: blink 2s infinite; }
@keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0.45; } }

/* ── Hero ── */
.hero { padding: 0 0 2.6rem; }
.hero-eyebrow { display: inline-block; font-family: 'JetBrains Mono', monospace; font-size: 0.68rem; font-weight: 600; letter-spacing: 0.18em; text-transform: uppercase; color: var(--accent-2); padding: 0.32rem 0.8rem; border: 1px solid var(--border-strong); border-radius: 99px; margin-bottom: 1.4rem; background: var(--surface); }
.hero h1 { font-family: 'Fraunces', serif; font-size: clamp(2.4rem, 4.6vw, 3.7rem); font-weight: 700; line-height: 1.08; letter-spacing: -0.02em; color: var(--text-1); margin: 0 0 1.1rem; max-width: 800px; }
.hero h1 em { font-style: normal; background: linear-gradient(90deg, #38bdf8, #a855f7 45%, #ec4899); -webkit-background-clip: text; background-clip: text; color: transparent; }
.hero-sub { font-size: 1.05rem; color: var(--text-2); max-width: 560px; margin: 0 0 2.2rem; line-height: 1.65; }

/* ── Stat strip ── */
.stat-strip { display: flex; gap: 0; border: 1px solid var(--border); border-radius: 10px; overflow: hidden; width: fit-content; background: var(--surface); }
.stat-item { padding: 0.9rem 1.7rem; border-right: 1px solid var(--border); }
.stat-item:last-child { border-right: none; }
.stat-num { font-family: 'Fraunces', serif; font-weight: 700; font-size: 1.35rem; color: var(--text-1); }
.stat-label { font-family: 'JetBrains Mono', monospace; font-size: 0.62rem; letter-spacing: 0.09em; text-transform: uppercase; color: var(--text-3); margin-top: 0.15rem; }

.divider { height: 1px; background: linear-gradient(90deg, transparent, var(--border-strong) 20%, var(--border-strong) 80%, transparent); margin: 3rem 0; }

/* ── Section labels ── */
.section-eyebrow { font-family: 'JetBrains Mono', monospace; font-size: 0.68rem; font-weight: 600; letter-spacing: 0.16em; text-transform: uppercase; color: var(--accent-2); margin-bottom: 0.4rem; }
.section-heading { font-family: 'Fraunces', serif; font-size: 1.55rem; font-weight: 700; color: var(--text-1); margin: 0 0 1.5rem; letter-spacing: -0.01em; }

/* ── Input card ── */
div[data-testid="stVerticalBlockBorderWrapper"]:has(.st-key-input_card) > div { background: linear-gradient(160deg, var(--surface), var(--surface-2)); border: 1px solid var(--border-strong); border-radius: 14px; padding: 1.9rem 2.1rem; box-shadow: 0 12px 40px rgba(0,0,0,0.35); }
.stTextInput > div > div > input { background: var(--surface-2) !important; border: 1px solid var(--border) !important; border-radius: 8px !important; color: var(--text-1) !important; font-family: 'Inter', sans-serif !important; font-size: 0.97rem !important; padding: 0.8rem 1rem !important; transition: border-color 0.2s, box-shadow 0.2s !important; }
.stTextInput > div > div > input:focus { border-color: var(--accent) !important; box-shadow: 0 0 0 3px var(--accent-soft) !important; }
.stTextInput > label { font-family: 'JetBrains Mono', monospace !important; font-size: 0.68rem !important; letter-spacing: 0.13em !important; text-transform: uppercase !important; color: var(--text-2) !important; font-weight: 600 !important; margin-bottom: 0.45rem !important; }
div[data-testid="stVerticalBlockBorderWrapper"]:has(.st-key-input_card) .stButton > button { background: linear-gradient(90deg, var(--accent), var(--accent-2)) !important; color: #0a0716 !important; font-family: 'Fraunces', serif !important; font-weight: 700 !important; font-size: 0.98rem !important; border: none !important; border-radius: 8px !important; padding: 0.8rem 2rem !important; transition: opacity 0.15s, transform 0.15s, box-shadow 0.15s !important; width: 100%; margin-top: 0.6rem; box-shadow: 0 8px 24px rgba(168,85,247,0.35) !important; }
div[data-testid="stVerticalBlockBorderWrapper"]:has(.st-key-input_card) .stButton > button:hover { opacity: 0.92 !important; transform: translateY(-2px) !important; box-shadow: 0 12px 30px rgba(168,85,247,0.5) !important; }
.try-label { font-family: 'JetBrains Mono', monospace; font-size: 0.66rem; letter-spacing: 0.13em; text-transform: uppercase; color: var(--text-3); margin: 1.5rem 0 0.7rem; }
div[data-testid="stVerticalBlockBorderWrapper"]:has(.st-key-example_chips) .stButton > button { background: var(--surface) !important; border: 1px solid var(--border) !important; border-radius: 99px !important; color: var(--text-2) !important; font-family: 'Inter', sans-serif !important; font-size: 0.81rem !important; font-weight: 500 !important; padding: 0.5rem 0.7rem !important; }
div[data-testid="stVerticalBlockBorderWrapper"]:has(.st-key-example_chips) .stButton > button:hover { border-color: var(--accent-2) !important; color: var(--accent-2) !important; }

/* ── Overall progress bar ── */
.progress-shell { height: 8px; border-radius: 99px; background: var(--surface-2); overflow: hidden; margin-bottom: 1.4rem; border: 1px solid var(--border); }
.progress-fill { height: 100%; border-radius: 99px; background: linear-gradient(90deg, #38bdf8, #a855f7, #ec4899); transition: width 0.5s ease; }

/* ── Pipeline cards ── */
.pipe-thread { position: relative; }
.pipe-card { position: relative; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 1.15rem 1.4rem; margin-bottom: 0.85rem; display: flex; gap: 1rem; align-items: flex-start; transition: border-color 0.3s, background 0.3s, box-shadow 0.3s; }
.pipe-card:last-child { margin-bottom: 0; }
.pipe-card.done { border-color: var(--agent-color); background: linear-gradient(180deg, var(--agent-soft), var(--surface) 65%); }
.pipe-card.active { border-color: var(--agent-color); background: linear-gradient(180deg, var(--agent-soft), var(--surface) 65%); box-shadow: 0 0 0 1px var(--agent-color), 0 10px 28px -8px var(--agent-color); }
.pipe-card.tl-error { border-color: var(--error); background: linear-gradient(180deg, var(--error-soft), var(--surface) 65%); }

.pipe-icon { width: 42px; padding: 4px; height: 42px; border-radius: 11px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; font-size: 1.2rem; background: var(--surface-2); border: 1px solid var(--border); }
.pipe-card.done .pipe-icon, .pipe-card.active .pipe-icon { background: linear-gradient(135deg, var(--agent-color), var(--agent-color-2)); border-color: transparent; }
.pipe-card.active .pipe-icon { animation: pulse 1.3s infinite; }
@keyframes pulse { 0% { box-shadow: 0 0 0 0 var(--agent-soft); } 70% { box-shadow: 0 0 0 10px transparent; } 100% { box-shadow: 0 0 0 0 transparent; } }
.pipe-body { flex: 1; min-width: 0; }
.pipe-top { display: flex; align-items: center; justify-content: space-between; gap: 0.6rem; margin-bottom: 0.25rem; }
.pipe-title-row { display: flex; align-items: center; gap: 0.5rem; }
.pipe-num { font-family: 'JetBrains Mono', monospace; font-size: 0.63rem; color: var(--text-3); }
.pipe-title { font-family: 'Fraunces', serif; font-weight: 700; font-size: 1rem; color: var(--text-1); }
.pipe-status { font-family: 'JetBrains Mono', monospace; font-size: 0.6rem; letter-spacing: 0.09em; padding: 0.2rem 0.55rem; border-radius: 99px; white-space: nowrap; font-weight: 600; }
.pipe-status.waiting { color: var(--text-3); background: var(--surface-2); }
.pipe-status.active { color: var(--bg); background: var(--agent-color); }
.pipe-status.done { color: var(--bg); background: var(--agent-color); }
.pipe-status.error { color: var(--error); background: var(--error-soft); }
.pipe-desc { font-size: 0.82rem; color: var(--text-2); line-height: 1.5; }
.pipe-detail { font-family: 'JetBrains Mono', monospace; font-size: 0.68rem; color: var(--agent-color-2); margin-top: 0.4rem; }

/* ── Mission control (fills the space below the input card) ── */
.mission-panel { margin-top: 1.4rem; background: linear-gradient(160deg, var(--surface), var(--surface-2)); border: 1px solid var(--border-strong); border-radius: 14px; padding: 1.4rem 1.5rem; }
.mission-title { font-family: 'JetBrains Mono', monospace; font-size: 0.65rem; letter-spacing: 0.14em; text-transform: uppercase; color: var(--accent-2); margin-bottom: 1rem; font-weight: 600; }
.mission-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0.9rem; margin-bottom: 1.1rem; }
.mission-stat { text-align: center; padding: 0.8rem 0.4rem; background: var(--surface-2); border-radius: 10px; border: 1px solid var(--border); }
.mission-num { font-family: 'Fraunces', serif; font-weight: 700; font-size: 1.25rem; background: linear-gradient(90deg, #38bdf8, #ec4899); -webkit-background-clip: text; background-clip: text; color: transparent; }
.mission-label { font-family: 'JetBrains Mono', monospace; font-size: 0.58rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-3); margin-top: 0.2rem; }
.mission-tip { font-size: 0.82rem; color: var(--text-2); line-height: 1.55; border-top: 1px solid var(--border); padding-top: 0.9rem; }
.mission-tip b { color: var(--accent-2); font-family: 'JetBrains Mono', monospace; font-size: 0.68rem; letter-spacing: 0.08em; text-transform: uppercase; display: block; margin-bottom: 0.35rem; }

/* ── Agent squad grid (shown before a run, replaces the plain empty state) ── */
.squad-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.9rem; }
.squad-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 1.1rem 1.1rem; transition: transform 0.2s, border-color 0.2s; }
.squad-card:hover { transform: translateY(-3px); border-color: var(--sc-color); }
.squad-avatar { width: 40px;  padding: 6px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1.15rem; margin-bottom: 0.7rem; background: linear-gradient(135deg, var(--sc-color), var(--sc-color-2)); }
.squad-name { font-family: 'Fraunces', serif; font-weight: 700; font-size: 0.92rem; color: var(--text-1); margin-bottom: 0.3rem; }
.squad-desc { font-size: 0.76rem; color: var(--text-3); line-height: 1.5; }

/* ── Score gauge ── */
.score-wrap { display: flex; align-items: center; gap: 2rem; margin-bottom: 1.5rem; padding: 0.5rem 0 1.5rem; border-bottom: 1px solid var(--border); }
.score-ring { width: 112px; height: 112px; border-radius: 50%; flex-shrink: 0; background: conic-gradient(from -90deg, #38bdf8, #a855f7, #ec4899 var(--pct), var(--surface-2) 0); display: flex; align-items: center; justify-content: center; }
.score-ring-inner { width: 88px; height: 88px; border-radius: 50%; background: var(--bg); display: flex; flex-direction: column; align-items: center; justify-content: center; }
.score-value { font-family: 'Fraunces', serif; font-size: 1.7rem; font-weight: 700; color: var(--text-1); line-height: 1; }
.score-max { font-family: 'JetBrains Mono', monospace; font-size: 0.62rem; color: var(--text-3); margin-top: 2px; }
.score-verdict { font-size: 0.98rem; color: var(--text-1); line-height: 1.6; font-family: 'Fraunces', serif; font-style: italic; }
.score-verdict-label { font-family: 'JetBrains Mono', monospace; font-size: 0.62rem; letter-spacing: 0.13em; text-transform: uppercase; color: var(--accent-2); margin-bottom: 0.5rem; font-weight: 600; }

/* ── Result panels ── */
.result-panel { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 1.6rem 1.9rem; }
.result-content { font-size: 0.88rem; line-height: 1.8; color: var(--text-2); white-space: pre-wrap; }

.stTabs [data-baseweb="tab-list"] { gap: 0.4rem; border-bottom: 1px solid var(--border); margin-bottom: 1.5rem; }
.stTabs [data-baseweb="tab"] { font-family: 'JetBrains Mono', monospace !important; font-size: 0.75rem !important; letter-spacing: 0.06em; color: var(--text-3) !important; text-transform: uppercase; padding: 0.65rem 0.2rem !important; }
.stTabs [aria-selected="true"] { color: var(--accent-2) !important; }

.error-panel { background: var(--error-soft); border: 1px solid var(--error); border-radius: 12px; padding: 1.5rem 1.8rem; color: #ffd7de; font-size: 0.88rem; line-height: 1.7; white-space: pre-wrap; }

/* ── Source cards ── */
.source-card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 1rem 1.2rem; margin-bottom: 0.7rem; transition: border-color 0.2s; }
.source-card:hover { border-color: var(--accent-2); }
.source-title { font-family: 'Fraunces', serif; font-weight: 700; font-size: 0.92rem; color: var(--text-1); margin-bottom: 0.25rem; }
.source-url { font-family: 'JetBrains Mono', monospace; font-size: 0.68rem; color: #38bdf8; margin-bottom: 0.4rem; display: block; text-decoration: none; }
.source-snippet { font-size: 0.82rem; color: var(--text-2); line-height: 1.55; }

/* ── History ── */
.history-row { display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 0; border-bottom: 1px solid var(--border); font-size: 0.85rem; }
.history-row:last-child { border-bottom: none; }
.history-topic { color: var(--text-1); font-family: 'Fraunces', serif; font-weight: 600; }
.history-meta { font-family: 'JetBrains Mono', monospace; font-size: 0.68rem; color: var(--text-3); }

/* ── Footer ── */
.footer { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem; padding-top: 2rem; margin-top: 3.5rem; border-top: 1px solid var(--border); }
.footer-brand { font-family: 'Fraunces', serif; font-weight: 700; font-size: 0.88rem; color: var(--text-2); }
.footer-meta { font-family: 'JetBrains Mono', monospace; font-size: 0.68rem; color: var(--text-3); letter-spacing: 0.04em; text-align: right; }
</style>
""", unsafe_allow_html=True)


# ── Session state ────────────────────────────────────────────────────────────
for key, default in [
    ("results", {}), ("meta", {}), ("running_step", None), ("error", None),
    ("topic_input", ""), ("history", []), ("current_topic", ""),
]:
    if key not in st.session_state:
        st.session_state[key] = default


def render_pipeline(slot):
    """
    Builds every card as ONE combined HTML string and renders it with a
    single st.markdown() call. The previous version called st.markdown()
    once per card inside the loop — with unsafe_allow_html raw HTML,
    Streamlit re-renders each of those as a separate fragment on every
    rerun, and on fast, repeated reruns (this function runs after every
    single pipeline step) the browser can fail to fully replace the old
    fragment before the new one lands, leaving an orphaned closing tag
    from the previous render visible as literal text. Rendering the whole
    thread as one fragment avoids that entirely.
    """
    total = len(STEPS)
    done_count = sum(1 for _, key, *_ in STEPS if key in st.session_state.results)
    pct = int(done_count / total * 100)

    cards = []
    for num, key, title, desc, icon, color, color2, soft in STEPS:
        if st.session_state.error and st.session_state.running_step == key:
            cls, marker, status_cls, status_txt = "tl-error", "!", "error", "FAILED"
        elif key in st.session_state.results:
            cls, marker, status_cls, status_txt = "done", "✓", "done", "DONE"
        elif key == st.session_state.running_step:
            cls, marker, status_cls, status_txt = "active", icon, "active", "RUNNING"
        else:
            cls, marker, status_cls, status_txt = "", icon, "waiting", "WAITING"

        marker_html = MASCOTS[key] if status_cls in ("waiting", "active") else marker
        
        detail_html = ""
        m = st.session_state.meta.get(key)
        if m:
            detail_html = f'<div class="pipe-detail">↳ {m["detail"]} · {m["elapsed"]:.1f}s</div>'

        cards.append(f"""<div class="pipe-card {cls}" style="--agent-color:{color};--agent-color-2:{color2};--agent-soft:{soft};">
<div class="pipe-icon">{marker}</div>
<div class="pipe-body">
<div class="pipe-top">
<div class="pipe-title-row"><span class="pipe-num">{num}</span><span class="pipe-title">{title}</span></div>
<span class="pipe-status {status_cls}">{status_txt}</span>
</div>
<div class="pipe-desc">{desc}</div>
{detail_html}
</div>
</div>""")

    thread_html = (
        f'<div class="progress-shell"><div class="progress-fill" style="width:{pct}%;"></div></div>'
        f'<div class="pipe-thread">' + "".join(cards) + "</div>"
    )

    with slot.container():
        st.markdown(thread_html, unsafe_allow_html=True)


def render_squad_grid():
    """Fills the space before a run starts with a live preview of the
    four agents instead of empty whitespace."""
    cards = []
    for num, key, title, desc, icon, color, color2, soft in STEPS:
        cards.append(f"""<div class="squad-card" style="--sc-color:{color};--sc-color-2:{color2};">
<div class="squad-avatar">{MASCOTS[key]}</div>
<div class="squad-avatar">{icon}</div>
<div class="squad-name">{title}</div>
<div class="squad-desc">{desc}</div>
</div>""")
    st.markdown('<div class="squad-grid">' + "".join(cards) + "</div>", unsafe_allow_html=True)


def render_mission_control(elapsed_total: float, est_tokens: int):
    tip = TIPS[abs(hash(st.session_state.current_topic or "researchmind")) % len(TIPS)]
    est_cost = est_tokens / 1_000_000 * 0.60  # rough blended $/1M-token estimate for gpt-4o-mini
    st.markdown(f"""
    <div class="mission-panel">
        <div class="mission-title">Mission Control</div>
        <div class="mission-grid">
            <div class="mission-stat"><div class="mission-num">{elapsed_total:.1f}s</div><div class="mission-label">Total Time</div></div>
            <div class="mission-stat"><div class="mission-num">~{est_tokens:,}</div><div class="mission-label">Est. Tokens</div></div>
            <div class="mission-stat"><div class="mission-num">${est_cost:.4f}</div><div class="mission-label">Est. Cost</div></div>
        </div>
        <div class="mission-tip"><b>Tip</b>{tip}</div>
    </div>
    """, unsafe_allow_html=True)


def extract_score(critic_text: str):
    m = re.search(r"Score:\s*(\d+(?:\.\d+)?)\s*/\s*10", critic_text)
    score = float(m.group(1)) if m else None
    v = re.search(r"One line verdict:\s*\n?(.+)", critic_text)
    verdict = v.group(1).strip() if v else None
    return score, verdict


def parse_sources(search_text: str):
    """Turn the raw 'Title / URL / Snippet' blocks into structured dicts for source cards."""
    blocks = search_text.split("----")
    sources = []
    for b in blocks:
        t = re.search(r"Title:\s*(.+)", b)
        u = re.search(r"URL:\s*(\S+)", b)
        s = re.search(r"Snippet:\s*(.+)", b)
        if u:
            sources.append({
                "title": t.group(1).strip() if t else u.group(1),
                "url": u.group(1).strip(),
                "snippet": s.group(1).strip() if s else "",
            })
    return sources


# ── Top bar ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="topbar">
    <div class="topbar-brand">
        <div class="topbar-logo">🧠</div>
        <div class="topbar-name">ResearchMind</div>
    </div>
    <div class="topbar-status"><span class="status-dot"></span>Agents Online</div>
</div>
""", unsafe_allow_html=True)

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <span class="hero-eyebrow">Multi-Agent Research Desk</span>
    <h1>Four agents, one <em>case file</em>,<br>a finished report in minutes.</h1>
    <p class="hero-sub">
        Search, Reader, Writer, and Critic work in sequence — each one handing its
        findings to the next — to turn a single topic into a cited, self-reviewed report.
    </p>
    <div class="stat-strip">
        <div class="stat-item"><div class="stat-num">4</div><div class="stat-label">Agents</div></div>
        <div class="stat-item"><div class="stat-num">&lt;2min</div><div class="stat-label">Avg. Runtime</div></div>
        <div class="stat-item"><div class="stat-num">GPT-4o mini</div><div class="stat-label">+ Tavily</div></div>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)


# ── Layout ────────────────────────────────────────────────────────────────────
col_input, col_spacer, col_pipeline = st.columns([5, 0.6, 4])

with col_input:
    st.markdown('<div class="section-eyebrow">Open a Case</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-heading">Run a research pipeline</div>', unsafe_allow_html=True)

    with st.container(key="input_card"):
        topic = st.text_input(
            "Research Topic",
            placeholder="e.g. Quantum computing breakthroughs in 2025",
            key="topic_input",
        )
        run_btn = st.button("Run Research Pipeline", use_container_width=True)

    st.markdown('<div class="try-label">Try an example →</div>', unsafe_allow_html=True)
    with st.container(key="example_chips"):
        chip_cols = st.columns(3)
        examples = ["LLM agents 2025", "CRISPR gene editing", "Fusion energy progress"]
        for c, ex in zip(chip_cols, examples):
            with c:
                if st.button(ex, key=f"ex_{ex}", use_container_width=True):
                    st.session_state.topic_input = ex
                    st.rerun()

    # Fill the space under the input card instead of leaving it empty —
    # once results exist, show mission-control stats here too.
    if st.session_state.results:
        total_elapsed = sum(m["elapsed"] for m in st.session_state.meta.values())
        total_chars = sum(len(v) for k, v in st.session_state.results.items() if isinstance(v, str))
        render_mission_control(total_elapsed, int(total_chars / 4))

with col_pipeline:
    st.markdown('<div class="section-eyebrow">Live Status</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-heading">Pipeline</div>', unsafe_allow_html=True)
    pipeline_slot = st.empty()
    render_pipeline(pipeline_slot)

    if not st.session_state.results:
        st.markdown('<div class="try-label">Meet the squad →</div>', unsafe_allow_html=True)
        render_squad_grid()


# ── Run pipeline ──────────────────────────────────────────────────────────────
if run_btn:
    if not topic.strip():
        st.warning("Please enter a research topic first.")
    else:
        st.session_state.results = {}
        st.session_state.meta = {}
        st.session_state.error = None
        st.session_state.running_step = STEPS[0][1]
        st.session_state.current_topic = topic
        render_pipeline(pipeline_slot)

        step_keys = [key for _, key, *_ in STEPS]
        try:
            for step_name, step_output, step_meta in run_research_pipeline_stream(topic):
                st.session_state.results[step_name] = step_output
                st.session_state.meta[step_name] = step_meta
                next_idx = step_keys.index(step_name) + 1
                st.session_state.running_step = step_keys[next_idx] if next_idx < len(step_keys) else None
                render_pipeline(pipeline_slot)

            score, _ = extract_score(st.session_state.results.get("critic", ""))
            st.session_state.history.insert(0, {
                "topic": topic,
                "time": datetime.now().strftime("%H:%M"),
                "score": score,
            })
        except Exception as e:
            st.session_state.error = str(e)
            render_pipeline(pipeline_slot)

        st.rerun()


# ── Results ───────────────────────────────────────────────────────────────────
r = st.session_state.results

if st.session_state.error:
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-eyebrow">Something Went Wrong</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="error-panel"><strong>The pipeline stopped partway through:</strong><br><br>{st.session_state.error}</div>
    """, unsafe_allow_html=True)
    st.caption("Common causes: an invalid or expired API key, a rate limit, or every candidate source being unreachable. Check your .env file and try again.")

elif r:
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-eyebrow">Case File</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="section-heading">{st.session_state.current_topic}</div>', unsafe_allow_html=True)

    tab_labels = []
    if "writer" in r: tab_labels.append("📄 Report")
    if "critic" in r: tab_labels.append("🧭 Critique")
    if "search" in r: tab_labels.append("🔗 Sources")

    tabs = st.tabs(tab_labels)
    idx = 0

    if "writer" in r:
        with tabs[idx]:
            st.markdown(f'<div class="result-panel">', unsafe_allow_html=True)
            st.markdown(r["writer"])
            st.markdown('</div>', unsafe_allow_html=True)
            st.write("")
            st.download_button(
                "⬇ Download Report (.md)",
                data=r["writer"],
                file_name=f"research_report_{int(time.time())}.md",
                mime="text/markdown",
            )
        idx += 1

    if "critic" in r:
        with tabs[idx]:
            score, verdict = extract_score(r["critic"])
            if score is not None:
                pct = score / 10 * 100
                verdict_html = f'<div class="score-verdict-label">Verdict</div><div class="score-verdict">"{verdict}"</div>' if verdict else ""
                st.markdown(f"""
                <div class="score-wrap">
                    <div class="score-ring" style="--pct:{pct}%;">
                        <div class="score-ring-inner">
                            <span class="score-value">{score:g}</span>
                            <span class="score-max">/ 10</span>
                        </div>
                    </div>
                    <div>{verdict_html}</div>
                </div>
                """, unsafe_allow_html=True)
            st.markdown(f'<div class="result-panel">', unsafe_allow_html=True)
            st.markdown(r["critic"])
            st.markdown('</div>', unsafe_allow_html=True)
        idx += 1

    if "search" in r:
        with tabs[idx]:
            sources = parse_sources(r["search"])
            reader_source = r.get("reader_source")
            for src in sources:
                badge = " · read in full" if reader_source and src["url"] == reader_source else ""
                st.markdown(f"""
                <div class="source-card">
                    <div class="source-title">{src['title']}</div>
                    <a class="source-url" href="{src['url']}" target="_blank">{src['url']}{badge}</a>
                    <div class="source-snippet">{src['snippet']}</div>
                </div>
                """, unsafe_allow_html=True)
            if "reader" in r:
                with st.expander("Full extracted notes from the primary source"):
                    st.markdown(r["reader"])


# ── History ──────────────────────────────────────────────────────────────────
if st.session_state.history:
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    with st.expander(f"Case Log — {len(st.session_state.history)} run{'s' if len(st.session_state.history) != 1 else ''} this session"):
        for h in st.session_state.history:
            score_txt = f"{h['score']:g}/10" if h["score"] is not None else "—"
            st.markdown(f"""
            <div class="history-row">
                <span class="history-topic">{h['topic']}</span>
                <span class="history-meta">{h['time']} · Score {score_txt}</span>
            </div>
            """, unsafe_allow_html=True)


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="footer">
    <div class="footer-brand">ResearchMind</div>
    <div class="footer-meta">LangChain multi-agent pipeline · Groq Llama 3.3 70B + Tavily · Built with Streamlit</div>
</div>
""", unsafe_allow_html=True)