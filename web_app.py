"""
CalJOBS Code Assistant - Streamlit Web Application
A web-based tool for searching, browsing, and getting AI assistance
with CalJOBS case note codes and NAICS industry codes.
"""

import json
import os
import re
from pathlib import Path

import streamlit as st
from thefuzz import fuzz

try:
    import anthropic
except ImportError:
    anthropic = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# RAG / Navigator imports
try:
    from ai_assistant import build_rag_system_prompt, detect_query_domains, format_sources_for_display
    from knowledge_base import get_collection, get_stats
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

# ─── Page Config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="CalJOBS Assistant",
    page_icon=":clipboard:",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).parent

# ─── Custom CSS ──────────────────────────────────────────────────────────────

st.markdown("""
<style>
    /* ==============================================================
       CORE READABILITY - Force light backgrounds and dark text
       ============================================================== */

    /* Force light backgrounds and dark text on all form elements */
    .stSelectbox, .stTextInput, .stTextArea, select, input, textarea {
        background-color: white !important;
        color: black !important;
    }

    /* Dropdown options */
    option {
        background-color: white !important;
        color: black !important;
    }

    /* Make sure all text is readable */
    .stMarkdown, p, span, div:not(.stButton div) {
        color: black !important;
    }

    /* ==============================================================
       FORCE LIGHT THEME - Override Streamlit dark mode everywhere
       ============================================================== */

    /* Root: light background, dark text */
    .stApp, [data-testid="stAppViewContainer"],
    [data-testid="stMainBlockContainer"], main, section {
        background-color: #f0f2f6 !important;
        color: #1a1a2e !important;
    }

    /* Sidebar: light gray background */
    [data-testid="stSidebar"],
    [data-testid="stSidebar"] > div,
    [data-testid="stSidebarContent"] {
        background-color: #e8ecf1 !important;
        color: #1a1a2e !important;
    }

    /* ==============================================================
       TEXT: Dark on light everywhere (except buttons)
       ============================================================== */

    /* Headings */
    h1, h2, h3, h4, h5, h6,
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3, [data-testid="stSidebar"] h4 {
        color: #0d1b2a !important;
    }

    /* Body text, markdown, labels */
    p, span, li, td, th, label, div.stMarkdown,
    .stMarkdown p, .stMarkdown li, .stMarkdown span,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stMarkdown p {
        color: #1a1a2e !important;
    }

    /* Captions */
    .stCaption, .stCaption *, small {
        color: #4a5568 !important;
    }

    /* Chat messages */
    [data-testid="stChatMessage"],
    [data-testid="stChatMessage"] p,
    [data-testid="stChatMessage"] li,
    [data-testid="stChatMessage"] span,
    [data-testid="stChatMessage"] div {
        color: #1a1a2e !important;
    }

    /* Alerts */
    [data-testid="stAlert"], [data-testid="stAlert"] p,
    [data-testid="stAlert"] span {
        color: #1a1a2e !important;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab"],
    .stTabs [data-baseweb="tab"] p,
    .stTabs [data-baseweb="tab"] span {
        color: #1a1a2e !important;
        font-weight: 500 !important;
    }

    /* Code blocks */
    code {
        color: #1a1a2e !important;
        background-color: #e2e8f0 !important;
    }

    /* Dividers */
    hr { border-color: #cbd5e0 !important; }

    /* ==============================================================
       INPUTS: White background, dark text, visible borders
       ============================================================== */

    /* All native inputs */
    input, textarea, select {
        color: #1a1a2e !important;
        background-color: #ffffff !important;
        border: 1px solid #cbd5e0 !important;
    }

    /* Streamlit text inputs */
    [data-testid="stTextInput"] input,
    [data-testid="stTextArea"] textarea {
        color: #1a1a2e !important;
        background-color: #ffffff !important;
        border: 1px solid #cbd5e0 !important;
        border-radius: 6px !important;
    }

    /* Chat input */
    [data-testid="stChatInput"],
    [data-testid="stChatInput"] textarea,
    [data-testid="stChatInput"] div {
        background-color: #ffffff !important;
        color: #1a1a2e !important;
    }

    /* ==============================================================
       DROPDOWNS / SELECTBOX: Light bg, dark text, everywhere
       ============================================================== */

    /* Select trigger (closed state) */
    [data-baseweb="select"],
    [data-baseweb="select"] > div,
    [data-baseweb="select"] span,
    [data-baseweb="select"] input,
    .stSelectbox > div > div,
    .stSelectbox [data-baseweb="select"] {
        background-color: #ffffff !important;
        color: #1a1a2e !important;
        border-color: #cbd5e0 !important;
    }

    /* Select dropdown menu (open state / popover) */
    [data-baseweb="popover"],
    [data-baseweb="popover"] > div,
    [data-baseweb="menu"],
    [data-baseweb="menu"] ul,
    [data-baseweb="menu"] li,
    [data-baseweb="menu"] li *,
    ul[role="listbox"],
    ul[role="listbox"] li,
    ul[role="listbox"] li * {
        background-color: #ffffff !important;
        color: #1a1a2e !important;
    }

    /* Dropdown option hover */
    [data-baseweb="menu"] li:hover,
    ul[role="listbox"] li:hover,
    [data-baseweb="menu"] li[aria-selected="true"] {
        background-color: #e3f2fd !important;
        color: #1a1a2e !important;
    }

    /* Multiselect */
    .stMultiSelect [data-baseweb="select"],
    .stMultiSelect [data-baseweb="select"] > div,
    .stMultiSelect [data-baseweb="tag"],
    .stMultiSelect [data-baseweb="tag"] span {
        background-color: #ffffff !important;
        color: #1a1a2e !important;
    }
    .stMultiSelect [data-baseweb="tag"] {
        background-color: #e3f2fd !important;
    }

    /* ==============================================================
       RADIO BUTTONS: Dark text, light background
       ============================================================== */

    .stRadio > div,
    .stRadio label,
    .stRadio label p,
    .stRadio label span,
    .stRadio label div,
    [data-baseweb="radio"],
    [data-baseweb="radio"] label,
    [data-baseweb="radio"] label *,
    div[role="radiogroup"],
    div[role="radiogroup"] label,
    div[role="radiogroup"] label *,
    div[role="radiogroup"] > div,
    div[role="radiogroup"] > div * {
        color: #1a1a2e !important;
    }

    /* ==============================================================
       EXPANDERS: Light blue cards
       ============================================================== */

    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary span,
    [data-testid="stExpander"] summary p {
        color: #0d1b2a !important;
        font-weight: 600 !important;
    }

    [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
        background-color: #e8f4fd !important;
        border: 1px solid #b3d9f2 !important;
        border-radius: 8px !important;
        padding: 16px !important;
    }
    [data-testid="stExpander"] [data-testid="stExpanderDetails"] p,
    [data-testid="stExpander"] [data-testid="stExpanderDetails"] span,
    [data-testid="stExpander"] [data-testid="stExpanderDetails"] li {
        color: #1a1a2e !important;
    }

    /* Category badges */
    .cat-badge {
        display: inline-block;
        background: #cce5ff !important;
        color: #004085 !important;
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
        border: 1px solid #b8daff;
    }

    /* ==============================================================
       BUTTONS: White text on colored/dark backgrounds
       ============================================================== */

    /* All Streamlit buttons: white text */
    .stButton > button,
    .stButton > button p,
    .stButton > button span,
    .stButton > button div {
        color: #ffffff !important;
        font-weight: 600 !important;
    }

    /* Main area buttons */
    .stApp .stButton > button {
        background-color: #37474f !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 8px 16px !important;
        font-size: 14px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.15) !important;
    }
    .stApp .stButton > button:hover {
        background-color: #455a64 !important;
        box-shadow: 0 4px 8px rgba(0,0,0,0.2) !important;
    }

    /* Sidebar buttons */
    div[data-testid="stSidebar"] .stButton > button {
        width: 100%;
        text-align: center;
        margin-bottom: 8px;
        margin-top: -4px;
        background-color: #37474f !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 0 0 8px 8px !important;
        padding: 8px 12px !important;
        font-weight: 700 !important;
        font-size: 14px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.15) !important;
    }
    div[data-testid="stSidebar"] .stButton > button p,
    div[data-testid="stSidebar"] .stButton > button span,
    div[data-testid="stSidebar"] .stButton > button div {
        color: #ffffff !important;
        font-weight: 700 !important;
    }
    div[data-testid="stSidebar"] .stButton > button:hover {
        background-color: #546e7a !important;
    }

    /* Chat input submit button */
    [data-testid="stChatInput"] button,
    [data-testid="stChatInput"] button * {
        color: #ffffff !important;
    }

    /* Disabled buttons */
    .stButton > button:disabled,
    .stButton > button:disabled p,
    .stButton > button:disabled span {
        background-color: #b0bec5 !important;
        color: #eceff1 !important;
        box-shadow: none !important;
        cursor: not-allowed !important;
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
#  DATA LOADING
# =============================================================================

@st.cache_data
def load_caljobs_db():
    """Load CalJOBS codes database."""
    for filename in ["codes_database_complete.json", "codes_database.json"]:
        path = BASE_DIR / filename
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    return None


@st.cache_data
def load_naics_db():
    """Load NAICS industry codes database."""
    path = BASE_DIR / "naics_database.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


# =============================================================================
#  SEARCH FUNCTIONS
# =============================================================================

def score_caljobs_entry(terms, entry):
    """Score a CalJOBS entry against search terms. Higher = better match."""
    query = " ".join(terms)
    code_lower = entry["code"].lower()
    name_lower = entry["name"].lower()
    desc_lower = entry["description"].lower()
    cat_lower = entry["category"].lower()
    kw_lower = " ".join(entry.get("keywords", [])).lower()

    score = 0
    for t in terms:
        if t == code_lower:
            score += 500
        elif re.search(r'\b' + re.escape(t) + r'\b', name_lower):
            score += 300
        elif t in name_lower:
            score += 200
        elif any(t in kw.lower() for kw in entry.get("keywords", [])):
            score += 150
        elif t in desc_lower:
            score += 100
        elif t in cat_lower:
            score += 50
        else:
            return 0

    fuzzy_score = max(
        fuzz.token_set_ratio(query, name_lower),
        fuzz.partial_ratio(query, name_lower),
    )
    score += int(fuzzy_score * 0.2)

    return score


def search_caljobs(db, query):
    """Search CalJOBS codes and return top 10 scored results."""
    if not db or not query.strip():
        return []
    terms = query.strip().lower().split()
    scored = []
    for entry in db["codes"]:
        s = score_caljobs_entry(terms, entry)
        if s > 0:
            scored.append((s, entry))
    scored.sort(key=lambda x: (-x[0], x[1]["code"]))
    return [(s, e) for s, e in scored[:10]]


def search_naics(naics_db, query):
    """Search NAICS codes with substring + fuzzy matching, return top 10."""
    if not naics_db or not query.strip():
        return []
    query_lower = query.strip().lower()
    scored = []
    for entry in naics_db["codes"]:
        name_lower = entry["name"].lower()
        if query_lower in name_lower:
            score = 200 + (100 if name_lower.startswith(query_lower) else 0)
            if re.search(r'\b' + re.escape(query_lower) + r'\b', name_lower):
                score += 50
        else:
            score = max(
                fuzz.token_set_ratio(query_lower, name_lower),
                fuzz.partial_ratio(query_lower, name_lower),
            )
        if score >= 60:
            scored.append((score, entry))
    scored.sort(key=lambda x: (-x[0], x[1]["code"]))
    return [(s, e) for s, e in scored[:10]]


def find_code(db, code_str):
    """Find a code entry by code number (case-insensitive)."""
    if not db:
        return None
    code_upper = code_str.upper()
    for entry in db["codes"]:
        if entry["code"].upper() == code_upper:
            return entry
    return None


# =============================================================================
#  DISPLAY HELPERS
# =============================================================================

def render_code_card(entry, key_prefix="card"):
    """Render a CalJOBS code as an expandable card with copyable fields."""
    code = entry["code"]
    name = entry["name"]
    desc = entry["description"]
    cat = entry["category"]
    requirements = entry.get("requirements", [])
    related = entry.get("related_codes", [])

    with st.expander(f"**{code}** - {name}", expanded=False):
        # Code header with badge
        st.markdown(
            f'<div style="margin-bottom:8px;">'
            f'<span style="font-size:1.3em;font-weight:700;color:#2e7d32;">{code}</span>'
            f'&nbsp;&nbsp;'
            f'<span class="cat-badge">{cat}</span>'
            f'</div>',
            unsafe_allow_html=True
        )

        # Description
        st.markdown(
            f'<div style="background:#f8f9fa;border-left:4px solid #2e7d32;'
            f'padding:10px 14px;margin:8px 0;border-radius:0 6px 6px 0;'
            f'color:#1a1a2e;">'
            f'<strong style="color:#1a1a2e;">Description:</strong> '
            f'<span style="color:#2d3748;">{desc}</span></div>',
            unsafe_allow_html=True
        )

        if requirements:
            req_html = "".join(f"<li style='color:#c62828;'>{req}</li>" for req in requirements)
            st.markdown(
                f'<div style="margin:6px 0;">'
                f'<strong style="color:#1a1a2e;">Requirements:</strong>'
                f'<ul style="margin:4px 0;">{req_html}</ul></div>',
                unsafe_allow_html=True
            )

        if related:
            st.markdown(
                f'<div style="margin:6px 0;color:#1a1a2e;">'
                f'<strong>Related codes:</strong> '
                f'<span style="color:#1565c0;">{", ".join(related)}</span></div>',
                unsafe_allow_html=True
            )

        # Copyable fields - st.code() has a built-in copy icon
        st.markdown("**Copy: Code | Title | Description** (click the copy icon in each box)")
        cols = st.columns(3)
        with cols[0]:
            st.caption("Code")
            st.code(code, language=None)
        with cols[1]:
            st.caption("Title")
            st.code(name, language=None)
        with cols[2]:
            st.caption("Description")
            st.code(desc, language=None)


def render_naics_card(entry, naics_db, key_prefix="naics"):
    """Render a NAICS code card with hierarchy path."""
    code = entry["code"]
    name = entry["name"]
    level_name = entry.get("level_name", "")
    sector_name = entry.get("sector_name", "")

    with st.expander(f"**{code}** - {name}", expanded=False):
        # Header
        st.markdown(
            f'<div style="margin-bottom:8px;">'
            f'<span style="font-size:1.3em;font-weight:700;color:#1565c0;">{code}</span>'
            f'&nbsp;&nbsp;'
            f'<span style="background:#e8eaf6;color:#283593;padding:2px 8px;'
            f'border-radius:12px;font-size:12px;font-weight:600;border:1px solid #c5cae9;">'
            f'{level_name} ({len(code)}-digit)</span>'
            f'</div>',
            unsafe_allow_html=True
        )

        st.markdown(
            f'<div style="color:#1a1a2e;margin:4px 0;">'
            f'<strong>Sector:</strong> {sector_name}</div>',
            unsafe_allow_html=True
        )

        # Build hierarchy path
        path_lines = []
        for length in range(2, len(code) + 1):
            prefix = code[:length]
            match = next((c for c in naics_db["codes"] if c["code"] == prefix), None)
            if match:
                is_current = match["code"] == code
                indent_px = (match["level"] - 1) * 20
                bg = "#e3f2fd" if is_current else "transparent"
                weight = "700" if is_current else "400"
                arrow = " &#9668;" if is_current else ""
                path_lines.append(
                    f'<div style="margin-left:{indent_px}px;padding:2px 6px;'
                    f'background:{bg};border-radius:4px;color:#1a1a2e;font-weight:{weight};">'
                    f'<code style="color:#1565c0;background:#e8eaf6;">{match["code"]}</code> '
                    f'{match["name"]}{arrow}</div>'
                )
        if path_lines:
            st.markdown(
                f'<div style="margin:8px 0;"><strong style="color:#1a1a2e;">Hierarchy:</strong>'
                + "".join(path_lines) + '</div>',
                unsafe_allow_html=True
            )

        # Children
        children = [c for c in naics_db["codes"]
                     if c.get("parent_code") == code and c["code"] != code]
        if children:
            child_items = "".join(
                f'<li style="color:#1a1a2e;"><code style="color:#1565c0;background:#e8eaf6;">'
                f'{ch["code"]}</code> {ch["name"]}</li>'
                for ch in children[:10]
            )
            extra = f'<li style="color:#4a5568;">... and {len(children) - 10} more</li>' if len(children) > 10 else ""
            st.markdown(
                f'<div style="margin:8px 0;">'
                f'<strong style="color:#1a1a2e;">Sub-categories ({len(children)}):</strong>'
                f'<ul style="margin:4px 0;">{child_items}{extra}</ul></div>',
                unsafe_allow_html=True
            )

        # Copyable fields
        st.markdown("**Copy: Code | Name** (click the copy icon in each box)")
        cols = st.columns(2)
        with cols[0]:
            st.caption("Code")
            st.code(code, language=None)
        with cols[1]:
            st.caption("Name")
            st.code(name, language=None)


# =============================================================================
#  AI ASSISTANT
# =============================================================================

def build_system_prompt(db):
    """Build AI system prompt with embedded code reference table."""
    code_table = "Code | Name | Category\n"
    code_table += "---|---|---\n"
    for entry in db["codes"]:
        code_table += f"{entry['code']} | {entry['name']} | {entry['category']}\n"

    return f"""You are a CalJOBS Code Assistant - an expert on CalJOBS activity codes used by
Business Service Representatives (BSRs) and workforce staff in California's
America's Job Centers of California (AJCCs).

Your job is to help staff identify the correct activity codes for their case notes,
explain what codes mean, suggest related codes, and answer questions about
CalJOBS documentation workflows.

## Reference: All CalJOBS Activity Codes

{code_table}

## Instructions
- When a user describes a situation, identify the most relevant CalJOBS activity code(s)
- Explain WHY each code applies to their situation
- Mention related codes they might also need
- If the situation is ambiguous, ask clarifying questions
- Be concise and practical - staff are busy
- Bold the code numbers in your responses (e.g., **E20**)
- Use bullet points for multiple codes
- If you're unsure about a code, say so rather than guessing
- If the user's question is vague or unclear, do your best to provide helpful guidance
  and suggest codes that MIGHT apply, while noting you'd need more details to be certain
- You can also answer general questions about CalJOBS workflows, even if no specific code is needed

## Common Workflows
- New client enrollment: 101 (Orientation) + 102 (Initial Assessment)
- Employer outreach: E20 (Contact) -> E28 (Services Provided) -> E03 (Job Order)
- Supportive services: 181 (Transportation), 182 (Training Support), 183 (Incentive), 188 (Other)
- Training: 300-330 range codes + NAICS industry code
- Follow-up: E60 (Job Order), E57 (Employer Follow-up)
"""


def extract_code_references(text, db):
    """Scan AI response text for CalJOBS code references and return matching entries."""
    if not db:
        return []
    found = []
    seen = set()
    # Match patterns like E20, E03, 101, 181, 300 - word boundary codes
    for entry in db["codes"]:
        code = entry["code"]
        # Look for the code as a standalone token (not part of longer number)
        pattern = r'\b' + re.escape(code) + r'\b'
        if re.search(pattern, text) and code not in seen:
            found.append(entry)
            seen.add(code)
    return found


# =============================================================================
#  SESSION STATE INITIALIZATION
# =============================================================================

if "messages" not in st.session_state:
    st.session_state.messages = []
if "quick_action_codes" not in st.session_state:
    st.session_state.quick_action_codes = []
if "quick_action_title" not in st.session_state:
    st.session_state.quick_action_title = ""
if "api_key" not in st.session_state:
    # Try Streamlit Cloud secrets first, then env var, then empty
    try:
        st.session_state.api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        st.session_state.api_key = os.environ.get("ANTHROPIC_API_KEY", "")
if "nav_history" not in st.session_state:
    st.session_state.nav_history = []
if "nav_forward" not in st.session_state:
    st.session_state.nav_forward = []


# =============================================================================
#  LOAD DATA
# =============================================================================

caljobs_db = load_caljobs_db()
naics_db = load_naics_db()


# =============================================================================
#  SIDEBAR
# =============================================================================

with st.sidebar:
    st.title("CalJOBS Assistant")

    if caljobs_db:
        total_codes = len(caljobs_db["codes"])
        total_cats = len(caljobs_db["metadata"]["categories"])
        st.caption(f"{total_codes} activity codes | {total_cats} categories")
    if naics_db:
        st.caption(f"{naics_db['metadata']['total_codes']:,} NAICS codes")

    # Show Navigator knowledge base status
    if RAG_AVAILABLE:
        try:
            kb_stats = get_stats()
            total_chunks = kb_stats.get("total_chunks", 0)
            if total_chunks > 0:
                st.caption(f"Navigator: {total_chunks:,} knowledge chunks")
        except Exception:
            pass

    # Quick Actions (moved up)
    st.subheader("Quick Actions")

    QUICK_ACTIONS = [
        ("q8", "Career Guidance (202)", ["202"], "Career Guidance/Planning", "#7b1fa2"),
        ("q9", "Job Referral Outside (121)", ["121"], "Job Referral: Outside CalJOBS", "#0288d1"),
        ("q10", "Job Referral Federal (122)", ["122"], "Job Referral: Federal", "#1976d2"),
        ("q11", "Job Development (123)", ["123"], "Job Development Contacts", "#388e3c"),
        ("q12", "Job Search Assist (125)", ["125"], "Job Search and Placement Assistance", "#5d4037"),
        ("q13", "Job Referral Web-Link (179)", ["179"], "Job Referral: Outside Web-Link", "#455a64"),
        ("q1", "Workshop Incentive (183)", ["183"], "Workshop Completion Incentive", "#2e7d32"),
        ("q2", "Transportation (181)", ["181"], "Transportation Assistance", "#1565c0"),
        ("q3", "Work Clothing (188)", ["188"], "Work Clothing / Tools", "#6a1b9a"),
        ("q6", "New Client (101+102)", ["101", "102"], "New Client Enrollment", "#c62828"),
    ]

    for key, label, codes, title, bg in QUICK_ACTIONS:
        # Render a colored HTML label above a hidden-ish streamlit button
        st.markdown(
            f'<div style="background:{bg};color:#ffffff;padding:10px 14px;'
            f'border-radius:8px 8px 0 0;font-weight:700;font-size:15px;'
            f'margin-bottom:-10px;margin-top:4px;'
            f'box-shadow:0 2px 6px rgba(0,0,0,0.2);text-align:center;">'
            f'{label}</div>',
            unsafe_allow_html=True
        )
        if st.button("Select", key=f"qa_btn_{key}", use_container_width=True):
            # Save current state to nav history before changing
            if st.session_state.quick_action_codes or st.session_state.quick_action_title:
                st.session_state.nav_history.append({
                    "codes": list(st.session_state.quick_action_codes),
                    "title": st.session_state.quick_action_title,
                })
            else:
                st.session_state.nav_history.append({"codes": [], "title": ""})
            st.session_state.nav_forward = []
            st.session_state.quick_action_codes = codes
            st.session_state.quick_action_title = title
            st.rerun()

    if st.session_state.quick_action_codes:
        st.markdown("")  # spacer
        if st.button("Clear Quick Action", use_container_width=True, key="qa_btn_clear"):
            st.session_state.quick_action_codes = []
            st.session_state.quick_action_title = ""
            st.rerun()

    # Settings - at the bottom
    st.divider()
    with st.expander("Settings", expanded=False):
        # Check if key was loaded from secrets/env (don't expose it in the input)
        key_from_secrets = False
        try:
            if st.secrets.get("ANTHROPIC_API_KEY", ""):
                key_from_secrets = True
        except Exception:
            pass

        # Also check if we have a key in session state from env var
        if not key_from_secrets and st.session_state.api_key:
            key_from_secrets = True

        if key_from_secrets:
            st.success("API key loaded", icon=":material/check:")
        else:
            st.caption("API Key (for AI Assistant)")
            api_key_input = st.text_input(
                "Anthropic API Key",
                value=st.session_state.api_key,
                type="password",
                help="Required for the AI Assistant. Set ANTHROPIC_API_KEY env var or enter here.",
                label_visibility="collapsed",
                placeholder="sk-ant-...",
            )
            if api_key_input != st.session_state.api_key:
                st.session_state.api_key = api_key_input


# =============================================================================
#  NAVIGATION BAR
# =============================================================================

nav_col1, nav_col2, nav_col3, nav_spacer = st.columns([1, 1, 1, 7])

with nav_col1:
    if st.button("Back", key="nav_back", use_container_width=True, disabled=len(st.session_state.nav_history) == 0):
        if st.session_state.nav_history:
            current = {
                "codes": list(st.session_state.quick_action_codes),
                "title": st.session_state.quick_action_title,
            }
            st.session_state.nav_forward.append(current)
            prev = st.session_state.nav_history.pop()
            st.session_state.quick_action_codes = prev["codes"]
            st.session_state.quick_action_title = prev["title"]
            st.rerun()

with nav_col2:
    if st.button("Forward", key="nav_fwd", use_container_width=True, disabled=len(st.session_state.nav_forward) == 0):
        if st.session_state.nav_forward:
            current = {
                "codes": list(st.session_state.quick_action_codes),
                "title": st.session_state.quick_action_title,
            }
            st.session_state.nav_history.append(current)
            nxt = st.session_state.nav_forward.pop()
            st.session_state.quick_action_codes = nxt["codes"]
            st.session_state.quick_action_title = nxt["title"]
            st.rerun()

with nav_col3:
    if st.button("Home", key="nav_home", use_container_width=True):
        if st.session_state.quick_action_codes:
            current = {
                "codes": list(st.session_state.quick_action_codes),
                "title": st.session_state.quick_action_title,
            }
            st.session_state.nav_history.append(current)
        st.session_state.quick_action_codes = []
        st.session_state.quick_action_title = ""
        st.session_state.nav_forward = []
        st.rerun()


# =============================================================================
#  QUICK ACTION DISPLAY (above tabs)
# =============================================================================

if st.session_state.quick_action_codes:
    qa_codes = st.session_state.quick_action_codes
    qa_title = st.session_state.quick_action_title

    st.header(qa_title)

    # Q4: Employer Contact - multi-choice with styled options
    if qa_codes == ["__Q4__"]:
        EMPLOYER_OPTIONS = [
            ("E20", "Employer Contact/Visit", "General outreach - phone call, email, or in-person visit"),
            ("E22", "Employer Contact - Job Development", "Contacting employer to develop a job opportunity for a client"),
            ("E60", "Job Order Placed/Received", "Employer has an open position - creating or updating a job order"),
            ("E69", "Employer Provided Information", "Gave employer info about services, tax credits, programs"),
            ("E57", "Employer Follow-up", "Following up on a previous contact, job order, or placement"),
        ]
        st.markdown(
            '<p style="color:#1a1a2e;font-weight:700;font-size:16px;margin-bottom:8px;">'
            'What best describes your employer interaction?</p>',
            unsafe_allow_html=True
        )
        # Render each option as a styled card for visibility
        for emp_code, emp_label, emp_desc in EMPLOYER_OPTIONS:
            st.markdown(
                f'<div style="background:#fff3e0;border-left:4px solid #e65100;'
                f'padding:8px 12px;margin:4px 0;border-radius:0 6px 6px 0;">'
                f'<span style="color:#e65100;font-weight:700;font-size:15px;">{emp_code}</span>'
                f' &mdash; '
                f'<span style="color:#1a1a2e;font-weight:600;">{emp_label}</span>'
                f'<br><span style="color:#4a5568;font-size:13px;">{emp_desc}</span>'
                f'</div>',
                unsafe_allow_html=True
            )
        selected_emp = st.selectbox(
            "Select employer code:",
            [f"{code} - {label}" for code, label, _ in EMPLOYER_OPTIONS],
            key="qa_emp_select",
        )
        if selected_emp:
            emp_code = selected_emp.split(" - ")[0]
            entry = find_code(caljobs_db, emp_code)
            if entry:
                render_code_card(entry, key_prefix="qa_emp")

    # Q5: Training + NAICS - two-step
    elif qa_codes == ["__Q5__"]:
        TRAINING_CODES = [
            ("300", "Occupational Skills Training (OST)"),
            ("301", "On-the-Job Training (OJT)"),
            ("302", "Entrepreneurial Training"),
            ("304", "Customized Training"),
            ("305", "Skills Upgrading and Retraining"),
            ("308", "Incumbent Worker Training"),
            ("321", "Transitional Job"),
            ("322", "Job Readiness Training"),
            ("325", "Apprenticeship Training"),
            ("224", "Pre-Apprenticeship Training"),
            ("330", "Local Board Determination Training"),
        ]
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Step 1: Select Training Type**")
            training_choice = st.selectbox(
                "Training code:",
                [f"{code} - {name}" for code, name in TRAINING_CODES],
                label_visibility="collapsed",
            )
            if training_choice:
                tc = training_choice.split(" - ")[0]
                entry = find_code(caljobs_db, tc)
                if entry:
                    render_code_card(entry, key_prefix="qa_train")

        with col2:
            st.markdown("**Step 2: Select NAICS Industry**")
            if naics_db:
                naics_query = st.text_input("Search NAICS:", placeholder="e.g. restaurant, trucking, software", key="q5_naics_search")
                if naics_query:
                    naics_results = search_naics(naics_db, naics_query)
                    if naics_results:
                        for score, nentry in naics_results[:5]:
                            render_naics_card(nentry, naics_db, key_prefix="qa_naics")
                    else:
                        st.info("No NAICS codes found. Try a different term.")
            else:
                st.warning("NAICS database not available.")

    # Simple quick actions (Q1, Q2, Q3, Q6)
    else:
        for code_str in qa_codes:
            entry = find_code(caljobs_db, code_str)
            if entry:
                render_code_card(entry, key_prefix="qa")

    st.divider()


# =============================================================================
#  MAIN AREA - CASE NOTE GENERATOR AS PRIMARY VIEW
# =============================================================================

# -----------------------------------------------------------------------------
#  COMPACT AI ASSISTANT (Top Section)
# -----------------------------------------------------------------------------

st.subheader("AI Assistant")
st.caption("Describe what you did and I'll suggest the right activity code.")

# Initialize AI-related session state
if "ai_suggested_codes" not in st.session_state:
    st.session_state.ai_suggested_codes = []

if not anthropic:
    st.warning("Install `anthropic` package to use the AI Assistant.")
elif not st.session_state.api_key:
    st.info("Enter your Anthropic API key in the sidebar to use the AI Assistant.")
else:
    # Compact chat display - show last 3 messages only
    if st.session_state.messages:
        for msg in st.session_state.messages[-3:]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # Chat input
    ai_query = st.text_input(
        "Ask about codes:",
        placeholder="e.g., 'What code for helping with resume?' or 'I met with an employer'",
        key="compact_ai_input",
        label_visibility="collapsed"
    )

    col_ask, col_clear = st.columns([4, 1])
    with col_ask:
        ask_btn = st.button("Ask AI", key="compact_ai_ask", use_container_width=True)
    with col_clear:
        if st.button("Clear", key="compact_ai_clear", use_container_width=True):
            st.session_state.messages = []
            st.session_state.ai_suggested_codes = []
            st.rerun()

    # Show suggested codes BELOW the Ask AI button
    if st.session_state.ai_suggested_codes:
        st.markdown("**Select a code to use:**")
        code_cols = st.columns(min(len(st.session_state.ai_suggested_codes), 4))
        for i, code_entry in enumerate(st.session_state.ai_suggested_codes[:4]):
            with code_cols[i]:
                if st.button(f"📋 {code_entry['code']}", key=f"ai_code_btn_{code_entry['code']}", use_container_width=True):
                    st.session_state.selected_casenote_code = code_entry["code"]
                    st.session_state.edited_description = code_entry.get("description", code_entry["name"])
                    st.rerun()

    if ask_btn and ai_query:
        st.session_state.messages.append({"role": "user", "content": ai_query})

        with st.chat_message("assistant"):
            try:
                client = anthropic.Anthropic(api_key=st.session_state.api_key, timeout=60.0)

                # Use RAG-enhanced prompt if available, otherwise fall back to basic
                retrieved_chunks = []
                if RAG_AVAILABLE:
                    try:
                        domain_filter = detect_query_domains(ai_query)
                        system_prompt, retrieved_chunks = build_rag_system_prompt(
                            ai_query,
                            domain_filter=domain_filter
                        )
                    except Exception:
                        # Fall back to basic prompt if RAG fails
                        system_prompt = build_system_prompt(caljobs_db) if caljobs_db else "You are a CalJOBS code assistant."
                else:
                    system_prompt = build_system_prompt(caljobs_db) if caljobs_db else "You are a CalJOBS code assistant."

                MODELS = ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"]
                assistant_text = None

                for model_name in MODELS:
                    try:
                        with client.messages.stream(
                            model=model_name,
                            max_tokens=800,
                            system=system_prompt,
                            messages=st.session_state.messages,
                        ) as stream:
                            assistant_text = st.write_stream(stream.text_stream)
                        break
                    except (anthropic.NotFoundError, anthropic.APIStatusError):
                        continue

                if assistant_text:
                    st.session_state.messages.append({"role": "assistant", "content": assistant_text})

                    # Show sources if RAG was used
                    if RAG_AVAILABLE and retrieved_chunks:
                        sources_text = format_sources_for_display(retrieved_chunks)
                        if sources_text:
                            st.caption(sources_text)

                    # Extract and store referenced codes for persistent display
                    referenced = extract_code_references(assistant_text, caljobs_db)
                    st.session_state.ai_suggested_codes = referenced if referenced else []
                    st.rerun()  # Rerun to show the code buttons

            except Exception as e:
                st.error(f"Error: {e}")

st.divider()

# -----------------------------------------------------------------------------
#  CASE NOTE GENERATOR (Main Section)
# -----------------------------------------------------------------------------

st.header("Case Note Generator")
st.caption("Select a code → Copy Subject Line and Description directly into CalJOBS")

# Initialize session state for selected code
if "selected_casenote_code" not in st.session_state:
    st.session_state.selected_casenote_code = None
if "edited_description" not in st.session_state:
    st.session_state.edited_description = ""

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("Select Activity Code")

    # Search for code
    code_search = st.text_input(
        "Search or enter code:",
        placeholder="Type code number or keyword (e.g., 102, resume, workshop)",
        key="casenote_search"
    )

    if code_search and caljobs_db:
        # Check if it's a direct code match first
        direct_match = find_code(caljobs_db, code_search.strip())
        if direct_match:
            if st.session_state.selected_casenote_code != direct_match["code"]:
                st.session_state.selected_casenote_code = direct_match["code"]
                st.session_state.edited_description = direct_match.get("description", direct_match["name"])
            st.success(f"Selected: **{direct_match['code']}** - {direct_match['name']}")
        else:
            # Search by keyword
            results = search_caljobs(caljobs_db, code_search)
            if results:
                st.markdown("**Search Results:** (click to select)")
                for score, entry in results[:6]:
                    if st.button(
                        f"{entry['code']} - {entry['name']}",
                        key=f"cn_select_{entry['code']}",
                        use_container_width=True
                    ):
                        st.session_state.selected_casenote_code = entry["code"]
                        st.session_state.edited_description = entry.get("description", entry["name"])
                        st.rerun()
            else:
                st.info("No codes found. Try a different search term.")

    st.divider()

    # Quick select common codes
    st.markdown("**Quick Select**")

    COMMON_CODES = [
        ("102", "Initial Assessment"),
        ("115", "Resume Preparation"),
        ("125", "Job Search Assistance"),
        ("200", "Individual Counseling"),
        ("202", "Career Guidance"),
        ("205", "Development of IEP"),
        ("121", "Job Referral: Outside"),
        ("181", "Transportation"),
        ("183", "Incentive Payment"),
        ("132", "Resume Workshop"),
        ("133", "Job Search Workshop"),
        ("101", "Orientation"),
    ]

    # Display as buttons in a grid
    quick_cols = st.columns(3)
    for i, (code, name) in enumerate(COMMON_CODES):
        with quick_cols[i % 3]:
            is_selected = st.session_state.selected_casenote_code == code
            btn_style = "primary" if is_selected else "secondary"
            if st.button(f"{code}", key=f"quick_cn_{code}", use_container_width=True, type=btn_style):
                entry = find_code(caljobs_db, code)
                st.session_state.selected_casenote_code = code
                st.session_state.edited_description = entry.get("description", name) if entry else name
                st.rerun()

    # Clear selection
    if st.session_state.selected_casenote_code:
        st.markdown("")
        if st.button("Clear Selection", type="secondary", use_container_width=True):
            st.session_state.selected_casenote_code = None
            st.session_state.edited_description = ""
            st.rerun()

with col2:
    st.subheader("Copy to CalJOBS")

    if st.session_state.selected_casenote_code and caljobs_db:
        entry = find_code(caljobs_db, st.session_state.selected_casenote_code)

        if entry:
            code = entry["code"]
            title = entry["name"]
            original_description = entry.get("description", title)

            # Initialize edited description if empty or different code
            if not st.session_state.edited_description or st.session_state.edited_description == "":
                st.session_state.edited_description = original_description

            # Show selected code prominently
            st.markdown(
                f'<div style="background:#e3f2fd;border-left:4px solid #1976d2;'
                f'padding:12px 16px;margin-bottom:16px;border-radius:0 8px 8px 0;">'
                f'<span style="font-size:1.4em;font-weight:700;color:#1565c0;">{code}</span>'
                f' &mdash; <span style="color:#1a1a2e;font-weight:500;">{title}</span>'
                f'</div>',
                unsafe_allow_html=True
            )

            # ═══════════════════════════════════════════════════════════════
            # SUBJECT LINE - Copy Box 1
            # ═══════════════════════════════════════════════════════════════
            st.markdown(
                '<p style="background:#4caf50;color:white;padding:8px 12px;'
                'border-radius:6px 6px 0 0;margin:0;font-weight:700;">'
                '1. SUBJECT LINE (paste into CalJOBS Subject field)</p>',
                unsafe_allow_html=True
            )
            st.code(title, language=None)

            st.markdown("")

            # ═══════════════════════════════════════════════════════════════
            # DESCRIPTION - Main Copy Box with Edit Option
            # ═══════════════════════════════════════════════════════════════
            st.markdown(
                '<p style="background:#2196f3;color:white;padding:8px 12px;'
                'border-radius:6px 6px 0 0;margin:0;font-weight:700;">'
                '2. DESCRIPTION 📋</p>',
                unsafe_allow_html=True
            )

            # Add CSS to make this specific code block wrap text
            st.markdown("""
                <style>
                    [data-testid="stCode"] code {
                        white-space: pre-wrap !important;
                        word-wrap: break-word !important;
                    }
                </style>
            """, unsafe_allow_html=True)

            # Single copy box with word wrap
            st.code(st.session_state.edited_description, language=None)

            # Edit option in expander
            with st.expander("✏️ Edit description", expanded=False):
                edited_desc = st.text_area(
                    "Edit:",
                    value=st.session_state.edited_description,
                    height=100,
                    key="desc_editor",
                    label_visibility="collapsed"
                )
                if edited_desc != st.session_state.edited_description:
                    st.session_state.edited_description = edited_desc
                    st.rerun()

                if st.session_state.edited_description != original_description:
                    if st.button("↩ Reset to Original", key="reset_desc"):
                        st.session_state.edited_description = original_description
                        st.rerun()

            # Show character counts
            st.caption(f"Subject: {len(title)} chars | Description: {len(st.session_state.edited_description)} chars")

    else:
        st.info("Select an activity code on the left to see the Subject Line and Description.")

        # Show example of what they'll get
        st.markdown("---")
        st.markdown("**Example Output:**")
        st.markdown(
            '<div style="background:#f5f5f5;padding:12px;border-radius:8px;margin-top:8px;">'
            '<p style="color:#4caf50;margin:0 0 4px 0;font-weight:700;font-size:12px;">1. SUBJECT LINE:</p>'
            '<code style="color:#1565c0;background:#e3f2fd;padding:4px 8px;border-radius:4px;">Initial Assessment</code>'
            '<p style="color:#2196f3;margin:16px 0 4px 0;font-weight:700;font-size:12px;">2. DESCRIPTION:</p>'
            '<code style="color:#1565c0;background:#e3f2fd;padding:4px 8px;border-radius:4px;display:block;">'
            'Assessment of aptitudes, abilities, interests, skill levels, literacy, '
            'and related needs for Workforce Innovation and Opportunity Act services.</code>'
            '</div>',
            unsafe_allow_html=True
        )

st.divider()

# =============================================================================
#  ADDITIONAL TABS (Search & Browse)
# =============================================================================

tab_search, tab_browse = st.tabs(["Search Codes", "Browse Categories"])


# -----------------------------------------------------------------------------
#  TAB 1: SEARCH
# -----------------------------------------------------------------------------

with tab_search:
    search_query = st.text_input(
        "Search",
        placeholder="Enter keywords (e.g., training, employer, transportation)",
        key="search_input",
    )

    search_scope = st.radio(
        "Search in:",
        ["CalJOBS", "NAICS", "Both"],
        horizontal=True,
        key="search_scope",
    )

    if search_query:
        # CalJOBS results
        if search_scope in ("CalJOBS", "Both") and caljobs_db:
            results = search_caljobs(caljobs_db, search_query)
            if results:
                st.subheader(f"CalJOBS Results ({len(results)})")
                for score, entry in results:
                    render_code_card(entry, key_prefix="search_cj")
            elif search_scope == "CalJOBS":
                st.info("No CalJOBS codes found. Try different keywords.")

        # NAICS results
        if search_scope in ("NAICS", "Both") and naics_db:
            results = search_naics(naics_db, search_query)
            if results:
                st.subheader(f"NAICS Results ({len(results)})")
                for score, entry in results:
                    render_naics_card(entry, naics_db, key_prefix="search_na")
            elif search_scope == "NAICS":
                st.info("No NAICS codes found. Try different keywords.")
    else:
        st.caption("Enter a search term above to find CalJOBS activity codes or NAICS industry codes.")


# -----------------------------------------------------------------------------
#  TAB 2: BROWSE
# -----------------------------------------------------------------------------

with tab_browse:
    browse_type = st.radio("Browse:", ["CalJOBS Categories", "NAICS Sectors"], horizontal=True, key="browse_type")

    if browse_type == "CalJOBS Categories" and caljobs_db:
        categories = caljobs_db["metadata"]["categories"]

        # Count codes per category
        cat_counts = {}
        for entry in caljobs_db["codes"]:
            cat = entry["category"]
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        selected_cats = st.multiselect(
            "Filter by category:",
            categories,
            default=[],
            placeholder="Select categories to browse...",
        )

        if selected_cats:
            for cat in selected_cats:
                st.subheader(f"{cat} ({cat_counts.get(cat, 0)})")
                codes = [e for e in caljobs_db["codes"] if e["category"] == cat]
                for entry in codes:
                    render_code_card(entry, key_prefix=f"browse_{cat[:5]}")
        else:
            # Show category summary
            st.markdown("**Select a category above to view its codes.**")
            cols = st.columns(2)
            for i, cat in enumerate(categories):
                with cols[i % 2]:
                    count = cat_counts.get(cat, 0)
                    st.markdown(f"- **{cat}** ({count} codes)")

    elif browse_type == "NAICS Sectors" and naics_db:
        sectors = naics_db["sectors"]

        # Sector selector
        sector_options = [f"{s['code']} - {s['name']} ({s['code_count']})" for s in sectors]
        selected_sector_str = st.selectbox("Select a sector:", [""] + sector_options, key="naics_sector")

        if selected_sector_str and selected_sector_str != "":
            sector_code = selected_sector_str.split(" - ")[0]
            sector = next((s for s in sectors if s["code"] == sector_code), None)

            if sector:
                prefixes = sector.get("prefixes", [sector["code"]])

                # Get subsectors (level 3) for this sector
                subsectors = [
                    c for c in naics_db["codes"]
                    if c["level"] == 3 and c["sector_code"] in prefixes
                ]

                if subsectors:
                    sub_options = [f"{s['code']} - {s['name']}" for s in subsectors]
                    selected_sub = st.selectbox(
                        "Drill down to subsector:",
                        ["(All subsectors)"] + sub_options,
                        key="naics_subsector",
                    )

                    if selected_sub == "(All subsectors)":
                        # Show all subsectors as cards
                        for sub in subsectors:
                            render_naics_card(sub, naics_db, key_prefix="browse_sub")
                    else:
                        sub_code = selected_sub.split(" - ")[0]

                        # Get industry groups under this subsector (level 4)
                        industry_groups = [
                            c for c in naics_db["codes"]
                            if c["level"] == 4 and c.get("parent_code") == sub_code
                        ]

                        if industry_groups:
                            ig_options = [f"{g['code']} - {g['name']}" for g in industry_groups]
                            selected_ig = st.selectbox(
                                "Drill down to industry group:",
                                ["(All industry groups)"] + ig_options,
                                key="naics_ig",
                            )

                            if selected_ig == "(All industry groups)":
                                for ig in industry_groups:
                                    render_naics_card(ig, naics_db, key_prefix="browse_ig")
                            else:
                                ig_code = selected_ig.split(" - ")[0]

                                # Show all codes under this industry group
                                children = [
                                    c for c in naics_db["codes"]
                                    if c["code"].startswith(ig_code) and c["code"] != ig_code
                                ]
                                if children:
                                    for child in children:
                                        render_naics_card(child, naics_db, key_prefix="browse_child")
                                else:
                                    # Show the industry group itself
                                    ig_entry = next((c for c in naics_db["codes"] if c["code"] == ig_code), None)
                                    if ig_entry:
                                        render_naics_card(ig_entry, naics_db, key_prefix="browse_ig_single")
                        else:
                            # Show codes directly under subsector
                            direct = [
                                c for c in naics_db["codes"]
                                if c["code"].startswith(sub_code) and c["code"] != sub_code
                            ]
                            for d in direct:
                                render_naics_card(d, naics_db, key_prefix="browse_direct")
        else:
            st.caption("Select a sector above to browse NAICS codes.")
