"""
DAVID AI Outreach Agent - Streamlit UI
AI-powered prospecting tool that scrapes websites, analyzes business needs,
drafts personalized outreach emails, and sends them via Gmail.
"""

import os
import html as html_module
from datetime import date, timedelta, datetime
import streamlit as st
from dotenv import load_dotenv

from src.agent import OutreachAgent, AgentConfig, PipelineResult
from src.gmail_sender import get_outreach_log, update_outreach_record
from src.models import EmailDraft

load_dotenv()


def esc(text: str) -> str:
    """HTML-escape user/LLM-generated text for safe injection into markup."""
    return html_module.escape(str(text)) if text else ""


# --- Page Config ---
st.set_page_config(
    page_title="DAVID AI Outreach Agent",
    page_icon="D",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Custom Styling ---
st.markdown("""
<style>
/* ===== Google Fonts ===== */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ===== Global ===== */
*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
.main .block-container {
    padding-top: 0 !important;
    padding-bottom: 2rem;
    max-width: 960px;
    margin: 0 auto;
}
/* Kill the top gap Streamlit injects */
.appview-container .main {
    padding-top: 0 !important;
}
.appview-container {
    margin-top: -4rem !important;
}
/* Hide Streamlit default header / footer / deploy button */
#MainMenu {visibility: hidden !important;}
footer {visibility: hidden !important;}
header[data-testid="stHeader"] {
    background: transparent !important;
    height: 0 !important;
    min-height: 0 !important;
    padding: 0 !important;
}
[data-testid="stDecoration"] { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }
[data-testid="stStatusWidget"] { display: none !important; }

/* ===== Sidebar ===== */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #f8f9fc 0%, #f0f2f7 100%);
    border-right: 1px solid #e2e6ec;
}
section[data-testid="stSidebar"] .block-container {
    padding-top: 1rem;
}
section[data-testid="stSidebar"] hr {
    border-color: #e2e6ec;
    margin: 1rem 0;
}
.sidebar-section-label {
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #6b7685;
    margin-bottom: 0.5rem;
    margin-top: 0.25rem;
}
.sidebar-logo-block {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 0 0.5rem 0;
    margin-bottom: 0.5rem;
}
.sidebar-logo-mark {
    width: 40px;
    height: 40px;
    border-radius: 10px;
    background: linear-gradient(135deg, #4a8fd9, #7b68ee);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.3rem;
    font-weight: 800;
    color: #fff;
    flex-shrink: 0;
}
.sidebar-logo-text {
    font-size: 1.05rem;
    font-weight: 700;
    color: #1e2a3a;
    line-height: 1.2;
}
.sidebar-logo-sub {
    font-size: 0.7rem;
    color: #6b7685;
    font-weight: 400;
}
.sidebar-footer {
    text-align: center;
    color: #8c95a1;
    font-size: 0.75rem;
    padding-top: 0.5rem;
    line-height: 1.6;
}
.sidebar-footer a {
    color: #4a8fd9;
    text-decoration: none;
}
.sidebar-footer a:hover {
    text-decoration: underline;
}

/* ===== Tab Bar ===== */
div[data-testid="stTabs"] [role="tablist"] {
    background: #f5f7fa;
    border-radius: 12px;
    padding: 4px;
    gap: 4px;
    border: 1px solid #e2e6ec;
}
div[data-testid="stTabs"] button[role="tab"] {
    border-radius: 9px !important;
    padding: 0.5rem 1.25rem !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    color: #6b7685 !important;
    border: none !important;
    background: transparent !important;
    transition: all 0.2s;
}
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    background: #ffffff !important;
    color: #1e2a3a !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}
div[data-testid="stTabs"] button[role="tab"]:hover:not([aria-selected="true"]) {
    background: rgba(0, 0, 0, 0.03) !important;
    color: #3d4a5c !important;
}
/* Hide tab bottom border / indicator line */
div[data-testid="stTabs"] [role="tablist"]::after,
div[data-testid="stTabs"] button[role="tab"]::after,
div[data-testid="stTabs"] [data-baseweb="tab-highlight"],
div[data-testid="stTabs"] [role="tablist"] hr {
    display: none !important;
    height: 0 !important;
    border: none !important;
}

/* ===== Input Fields ===== */
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea,
div[data-baseweb="select"] {
    background: #ffffff !important;
    border: 1px solid #dce0e8 !important;
    border-radius: 8px !important;
    color: #1e2a3a !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.92rem !important;
    transition: border-color 0.2s, box-shadow 0.2s;
}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stTextArea"] textarea:focus {
    border-color: #4a8fd9 !important;
    box-shadow: 0 0 0 3px rgba(74, 143, 217, 0.12) !important;
}

/* ===== Buttons ===== */
button[kind="primary"],
button[data-testid="stBaseButton-primary"] {
    background: linear-gradient(135deg, #4a8fd9, #7b68ee) !important;
    border: none !important;
    color: #fff !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    border-radius: 8px !important;
    padding: 0.55rem 1.5rem !important;
    transition: opacity 0.2s, box-shadow 0.2s !important;
}
button[kind="primary"]:hover,
button[data-testid="stBaseButton-primary"]:hover {
    opacity: 0.9 !important;
    box-shadow: 0 4px 16px rgba(74, 143, 217, 0.2) !important;
}
button[kind="secondary"],
button[data-testid="stBaseButton-secondary"] {
    background: transparent !important;
    border: 1px solid #c8d0dc !important;
    color: #4a8fd9 !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    border-radius: 8px !important;
    padding: 0.55rem 1.5rem !important;
    transition: all 0.2s !important;
}
button[kind="secondary"]:hover,
button[data-testid="stBaseButton-secondary"]:hover {
    background: rgba(74, 143, 217, 0.05) !important;
    border-color: #4a8fd9 !important;
}

/* ===== Progress Bar ===== */
div[data-testid="stProgressBar"] > div > div {
    background: linear-gradient(90deg, #4a8fd9, #7b68ee) !important;
    border-radius: 8px !important;
}
div[data-testid="stProgressBar"] > div {
    background: #e8ebf0 !important;
    border-radius: 8px !important;
}

/* ===== Styled Cards ===== */
.styled-card {
    background: #f5f7fa;
    border: 1px solid #e2e6ec;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
}
.styled-card-accent {
    background: #f5f7fa;
    border: 1px solid rgba(123, 104, 238, 0.2);
    border-left: 3px solid #7b68ee;
    border-radius: 0 12px 12px 0;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
}

/* ===== Section Headers ===== */
.section-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-top: 1.5rem;
    margin-bottom: 0.75rem;
}
.section-icon {
    width: 36px;
    height: 36px;
    border-radius: 9px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
.section-icon svg {
    width: 18px;
    height: 18px;
}
.section-icon-blue { background: rgba(74, 143, 217, 0.1); }
.section-icon-blue svg { fill: #4a8fd9; stroke: #4a8fd9; }
.section-icon-purple { background: rgba(123, 104, 238, 0.1); }
.section-icon-purple svg { fill: #7b68ee; stroke: #7b68ee; }
.section-icon-green { background: rgba(34, 154, 60, 0.1); }
.section-icon-green svg { fill: #229a3c; stroke: #229a3c; }
.section-icon-orange { background: rgba(220, 140, 30, 0.1); }
.section-icon-orange svg { fill: #dc8c1e; stroke: #dc8c1e; }
.section-title {
    font-size: 1.15rem;
    font-weight: 700;
    color: #1e2a3a;
    margin: 0;
    line-height: 1.3;
}
.section-subtitle {
    font-size: 0.82rem;
    color: #6b7685;
    margin: 0;
    line-height: 1.3;
}

/* ===== Pain Points / Opportunities ===== */
.item-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}
.item-pain {
    background: rgba(220, 53, 69, 0.05);
    border-left: 3px solid #dc3545;
    border-radius: 0 8px 8px 0;
    padding: 0.65rem 1rem;
    font-size: 0.9rem;
    color: #1e2a3a;
    display: flex;
    align-items: flex-start;
    gap: 0.6rem;
}
.item-opp {
    background: rgba(34, 154, 60, 0.05);
    border-left: 3px solid #229a3c;
    border-radius: 0 8px 8px 0;
    padding: 0.65rem 1rem;
    font-size: 0.9rem;
    color: #1e2a3a;
    display: flex;
    align-items: flex-start;
    gap: 0.6rem;
}
.dot-red {
    width: 8px; height: 8px; border-radius: 50%;
    background: #dc3545; flex-shrink: 0; margin-top: 6px;
}
.dot-green {
    width: 8px; height: 8px; border-radius: 50%;
    background: #229a3c; flex-shrink: 0; margin-top: 6px;
}

/* ===== Tag Pills ===== */
.tag-pill {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 600;
    margin: 0.15rem 0.25rem;
    background: rgba(74, 143, 217, 0.08);
    color: #3a7fc0;
    border: 1px solid rgba(74, 143, 217, 0.15);
}
.tag-industry {
    background: rgba(123, 104, 238, 0.08);
    color: #6b58d6;
    border: 1px solid rgba(123, 104, 238, 0.15);
}

/* ===== Branded Header ===== */
.branded-header {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 0.25rem;
}
.brand-logo-mark {
    width: 52px;
    height: 52px;
    border-radius: 14px;
    background: linear-gradient(135deg, #4a8fd9, #7b68ee);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.6rem;
    font-weight: 800;
    color: #fff;
    flex-shrink: 0;
}
.brand-title {
    font-size: 1.7rem;
    font-weight: 800;
    background: linear-gradient(135deg, #4a8fd9, #7b68ee);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0;
    line-height: 1.2;
}
.brand-subtitle {
    font-size: 0.92rem;
    color: #6b7685;
    margin: 0;
    line-height: 1.3;
}
.accent-divider {
    height: 3px;
    background: linear-gradient(90deg, #4a8fd9, #7b68ee, transparent);
    border: none;
    border-radius: 3px;
    margin: 0.75rem 0 1.25rem 0;
}

/* ===== Alert / Info Box Overrides ===== */
div[data-testid="stAlert"] {
    background: #f5f7fa !important;
    border: 1px solid #e2e6ec !important;
    border-radius: 10px !important;
    color: #3d4a5c !important;
}

/* ===== Expanders ===== */
details[data-testid="stExpander"] {
    background: #f5f7fa;
    border: 1px solid #e2e6ec;
    border-radius: 10px;
}
details[data-testid="stExpander"] summary {
    font-weight: 600;
    color: #3d4a5c;
}

/* ===== Table Styling ===== */
table {
    border-collapse: collapse;
    width: 100%;
}
th {
    background: rgba(74, 143, 217, 0.06);
    color: #3a7fc0;
    font-weight: 600;
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    padding: 0.6rem 1rem;
    text-align: left;
    border-bottom: 2px solid #e2e6ec;
}
td {
    padding: 0.55rem 1rem;
    border-bottom: 1px solid #edf0f4;
    font-size: 0.9rem;
    color: #3d4a5c;
}
tr:hover td {
    background: rgba(74, 143, 217, 0.03);
}

/* ===== Metrics ===== */
div[data-testid="stMetric"] {
    background: #f5f7fa;
    border: 1px solid #e2e6ec;
    border-radius: 10px;
    padding: 0.75rem 1rem;
}
div[data-testid="stMetric"] label {
    color: #6b7685 !important;
    font-size: 0.75rem !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* ===== Status Labels ===== */
.status-sent {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 700;
    background: rgba(34, 154, 60, 0.1);
    color: #1a7a30;
}
.status-failed {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 700;
    background: rgba(220, 53, 69, 0.1);
    color: #c42d3e;
}
.status-draft {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 700;
    background: rgba(74, 143, 217, 0.1);
    color: #3a7fc0;
}
.status-opened {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 700;
    background: rgba(220, 140, 30, 0.12);
    color: #b87a10;
}
.status-replied {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 700;
    background: rgba(34, 154, 60, 0.12);
    color: #1a7a30;
}
.follow-up-due {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 600;
    background: rgba(220, 53, 69, 0.1);
    color: #c42d3e;
}
.follow-up-upcoming {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 6px;
    font-size: 0.78rem;
    font-weight: 600;
    background: rgba(74, 143, 217, 0.1);
    color: #3a7fc0;
}

/* ===== Company Overview Grid ===== */
.overview-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
}
.overview-label {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6b7685;
    margin-bottom: 0.2rem;
}
.overview-value {
    font-size: 0.95rem;
    color: #1e2a3a;
    line-height: 1.5;
}

/* ===== Pipeline Step Indicator ===== */
.pipeline-steps {
    display: flex;
    gap: 0;
    margin: 0.75rem 0;
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid #e2e6ec;
}
.pipeline-step-item {
    flex: 1;
    text-align: center;
    padding: 0.5rem 0.75rem;
    font-size: 0.78rem;
    font-weight: 600;
    color: #8c95a1;
    background: #f5f7fa;
    border-right: 1px solid #e2e6ec;
}
.pipeline-step-item:last-child { border-right: none; }
.pipeline-step-item.active {
    background: rgba(74, 143, 217, 0.08);
    color: #1e2a3a;
}
.pipeline-step-item .step-num {
    display: block;
    font-size: 0.65rem;
    color: #4a8fd9;
    margin-bottom: 2px;
}
</style>
""", unsafe_allow_html=True)


# --- SVG Icon Helpers ---
SVG_TARGET = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>'
SVG_BOOK = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>'
SVG_ENVELOPE = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg>'
SVG_SEND = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m22 2-7 20-4-9-9-4z"/><path d="m22 2-11 11"/></svg>'
SVG_GRID = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>'
SVG_DOC = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>'
SVG_CLIPBOARD = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/></svg>'
SVG_CALENDAR = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>'


def section_header(title: str, subtitle: str, svg: str, color: str) -> str:
    """Return HTML for a styled section header with SVG icon."""
    return (
        f'<div class="section-header">'
        f'<div class="section-icon section-icon-{color}">{svg}</div>'
        f'<div><p class="section-title">{esc(title)}</p>'
        f'<p class="section-subtitle">{esc(subtitle)}</p></div>'
        f'</div>'
    )


def init_session_state():
    """Initialize session state variables."""
    defaults = {
        "pipeline_result": None,
        "scrape_logs": [],
        "email_subject": "",
        "email_body": "",
        "send_result": None,
        "batch_results": [],
        # Sidebar config defaults from env vars
        "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "gmail_addr": os.getenv("GMAIL_ADDRESS", ""),
        "gmail_pass": os.getenv("GMAIL_APP_PASSWORD", ""),
        "sender_name": os.getenv("SENDER_NAME", "The DAVID AI Team"),
        "tone": "professional",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def get_agent_config() -> AgentConfig:
    """Build AgentConfig from sidebar settings."""
    return AgentConfig(
        anthropic_api_key=st.session_state.get("api_key", ""),
        gmail_address=st.session_state.get("gmail_addr", ""),
        gmail_app_password=st.session_state.get("gmail_pass", ""),
        sender_name=st.session_state.get("sender_name", "The DAVID AI Team"),
        tone=st.session_state.get("tone", "professional"),
        llm_model="claude-sonnet-4-5-20250929",
        use_playwright=True,
    )


def render_sidebar():
    """Render the configuration sidebar."""
    with st.sidebar:
        # Branded logo block
        st.markdown(
            '<div class="sidebar-logo-block">'
            '<div class="sidebar-logo-mark">D</div>'
            '<div>'
            '<div class="sidebar-logo-text">DAVID AI</div>'
            '<div class="sidebar-logo-sub">Outreach Agent</div>'
            '</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.markdown('<p class="sidebar-section-label">Configuration</p>', unsafe_allow_html=True)

        st.text_input(
            "Anthropic API Key (required)",
            type="password",
            key="api_key",
            help="Your Anthropic API key for Claude. Required for website analysis and email drafting.",
        )

        st.markdown("---")
        st.markdown('<p class="sidebar-section-label">Gmail Settings</p>', unsafe_allow_html=True)
        st.caption("Only needed when you're ready to send. Scraping and drafting work without these.")

        st.text_input(
            "Gmail Address",
            key="gmail_addr",
            help="The Gmail address emails will be sent from.",
        )
        st.text_input(
            "Gmail App Password",
            type="password",
            key="gmail_pass",
            help="16-character App Password from Google Account > Security > App Passwords. This is NOT your Gmail login password.",
        )
        st.text_input(
            "Sender Name",
            key="sender_name",
            help="The display name recipients will see (e.g. 'John from DAVID AI').",
        )

        st.markdown("---")
        st.markdown('<p class="sidebar-section-label">Email Tone</p>', unsafe_allow_html=True)

        st.selectbox(
            "Tone / Style",
            options=["professional", "conversational", "bold", "consultative"],
            index=0,
            key="tone",
            help="Controls the writing style of the generated email. Professional = polished and direct. Conversational = warm and friendly. Bold = confident and pattern-interrupting. Consultative = insight-led and advisory.",
        )

        st.markdown("---")
        st.markdown(
            '<div class="sidebar-footer">'
            'Powered by Claude<br>'
            '<a href="https://getdavid.ai" target="_blank">getdavid.ai</a>'
            ' &mdash; Scale Intelligence. Tenfold.'
            '</div>',
            unsafe_allow_html=True,
        )


def render_single_mode():
    """Render the single-URL outreach mode."""
    st.markdown(
        section_header("Single Prospect Outreach", "Scrape, analyze, and draft a personalized email", SVG_TARGET, "blue"),
        unsafe_allow_html=True,
    )
    st.caption("Paste a company's website URL below. The agent will scrape their site, analyze their business needs, and draft a personalized outreach email.")

    col1, col2 = st.columns([3, 1])
    with col1:
        url = st.text_input(
            "Prospect Website URL",
            placeholder="https://example.com",
            help="The homepage of the company you want to reach out to. The agent will automatically discover and scrape key pages (About, Services, Blog, etc.).",
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        run_clicked = st.button("Run Pipeline", type="primary", use_container_width=True)

    if run_clicked and url:
        config = get_agent_config()
        if not config.anthropic_api_key:
            st.error("Please enter your Anthropic API key in the sidebar.")
            return

        agent = OutreachAgent(config)
        st.session_state["scrape_logs"] = []
        st.session_state["send_result"] = None

        progress_container = st.container()
        status_placeholder = progress_container.empty()
        progress_bar = progress_container.progress(0)

        logs = st.session_state["scrape_logs"]

        def progress_cb(msg: str):
            logs.append(msg)
            status_placeholder.text(msg)

        # Phase 1: Scrape
        progress_bar.progress(10, "Scraping website...")
        result = PipelineResult(url=url)

        try:
            result.scraped = agent.scrape(url, progress_callback=progress_cb)
            if not result.scraped.pages:
                st.error("Failed to scrape any content from the website.")
                return
            progress_bar.progress(35, "Scraping complete")

            # Phase 2: Analyze
            progress_bar.progress(40, "Analyzing prospect needs...")
            status_placeholder.text("Analyzing prospect needs with Claude...")
            result.analysis = agent.analyze(result.scraped)
            progress_bar.progress(65, "Analysis complete")

            # Phase 3: Draft
            progress_bar.progress(70, "Drafting outreach email...")
            status_placeholder.text("Drafting personalized email...")
            result.draft = agent.draft(result.analysis)
            progress_bar.progress(100, "Pipeline complete")
            status_placeholder.text("Pipeline complete — review results below")

            result.stage = "reviewing"

        except Exception as e:
            st.error(f"Pipeline error: {e}")
            result.error = str(e)
            result.stage = "failed"
            return

        st.session_state["pipeline_result"] = result
        st.session_state["email_subject"] = result.draft.subject
        st.session_state["email_body"] = result.draft.body

    # --- Display Results ---
    result: PipelineResult = st.session_state.get("pipeline_result")
    if not result:
        st.info("Enter a prospect's website URL above and click **Run Pipeline** to start. The agent will scrape their site, analyze their needs, and draft a personalized email for you to review.")
        return

    # Scraping log (collapsible)
    with st.expander("Scraping Log — See what pages were discovered and fetched", expanded=False):
        for log_line in st.session_state.get("scrape_logs", []):
            st.text(log_line)

    # Analysis Results
    if result.analysis:
        st.markdown("---")
        st.markdown(
            section_header("Prospect Analysis", "AI-powered insights from scraped content", SVG_BOOK, "purple"),
            unsafe_allow_html=True,
        )

        # Company Overview Card
        a = result.analysis
        industry_tag = f'<span class="tag-pill tag-industry">{esc(a.industry)}</span>' if a.industry else ""
        overview_html = (
            f'<div class="styled-card">'
            f'<div class="overview-grid">'
            f'<div><div class="overview-label">Company</div><div class="overview-value">{esc(a.company_name)}</div></div>'
            f'<div><div class="overview-label">Industry</div><div class="overview-value">{industry_tag}</div></div>'
            f'</div>'
            f'<div style="margin-top:0.75rem;"><div class="overview-label">Summary</div>'
            f'<div class="overview-value">{esc(a.company_summary)}</div></div>'
            f'</div>'
        )
        st.markdown(overview_html, unsafe_allow_html=True)

        col_a, col_b = st.columns(2)

        with col_a:
            # Services as tag pills
            if a.services_offered:
                services_html = '<div class="styled-card"><div class="overview-label">Services</div><div style="margin-top:0.4rem;">'
                for s in a.services_offered:
                    services_html += f'<span class="tag-pill">{esc(s)}</span>'
                services_html += '</div></div>'
                st.markdown(services_html, unsafe_allow_html=True)

            # Pain Points
            if a.pain_points:
                pain_html = '<div class="overview-label" style="margin-top:0.5rem;">Pain Points</div><div class="item-list">'
                for p in a.pain_points:
                    pain_html += f'<div class="item-pain"><div class="dot-red"></div><div>{esc(p)}</div></div>'
                pain_html += '</div>'
                st.markdown(pain_html, unsafe_allow_html=True)

        with col_b:
            # AI Opportunities
            if a.ai_opportunities:
                opp_html = '<div class="overview-label">AI Opportunities</div><div class="item-list">'
                for o in a.ai_opportunities:
                    opp_html += f'<div class="item-opp"><div class="dot-green"></div><div>{esc(o)}</div></div>'
                opp_html += '</div>'
                st.markdown(opp_html, unsafe_allow_html=True)

        # Value Proposition card
        if a.value_proposition:
            vp_html = (
                f'<div class="styled-card-accent">'
                f'<div class="overview-label">Value Proposition</div>'
                f'<div class="overview-value">{esc(a.value_proposition)}</div>'
            )
            if a.recommended_angle:
                vp_html += (
                    f'<div style="margin-top:0.75rem;">'
                    f'<div class="overview-label">Recommended Angle</div>'
                    f'<div class="overview-value" style="font-style:italic;">{esc(a.recommended_angle)}</div>'
                    f'</div>'
                )
            vp_html += '</div>'
            st.markdown(vp_html, unsafe_allow_html=True)

    # Email Draft (editable)
    if result.draft:
        st.markdown("---")
        st.markdown(
            section_header("Email Draft", "Review and edit before sending", SVG_ENVELOPE, "green"),
            unsafe_allow_html=True,
        )
        st.caption("This email was generated based on the analysis above. Edit anything you'd like before sending — or click Regenerate for a new version.")

        edited_subject = st.text_input("Subject", value=st.session_state["email_subject"])
        edited_body = st.text_area("Body", value=st.session_state["email_body"], height=300)

        st.session_state["email_subject"] = edited_subject
        st.session_state["email_body"] = edited_body

        # Send Section
        st.markdown("---")
        st.markdown(
            section_header("Send Email", "Deliver via Gmail SMTP", SVG_SEND, "orange"),
            unsafe_allow_html=True,
        )
        st.caption("Enter the recipient's email and click send. Requires Gmail credentials in the sidebar. Nothing sends without your explicit confirmation.")

        # Auto-fill from scraped contact emails if available
        default_to = ""
        email_help = "The email address of the person you want to reach out to at this company."
        if result.scraped and result.scraped.contact_emails:
            default_to = result.scraped.contact_emails[0]
            if len(result.scraped.contact_emails) > 1:
                others = ", ".join(result.scraped.contact_emails[1:])
                email_help += f" Also found: {others}"

        to_address = st.text_input(
            "Recipient Email Address",
            value=default_to,
            placeholder="prospect@company.com",
            help=email_help,
        )

        col_send, col_regen = st.columns(2)

        with col_regen:
            if st.button("Regenerate Draft", use_container_width=True):
                config = get_agent_config()
                agent = OutreachAgent(config)
                with st.spinner("Regenerating email..."):
                    new_draft = agent.draft(result.analysis)
                st.session_state["email_subject"] = new_draft.subject
                st.session_state["email_body"] = new_draft.body
                result.draft = new_draft
                st.rerun()

        with col_send:
            send_clicked = st.button(
                "Confirm & Send",
                type="primary",
                use_container_width=True,
                disabled=not to_address,
            )

        if send_clicked and to_address:
            config = get_agent_config()

            if not config.gmail_address or not config.gmail_app_password:
                st.error("Please enter your Gmail address and App Password in the sidebar before sending. These are only stored in your browser session — not saved to any file.")
                return

            # Build final draft with edits
            final_draft = EmailDraft(
                subject=st.session_state["email_subject"],
                body=st.session_state["email_body"],
                to_address=to_address,
                tone=config.tone,
            )

            agent = OutreachAgent(config)

            with st.spinner("Sending email..."):
                send_result = agent.send(
                    draft=final_draft,
                    to_address=to_address,
                    prospect_url=result.url,
                    prospect_name=result.analysis.company_name if result.analysis else "",
                )

            st.session_state["send_result"] = send_result

            if send_result.status == "sent":
                st.success(f"Email sent successfully to {to_address}!")
            else:
                st.error(f"Failed to send: {send_result.error_message}")

    # Show send result if exists
    send_result = st.session_state.get("send_result")
    if send_result and send_result.status == "sent":
        st.balloons()

        # --- Post-Send Follow-Up Scheduling ---
        st.markdown("---")
        st.markdown(
            section_header("Schedule Follow-Up", "Set a reminder to follow up", SVG_CALENDAR, "orange"),
            unsafe_allow_html=True,
        )
        st.caption("Optionally schedule a follow-up date for this email. You can manage follow-ups from the Follow-Ups tab.")

        fu_col1, fu_col2 = st.columns([1, 2])
        with fu_col1:
            fu_date = st.date_input(
                "Follow-up date",
                value=date.today() + timedelta(days=3),
                key="post_send_fu_date",
            )
        with fu_col2:
            fu_note = st.text_input(
                "Note (optional)",
                key="post_send_fu_note",
                placeholder="e.g. Check if they opened it",
            )

        if st.button("Save Follow-Up", key="post_send_fu_save"):
            # Find the most recent record matching this send
            records = get_outreach_log()
            if records:
                last_idx = len(records) - 1
                updates = {"follow_up_date": fu_date.isoformat()}
                if fu_note:
                    updates["notes"] = fu_note
                update_outreach_record(last_idx, **updates)
                st.success(f"Follow-up scheduled for {fu_date.isoformat()}")


def render_batch_mode():
    """Render the batch processing mode."""
    st.markdown(
        section_header("Batch Mode", "Process multiple prospects at once", SVG_GRID, "blue"),
        unsafe_allow_html=True,
    )
    st.caption("Process multiple prospect URLs at once. Each one goes through the full pipeline (scrape, analyze, draft). Emails are drafted but NOT auto-sent — you review each one individually.")

    urls_text = st.text_area(
        "Enter URLs (one per line)",
        placeholder="https://company1.com\nhttps://company2.com\nhttps://company3.com",
        height=150,
    )

    if st.button("Run Batch Pipeline", type="primary"):
        urls = [u.strip() for u in urls_text.strip().splitlines() if u.strip()]
        if not urls:
            st.warning("Please enter at least one URL.")
            return

        config = get_agent_config()
        if not config.anthropic_api_key:
            st.error("Please enter your Anthropic API key in the sidebar.")
            return

        agent = OutreachAgent(config)
        batch_results = []

        progress_bar = st.progress(0)
        status = st.empty()

        for i, url in enumerate(urls):
            status.text(f"Processing {i+1}/{len(urls)}: {url}")
            progress_bar.progress((i) / len(urls))

            try:
                result = agent.run_pipeline(url=url)
                batch_results.append(result)
            except Exception as e:
                batch_results.append(PipelineResult(url=url, error=str(e), stage="failed"))

        progress_bar.progress(1.0, "Batch complete")
        status.text(f"Processed {len(urls)} prospects")
        st.session_state["batch_results"] = batch_results

    # Display batch results
    batch_results = st.session_state.get("batch_results", [])
    if batch_results:
        st.markdown("---")
        for i, result in enumerate(batch_results):
            status_label = "[OK]" if result.stage == "reviewing" else "[FAILED]"
            label_name = result.analysis.company_name if result.analysis else result.url
            with st.expander(
                f"{status_label} {label_name}",
                expanded=(i == 0),
            ):
                if result.error:
                    st.error(f"Error: {result.error}")
                    continue

                if result.analysis:
                    st.markdown(f"**Industry:** {result.analysis.industry}")
                    st.markdown(f"**Summary:** {result.analysis.company_summary}")
                    st.markdown(f"**Key Pain Point:** {result.analysis.pain_points[0] if result.analysis.pain_points else 'N/A'}")

                if result.draft:
                    st.markdown(f"**Email Subject:** {result.draft.subject}")
                    st.text_area(
                        "Email Body",
                        value=result.draft.body,
                        height=200,
                        key=f"batch_body_{i}",
                    )


def render_outreach_log():
    """Render the CRM-style outreach log with tracking controls."""
    st.markdown(
        section_header("Outreach Log", "CRM-style history with tracking", SVG_DOC, "purple"),
        unsafe_allow_html=True,
    )
    st.caption("Track every outreach email — mark as opened/replied, schedule follow-ups, and add notes.")

    records = get_outreach_log()

    if not records:
        st.info("No outreach attempts logged yet. Send an email to see it here.")
        return

    # --- Summary Metrics ---
    total = len(records)
    sent = sum(1 for r in records if r.status == "sent")
    opened = sum(1 for r in records if r.opened_at)
    replied = sum(1 for r in records if r.replied_at)
    today_str = date.today().isoformat()
    due_follow_ups = sum(
        1 for r in records
        if r.follow_up_date and r.follow_up_date <= today_str and not r.replied_at
    )

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total", total)
    m2.metric("Sent", sent)
    m3.metric("Opened", opened)
    m4.metric("Replied", replied)
    m5.metric("Due Follow-Ups", due_follow_ups)

    st.markdown("---")

    # --- Record List ---
    for idx, record in enumerate(records):
        # Determine best status badge
        if record.replied_at:
            status_html = '<span class="status-replied">REPLIED</span>'
            badge = "REPLIED"
        elif record.opened_at:
            status_html = '<span class="status-opened">OPENED</span>'
            badge = "OPENED"
        elif record.status == "sent":
            status_html = '<span class="status-sent">SENT</span>'
            badge = "SENT"
        elif record.status == "failed":
            status_html = '<span class="status-failed">FAILED</span>'
            badge = "FAILED"
        else:
            status_html = '<span class="status-draft">DRAFT</span>'
            badge = "DRAFT"

        # Follow-up indicator for expander label
        fu_label = ""
        if record.follow_up_date and not record.replied_at:
            if record.follow_up_date <= today_str:
                fu_label = " | FOLLOW-UP DUE"
            else:
                fu_label = f" | Follow-up: {record.follow_up_date}"

        expander_label = f"{badge} | {record.prospect_name or record.prospect_url} → {record.recipient_email}{fu_label}"

        with st.expander(expander_label):
            st.markdown(status_html, unsafe_allow_html=True)
            col1, col2, col3 = st.columns(3)
            col1.metric("Status", badge)
            col2.metric("Recipient", record.recipient_email)
            col3.metric("Time", record.timestamp[:19])

            # Follow-up date display
            if record.follow_up_date and not record.replied_at:
                if record.follow_up_date <= today_str:
                    days_overdue = (date.today() - date.fromisoformat(record.follow_up_date)).days
                    st.markdown(
                        f'<span class="follow-up-due">FOLLOW-UP OVERDUE by {days_overdue} day(s)</span>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        f'<span class="follow-up-upcoming">Follow-up scheduled: {record.follow_up_date}</span>',
                        unsafe_allow_html=True,
                    )

            st.markdown(f"**Subject:** {record.email_subject}")
            st.text_area("Body", value=record.email_body, height=150, key=f"log_body_{idx}", disabled=True)

            if record.error_message:
                st.error(f"Error: {record.error_message}")

            # Notes display
            if record.notes:
                st.markdown(f"**Notes:** {record.notes}")

            # --- Tracking Actions (only for sent emails) ---
            if record.status == "sent":
                st.markdown("---")
                act_cols = st.columns(4)

                with act_cols[0]:
                    if not record.opened_at:
                        if st.button("Mark as Opened", key=f"open_{idx}"):
                            update_outreach_record(idx, opened_at=datetime.now().isoformat())
                            st.rerun()
                    else:
                        st.caption(f"Opened: {record.opened_at[:19]}")

                with act_cols[1]:
                    if not record.replied_at:
                        if st.button("Mark as Replied", key=f"reply_{idx}"):
                            update_outreach_record(idx, replied_at=datetime.now().isoformat())
                            st.rerun()
                    else:
                        st.caption(f"Replied: {record.replied_at[:19]}")

                with act_cols[2]:
                    if not record.follow_up_date and not record.replied_at:
                        fu_date = st.date_input(
                            "Follow-up date",
                            value=date.today() + timedelta(days=3),
                            key=f"fu_date_{idx}",
                        )
                        if st.button("Set Follow-Up", key=f"fu_set_{idx}"):
                            update_outreach_record(idx, follow_up_date=fu_date.isoformat())
                            st.rerun()

                with act_cols[3]:
                    new_note = st.text_input("Add note", key=f"note_input_{idx}", placeholder="e.g. Spoke with VP")
                    if st.button("Save Note", key=f"note_save_{idx}") and new_note:
                        existing = record.notes or ""
                        combined = f"{existing}\n{new_note}".strip() if existing else new_note
                        update_outreach_record(idx, notes=combined)
                        st.rerun()


def render_follow_up_dashboard():
    """Render the follow-up scheduling dashboard."""
    st.markdown(
        section_header("Follow-Up Dashboard", "Upcoming and overdue follow-ups", SVG_CALENDAR, "orange"),
        unsafe_allow_html=True,
    )
    st.caption("Track scheduled follow-ups. Overdue items appear first. Snooze or mark as replied to manage your pipeline.")

    records = get_outreach_log()
    today = date.today()
    today_str = today.isoformat()

    # Filter to records with follow-up dates that haven't been replied to
    follow_ups = [
        (idx, r) for idx, r in enumerate(records)
        if r.follow_up_date and not r.replied_at
    ]

    if not follow_ups:
        st.info("No follow-ups scheduled. Send emails and set follow-up dates from the Outreach Log tab.")
        return

    # Split into overdue and upcoming
    overdue = [(i, r) for i, r in follow_ups if r.follow_up_date <= today_str]
    upcoming = [(i, r) for i, r in follow_ups if today_str < r.follow_up_date <= (today + timedelta(days=7)).isoformat()]
    later = [(i, r) for i, r in follow_ups if r.follow_up_date > (today + timedelta(days=7)).isoformat()]

    # --- Overdue ---
    if overdue:
        st.markdown(f"### Overdue ({len(overdue)})")
        for idx, record in overdue:
            days_overdue = (today - date.fromisoformat(record.follow_up_date)).days
            with st.expander(
                f"OVERDUE ({days_overdue}d) | {record.prospect_name or record.prospect_url} → {record.recipient_email}"
            ):
                st.markdown(
                    f'<span class="follow-up-due">OVERDUE by {days_overdue} day(s)</span>',
                    unsafe_allow_html=True,
                )
                st.markdown(f"**Subject:** {record.email_subject}")
                if record.notes:
                    st.markdown(f"**Notes:** {record.notes}")

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Mark as Replied", key=f"fu_reply_{idx}"):
                        update_outreach_record(idx, replied_at=datetime.now().isoformat())
                        st.rerun()
                with c2:
                    snooze_days = st.selectbox(
                        "Snooze",
                        options=[1, 2, 3, 5, 7],
                        index=0,
                        key=f"snooze_sel_{idx}",
                    )
                    if st.button("Snooze", key=f"snooze_{idx}"):
                        new_date = (today + timedelta(days=snooze_days)).isoformat()
                        update_outreach_record(idx, follow_up_date=new_date)
                        st.rerun()

    # --- Upcoming (next 7 days) ---
    if upcoming:
        st.markdown(f"### Upcoming — Next 7 Days ({len(upcoming)})")
        for idx, record in upcoming:
            days_until = (date.fromisoformat(record.follow_up_date) - today).days
            with st.expander(
                f"In {days_until}d ({record.follow_up_date}) | {record.prospect_name or record.prospect_url} → {record.recipient_email}"
            ):
                st.markdown(
                    f'<span class="follow-up-upcoming">Follow-up in {days_until} day(s)</span>',
                    unsafe_allow_html=True,
                )
                st.markdown(f"**Subject:** {record.email_subject}")
                if record.notes:
                    st.markdown(f"**Notes:** {record.notes}")

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Mark as Replied", key=f"fu_reply_{idx}"):
                        update_outreach_record(idx, replied_at=datetime.now().isoformat())
                        st.rerun()
                with c2:
                    snooze_days = st.selectbox(
                        "Snooze",
                        options=[1, 2, 3, 5, 7],
                        index=0,
                        key=f"snooze_sel_{idx}",
                    )
                    if st.button("Snooze", key=f"snooze_{idx}"):
                        new_date = (date.fromisoformat(record.follow_up_date) + timedelta(days=snooze_days)).isoformat()
                        update_outreach_record(idx, follow_up_date=new_date)
                        st.rerun()

    # --- Later ---
    if later:
        st.markdown(f"### Later ({len(later)})")
        for idx, record in later:
            days_until = (date.fromisoformat(record.follow_up_date) - today).days
            st.markdown(f"- **{record.follow_up_date}** ({days_until}d) — {record.prospect_name or record.prospect_url} → {record.recipient_email}")


# --- Main App ---
def main():
    init_session_state()
    render_sidebar()

    # Branded header
    st.markdown(
        '<div class="branded-header">'
        '<div class="brand-logo-mark">D</div>'
        '<div>'
        '<p class="brand-title">DAVID AI Outreach Agent</p>'
        '<p class="brand-subtitle">Scale Intelligence. Tenfold.</p>'
        '</div>'
        '</div>'
        '<div class="accent-divider"></div>',
        unsafe_allow_html=True,
    )

    # Pipeline overview
    with st.expander("How It Works — Pipeline Overview", expanded=False):
        st.markdown(
            '<div class="pipeline-steps">'
            '<div class="pipeline-step-item"><span class="step-num">STEP 1</span>Web Scraping</div>'
            '<div class="pipeline-step-item"><span class="step-num">STEP 2</span>Need Analysis</div>'
            '<div class="pipeline-step-item"><span class="step-num">STEP 3</span>Email Drafting</div>'
            '<div class="pipeline-step-item"><span class="step-num">STEP 4</span>Review &amp; Send</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.markdown("""
**This tool runs a 4-step AI pipeline for each prospect:**

| Step | What Happens |
|------|-------------|
| **1. Web Scraping** | Fetches the prospect's website (homepage + key pages like About, Services, Blog) and extracts clean text content. |
| **2. Need Analysis** | Sends the scraped content to Claude, which identifies the company's industry, pain points, and specific opportunities where DAVID AI could help. |
| **3. Email Drafting** | Claude writes a personalized cold outreach email that references real details from the prospect's website — not a generic template. |
| **4. Review & Send** | You review the draft, edit it if needed, and send it via Gmail SMTP. Nothing sends without your confirmation. |

**To get started:** Enter your Anthropic API key in the sidebar, paste a prospect URL, and click Run Pipeline.
Gmail credentials are only needed at step 4 (sending).
        """)

    tab1, tab2, tab3, tab4 = st.tabs(["Single Outreach", "Batch Mode", "Outreach Log", "Follow-Ups"])

    with tab1:
        render_single_mode()

    with tab2:
        render_batch_mode()

    with tab3:
        render_outreach_log()

    with tab4:
        render_follow_up_dashboard()


if __name__ == "__main__":
    main()
