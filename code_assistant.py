"""
CalJOBS Code Assistant
A command-line tool for searching and browsing CalJOBS case note codes
and NAICS industry codes, with an AI-guided wizard for BSR workflows.
"""

import json
import os
import sys
import re
from datetime import datetime

# Force UTF-8 output on Windows
if sys.platform == "win32":
    os.system("chcp 65001 >nul 2>&1")
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")

import pyperclip
from colorama import init, Fore, Style
from thefuzz import fuzz

init(autoreset=True)

# ─── Colors ──────────────────────────────────────────────────────────────────

GREEN  = Fore.GREEN  + Style.BRIGHT
CYAN   = Fore.CYAN   + Style.BRIGHT
YELLOW = Fore.YELLOW + Style.BRIGHT
RED    = Fore.RED    + Style.BRIGHT
WHITE  = Fore.WHITE  + Style.BRIGHT
MAG    = Fore.MAGENTA + Style.BRIGHT
DIM    = Fore.WHITE  + Style.DIM
RESET  = Style.RESET_ALL

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RECENT_FILE = os.path.join(BASE_DIR, "recent_codes.json")


# ══════════════════════════════════════════════════════════════════════════════
#  WIZARD DATA — Decision Tree, Quick Scenarios, Industry NAICS Map
# ══════════════════════════════════════════════════════════════════════════════

WIZARD_TREE = {
    "root": {
        "question": "What type of activity are you documenting?",
        "help": "Example: You just finished a meeting with an employer or helped a client with a service.",
        "options": [
            {"label": "Employer-related activity", "next": "employer_activity"},
            {"label": "Supportive services for a client", "next": "supportive_services"},
        ],
    },
    "employer_activity": {
        "question": "What kind of employer activity?",
        "help": "Example: You visited a business, developed a job opening, or followed up on a placement.",
        "options": [
            {"label": "Employer outreach / site visit", "next": "employer_outreach"},
            {"label": "Job development / job order", "next": "job_development"},
            {"label": "Follow-up on placement or referral", "next": "followup"},
            {"label": "Tax credits (WOTC/ETP)", "next": "tax_credits"},
            {"label": "Training coordination (OJT/CT)", "next": "training"},
            {"label": "Youth outreach / work experience", "next": "youth_outreach"},
            {"label": "Rapid Response / layoff aversion", "next": "rapid_response"},
            {"label": "Job fair / recruitment event", "next": "job_fair"},
        ],
    },
    "employer_outreach": {
        "question": "What was the purpose of the outreach?",
        "help": "Example: You visited ABC Manufacturing to drop off brochures and talk about hiring.",
        "options": [
            {
                "label": "Initial contact / cold call",
                "result": {
                    "codes": ["E20"],
                    "naics_hint": "Look up the employer's industry",
                    "description": "First contact with a new employer to introduce AJCC services.",
                },
            },
            {
                "label": "Presented services / left materials",
                "result": {
                    "codes": ["E20", "E28"],
                    "naics_hint": "Look up the employer's industry",
                    "description": "Outreach visit where you presented AJCC services or left brochures/materials.",
                },
            },
            {
                "label": "Worksite visit (existing employer)",
                "result": {
                    "codes": ["E28"],
                    "naics_hint": "Look up the employer's industry",
                    "description": "Visit to an existing employer partner's worksite.",
                },
            },
            {
                "label": "Partnership / MOU discussion",
                "result": {
                    "codes": ["E28", "E60"],
                    "naics_hint": "Look up the employer's industry",
                    "description": "Discussion about formalizing a partnership or memorandum of understanding.",
                },
            },
        ],
    },
    "job_development": {
        "question": "What type of job development activity?",
        "help": "Example: You worked with an employer to create a new job listing in CalJOBS.",
        "options": [
            {
                "label": "Created / updated a job order",
                "result": {
                    "codes": ["E03"],
                    "naics_hint": "Look up the employer's industry",
                    "description": "Developed or updated a job order/listing in CalJOBS for an employer.",
                },
            },
            {
                "label": "Referred candidates to employer",
                "result": {
                    "codes": ["E03", "E60"],
                    "naics_hint": "Look up the employer's industry",
                    "description": "Referred qualified candidates to an employer's open position.",
                },
            },
            {
                "label": "Customized job posting assistance",
                "result": {
                    "codes": ["E03", "E28"],
                    "naics_hint": "Look up the employer's industry",
                    "description": "Helped employer craft or customize a job posting for better results.",
                },
            },
            {
                "label": "Job matching / screening candidates",
                "result": {
                    "codes": ["E03", "E92"],
                    "naics_hint": "Look up the employer's industry",
                    "description": "Screened and matched candidates to employer job requirements.",
                },
            },
        ],
    },
    "followup": {
        "question": "What kind of follow-up?",
        "help": "Example: You called an employer to check how a placed candidate is performing after 30 days.",
        "options": [
            {
                "label": "Post-placement follow-up (employer)",
                "result": {
                    "codes": ["E60", "E28"],
                    "naics_hint": "Look up the employer's industry",
                    "description": "Follow-up with employer after candidate placement to check on performance.",
                },
            },
            {
                "label": "Post-referral follow-up",
                "result": {
                    "codes": ["E60"],
                    "naics_hint": None,
                    "description": "Follow-up on a previous referral to check interview/hiring outcome.",
                },
            },
            {
                "label": "Retention check (60/90/180 day)",
                "result": {
                    "codes": ["E60"],
                    "naics_hint": "Look up the employer's industry",
                    "description": "Retention milestone check-in with employer or placed candidate.",
                },
            },
        ],
    },
    "tax_credits": {
        "question": "What tax credit activity?",
        "help": "Example: You helped an employer complete WOTC pre-screening forms for a new hire.",
        "options": [
            {
                "label": "WOTC pre-screening / forms",
                "result": {
                    "codes": ["E43"],
                    "naics_hint": None,
                    "description": "Assisted employer with Work Opportunity Tax Credit pre-screening or paperwork.",
                },
            },
            {
                "label": "WOTC employer education",
                "result": {
                    "codes": ["E43", "E28"],
                    "naics_hint": None,
                    "description": "Educated employer about WOTC benefits and eligibility.",
                },
            },
            {
                "label": "ETP coordination",
                "result": {
                    "codes": ["E28"],
                    "naics_hint": "Look up the employer's industry",
                    "description": "Coordinated Employment Training Panel activities with employer.",
                },
            },
            {
                "label": "Federal bonding information",
                "result": {
                    "codes": ["E14"],
                    "naics_hint": None,
                    "description": "Provided information about the Federal Bonding Program to employer.",
                },
            },
        ],
    },
    "training": {
        "question": "What type of training coordination?",
        "help": "Example: You set up an OJT contract between an employer and a WIOA participant.",
        "options": [
            {
                "label": "OJT contract / setup",
                "result": {
                    "codes": ["E60", "E28"],
                    "naics_hint": "Look up the employer's industry",
                    "description": "Set up or managed an On-the-Job Training (OJT) contract with employer.",
                },
            },
            {
                "label": "Customized Training (CT)",
                "result": {
                    "codes": ["E60", "E28"],
                    "naics_hint": "Look up the employer's industry",
                    "description": "Coordinated Customized Training with employer for specific skill needs.",
                },
            },
            {
                "label": "Training provider coordination",
                "result": {
                    "codes": ["E60"],
                    "naics_hint": None,
                    "description": "Coordinated with a training provider on behalf of employer or participant.",
                },
            },
            {
                "label": "Apprenticeship outreach",
                "result": {
                    "codes": ["E28", "E60"],
                    "naics_hint": "Look up the employer's industry",
                    "description": "Outreach to employer about registered apprenticeship opportunities.",
                },
            },
        ],
    },
    "youth_outreach": {
        "question": "What type of youth activity?",
        "help": "Example: You arranged a work experience placement for a youth participant at a local business.",
        "options": [
            {
                "label": "Work experience placement",
                "result": {
                    "codes": ["E60", "E28"],
                    "naics_hint": "Look up the employer's industry",
                    "description": "Placed a youth participant in a work experience at an employer site.",
                },
            },
            {
                "label": "Youth employer recruitment",
                "result": {
                    "codes": ["E20", "E28"],
                    "naics_hint": "Look up the employer's industry",
                    "description": "Recruited employers to participate in youth work experience programs.",
                },
            },
            {
                "label": "Career exploration / guest speaker",
                "result": {
                    "codes": ["E28"],
                    "naics_hint": "Look up the employer's industry",
                    "description": "Coordinated employer career exploration activity or guest speaker event.",
                },
            },
            {
                "label": "Youth job shadowing",
                "result": {
                    "codes": ["E28"],
                    "naics_hint": "Look up the employer's industry",
                    "description": "Set up job shadowing opportunity for youth participant.",
                },
            },
        ],
    },
    "rapid_response": {
        "question": "What Rapid Response activity?",
        "help": "Example: You responded to a WARN notice and helped coordinate services for affected workers.",
        "options": [
            {
                "label": "WARN notice / layoff response",
                "result": {
                    "codes": ["E60", "E28"],
                    "naics_hint": "Look up the employer's industry",
                    "description": "Responded to a WARN notice or layoff event at employer site.",
                },
            },
            {
                "label": "Layoff aversion outreach",
                "result": {
                    "codes": ["E28", "E20"],
                    "naics_hint": "Look up the employer's industry",
                    "description": "Proactive outreach to employer at risk of layoffs to discuss aversion strategies.",
                },
            },
            {
                "label": "Transition services coordination",
                "result": {
                    "codes": ["E60", "E28"],
                    "naics_hint": "Look up the employer's industry",
                    "description": "Coordinated transition services for workers affected by layoff/closure.",
                },
            },
        ],
    },
    "job_fair": {
        "question": "What type of hiring event?",
        "help": "Example: You organized a mini job fair with 5 employers at your AJCC.",
        "options": [
            {
                "label": "Organized / hosted a job fair",
                "result": {
                    "codes": ["E28", "E20"],
                    "naics_hint": None,
                    "description": "Organized or hosted a job fair or hiring event.",
                },
            },
            {
                "label": "Recruited employers for event",
                "result": {
                    "codes": ["E20", "E28"],
                    "naics_hint": None,
                    "description": "Recruited employer participation for an upcoming hiring event.",
                },
            },
            {
                "label": "On-site recruitment event",
                "result": {
                    "codes": ["E28", "E03"],
                    "naics_hint": "Look up the employer's industry",
                    "description": "Facilitated an on-site recruitment event at employer location.",
                },
            },
            {
                "label": "Virtual hiring event",
                "result": {
                    "codes": ["E28", "E03"],
                    "naics_hint": None,
                    "description": "Coordinated or facilitated a virtual hiring event.",
                },
            },
        ],
    },
    "supportive_services": {
        "question": "What type of supportive service?",
        "help": "Example: You helped a client get bus passes or arranged childcare assistance.",
        "options": [
            {
                "label": "Transportation assistance (bus pass, gas card)",
                "result": {
                    "codes": ["181"],
                    "naics_hint": None,
                    "description": "Provided transportation supportive services (bus pass, gas card, etc.).",
                },
            },
            {
                "label": "Training-related support (books, supplies, fees)",
                "result": {
                    "codes": ["182"],
                    "naics_hint": None,
                    "description": "Provided training-related supportive services (books, supplies, exam fees).",
                },
            },
            {
                "label": "Other supportive services (clothing, tools, documents)",
                "result": {
                    "codes": ["188"],
                    "naics_hint": None,
                    "description": "Provided other supportive services (work clothing, tools, ID documents, etc.).",
                },
            },
        ],
    },
}


QUICK_SCENARIOS = {
    "A": {
        "label": "Client got a job",
        "codes": ["E60", "E03"],
        "naics_hint": "Look up the employer's industry",
        "description": "Client obtained employment. Record the placement and update the job order.",
    },
    "B": {
        "label": "Client starting training",
        "codes": ["E60"],
        "naics_hint": None,
        "description": "Client is enrolling in or starting a training program.",
    },
    "C": {
        "label": "Worksite visit",
        "codes": ["E28"],
        "naics_hint": "Look up the employer's industry",
        "description": "Visited an employer worksite for outreach, monitoring, or relationship building.",
    },
    "D": {
        "label": "Upload documents",
        "codes": ["E92"],
        "naics_hint": None,
        "description": "Uploaded or processed documents for a participant's case file.",
    },
}


# ─── Utilities ───────────────────────────────────────────────────────────────

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def pause():
    input(f"\n{DIM}Press Enter to continue...{RESET}")


def print_header(title):
    print()
    print(f"{GREEN}{'=' * 60}")
    print(f"  {title.upper()}")
    print(f"{'=' * 60}{RESET}")
    print()


def print_divider():
    print(f"{DIM}{'-' * 60}{RESET}")


def word_wrap(text, width=54, indent=4):
    prefix = " " * indent
    words = text.split()
    line = ""
    for word in words:
        if len(line) + len(word) + 1 > width:
            print(f"{prefix}{line.strip()}")
            line = ""
        line += word + " "
    if line.strip():
        print(f"{prefix}{line.strip()}")


def copy_or_save(text, label):
    while True:
        print(f"\n  {YELLOW}[C]{RESET} Copy to clipboard")
        print(f"  {YELLOW}[S]{RESET} Save to file")
        print(f"  {YELLOW}[B]{RESET} Go back\n")
        choice = input(f"  {YELLOW}Choose an option: {RESET}").strip().upper()
        if choice == "C":
            try:
                pyperclip.copy(text)
                print(f"\n  {GREEN}Copied to clipboard!{RESET}")
            except pyperclip.PyperclipException:
                print(f"\n  {RED}Clipboard not available in this environment.{RESET}")
        elif choice == "S":
            filename = f"{label}_details.txt"
            with open(os.path.join(BASE_DIR, filename), "w", encoding="utf-8") as f:
                f.write(text)
            print(f"\n  {GREEN}Saved to {filename}{RESET}")
        elif choice == "B":
            break
        else:
            print(f"\n  {RED}Invalid option. Enter C, S, or B.{RESET}")


def paginated_list(items, title, render_row, on_select, page_size=20):
    """Generic paginated list with selection."""
    if not items:
        print(f"\n  {RED}No results found.{RESET}")
        pause()
        return

    page = 0
    total_pages = (len(items) - 1) // page_size + 1

    while True:
        clear_screen()
        print_header(title)

        start = page * page_size
        end = min(start + page_size, len(items))
        page_items = items[start:end]

        print(f"  {DIM}{len(items)} result(s)  |  Page {page + 1}/{total_pages}{RESET}\n")

        for i, item in enumerate(page_items, start + 1):
            render_row(i, item)

        print()
        print_divider()
        nav = []
        if page > 0:
            nav.append(f"{YELLOW}[P]{RESET} Prev page")
        if page < total_pages - 1:
            nav.append(f"{YELLOW}[N]{RESET} Next page")
        nav.append(f"{YELLOW}[0]{RESET} Go back")
        print(f"  {'   '.join(nav)}\n")

        choice = input(f"  {YELLOW}Enter # to select, or P/N/0: {RESET}").strip().upper()
        if choice == "0":
            return
        elif choice == "N" and page < total_pages - 1:
            page += 1
        elif choice == "P" and page > 0:
            page -= 1
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(items):
                    on_select(items[idx])
                    return
                else:
                    print(f"  {RED}Enter a number between 1 and {len(items)}.{RESET}")
                    pause()
            except ValueError:
                print(f"  {RED}Invalid input.{RESET}")
                pause()


# ─── Database loading ────────────────────────────────────────────────────────

def load_json(filename):
    path = os.path.join(BASE_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"{RED}Error: {filename} not found.{RESET}")
        print(f"{DIM}Make sure the file is in: {BASE_DIR}{RESET}")
        return None
    except json.JSONDecodeError:
        print(f"{RED}Error: {filename} contains invalid JSON.{RESET}")
        return None


# ─── Recently Used Codes ─────────────────────────────────────────────────────

def load_recent():
    """Load recently used wizard results from file."""
    try:
        with open(RECENT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_recent(result):
    """Save a wizard result to the recent codes list (max 5)."""
    recent = load_recent()
    entry = {
        "codes": result["codes"],
        "description": result["description"],
        "naics_hint": result.get("naics_hint"),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    recent.insert(0, entry)
    recent = recent[:5]
    with open(RECENT_FILE, "w", encoding="utf-8") as f:
        json.dump(recent, f, indent=2)


# ─── Smarter Search Scoring ─────────────────────────────────────────────────

def score_caljobs_entry(terms, entry):
    """Score a CalJOBS entry against search terms. Higher = better match."""
    query = " ".join(terms)
    code_lower = entry["code"].lower()
    name_lower = entry["name"].lower()
    desc_lower = entry["description"].lower()
    cat_lower = entry["category"].lower()
    kw_lower = " ".join(entry["keywords"]).lower()

    score = 0

    for t in terms:
        # Code match (highest priority)
        if t == code_lower:
            score += 500
        # Exact whole-word match in name
        elif re.search(r'\b' + re.escape(t) + r'\b', name_lower):
            score += 300
        # Substring in name
        elif t in name_lower:
            score += 200
        # Keyword match
        elif any(t in kw.lower() for kw in entry["keywords"]):
            score += 150
        # Description match
        elif t in desc_lower:
            score += 100
        # Category match
        elif t in cat_lower:
            score += 50
        else:
            # No direct match for this term — skip entry
            return 0

    # Fuzzy bonus on the full query vs name
    fuzzy_score = max(
        fuzz.token_set_ratio(query, name_lower),
        fuzz.partial_ratio(query, name_lower),
    )
    score += int(fuzzy_score * 0.2)  # 0-20 bonus

    return score


def ranked_search_results(scored_items, title, render_row, on_select, initial_count=5):
    """Display top results with option to show more."""
    if not scored_items:
        print(f"\n  {RED}No results found.{RESET}")
        pause()
        return

    show_all = False

    while True:
        clear_screen()
        print_header(title)

        display = scored_items if show_all else scored_items[:initial_count]

        if not show_all:
            print(f"  {DIM}Top {len(display)} of {len(scored_items)} result(s){RESET}\n")
        else:
            print(f"  {DIM}{len(scored_items)} result(s){RESET}\n")

        # Column headers
        print(f"  {DIM}{'':>6}  {'Code':<8} {'Name':<30} {'Category'}{RESET}")
        print(f"  {DIM}{'-' * 54}{RESET}")

        for i, item in enumerate(display, 1):
            star = f"{GREEN}*{RESET}" if i == 1 else " "
            render_row(i, item, star)

        print()
        print_divider()

        nav = []
        if not show_all and len(scored_items) > initial_count:
            nav.append(f"{YELLOW}[M]{RESET} Show more")
        nav.append(f"{YELLOW}[0]{RESET} Go back")
        print(f"  {'   '.join(nav)}\n")

        choice = input(f"  {YELLOW}Enter # to select, or M/0: {RESET}").strip().upper()
        if choice == "0":
            return
        elif choice == "M" and not show_all and len(scored_items) > initial_count:
            show_all = True
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(display):
                    on_select(display[idx])
                    return
                else:
                    print(f"  {RED}Enter a number between 1 and {len(display)}.{RESET}")
                    pause()
            except ValueError:
                print(f"  {RED}Invalid input.{RESET}")
                pause()


# ══════════════════════════════════════════════════════════════════════════════
#  CALJOBS CASE NOTE CODES
# ══════════════════════════════════════════════════════════════════════════════

def _try_copy(text):
    """Try to copy text to clipboard. Returns a status message."""
    try:
        pyperclip.copy(text)
        return f"{GREEN}Copied!{RESET}"
    except pyperclip.PyperclipException:
        return f"{RED}Clipboard not available.{RESET}"


def show_code_detail(entry, header_title="CODE DETAILS", tip=None, back_label="Back"):
    """Reusable code detail view with individual copy options.

    Returns when user presses back. Stays open for multiple copies.
    """
    code = entry["code"]
    name = entry["name"]
    desc = entry["description"]
    cat  = entry["category"]
    requirements = entry.get("requirements", [])
    related = entry.get("related_codes", [])

    while True:
        clear_screen()

        # Header box
        print()
        print(f"  {GREEN}{'=' * 49}")
        print(f"    {header_title}")
        print(f"  {'=' * 49}{RESET}")
        print()

        # Code number
        print(f"  {WHITE}CODE NUMBER:{RESET}  {CYAN}{Style.BRIGHT}{code}{RESET}")
        print(f"  {DIM}[Press 1 to copy]{RESET}")
        print()

        # Title
        print(f"  {WHITE}TITLE:{RESET}  {WHITE}{name}{RESET}")
        print(f"  {DIM}[Press 2 to copy]{RESET}")
        print()

        # Description
        print(f"  {WHITE}DESCRIPTION:{RESET}")
        print(f"  {DIM}{'-' * 49}{RESET}")
        word_wrap(desc, width=47, indent=2)
        print(f"  {DIM}{'-' * 49}{RESET}")
        print(f"  {DIM}[Press 3 to copy]{RESET}")
        print()

        # Category + metadata
        print(f"  {WHITE}Category:{RESET} {cat}")
        if requirements:
            print(f"  {WHITE}Requirements:{RESET}")
            for req in requirements:
                print(f"    {RED}-{RESET} {req}")
        if related:
            print(f"  {WHITE}Related codes:{RESET} {DIM}{', '.join(related)}{RESET}")

        # Tip / reminder
        if tip:
            print()
            print(f"  {GREEN}Reminder:{RESET} {tip}")

        # Copy options box
        print()
        print(f"  {GREEN}{'=' * 49}")
        print(f"    COPY OPTIONS")
        print(f"  {'=' * 49}{RESET}")
        print()
        print(f"  {YELLOW}[1]{RESET} Copy code number  {DIM}({code}){RESET}")
        print(f"  {YELLOW}[2]{RESET} Copy title         {DIM}({name[:30]}{'...' if len(name) > 30 else ''}){RESET}")
        print(f"  {YELLOW}[3]{RESET} Copy description   {DIM}(full text){RESET}")
        print(f"  {YELLOW}[M]{RESET} {back_label}")
        print()

        choice = input(f"  {YELLOW}Choose option: {RESET}").strip().upper()

        if choice == "1":
            print(f"\n  {_try_copy(code)}")
            pause()
        elif choice == "2":
            print(f"\n  {_try_copy(name)}")
            pause()
        elif choice == "3":
            print(f"\n  {_try_copy(desc)}")
            pause()
        elif choice in ("M", "B", "Q", "0"):
            return
        else:
            print(f"\n  {RED}Enter 1, 2, 3, or M.{RESET}")
            pause()


def caljobs_detail(entry):
    """Show code detail from search/browse (uses 'Back' label)."""
    show_code_detail(entry, back_label="Back")


def caljobs_search(db):
    clear_screen()
    print_header("Search CalJOBS Codes")
    query = input(f"  {YELLOW}Enter keyword(s): {RESET}").strip().lower()
    if not query:
        print(f"\n  {RED}No keyword entered.{RESET}")
        pause()
        return

    terms = query.split()
    scored = []
    for entry in db["codes"]:
        s = score_caljobs_entry(terms, entry)
        if s > 0:
            scored.append((s, entry))

    scored.sort(key=lambda x: (-x[0], x[1]["code"]))
    results = [item[1] for item in scored]

    def render(i, e, star=" "):
        cat_short = e["category"][:20]
        print(f"  {star}{YELLOW}[{i:>2}]{RESET}  {CYAN}{e['code']:<8}{RESET}{WHITE}{e['name']:<30}{RESET} {DIM}{cat_short}{RESET}")

    ranked_search_results(results, f'CalJOBS Search: "{query}"', render, caljobs_detail)


def caljobs_browse(db):
    clear_screen()
    print_header("Browse CalJOBS by Category")
    categories = db["metadata"]["categories"]
    cat_counts = {}
    for entry in db["codes"]:
        cat = entry["category"]
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    for i, cat in enumerate(categories, 1):
        count = cat_counts.get(cat, 0)
        print(f"  {YELLOW}[{i:>2}]{RESET}  {WHITE}{cat}{RESET} {DIM}({count}){RESET}")

    print(f"\n  {YELLOW}[ 0]{RESET}  Go back\n")

    while True:
        choice = input(f"  {YELLOW}Select a category: {RESET}").strip()
        if choice == "0":
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(categories):
                selected = categories[idx]
                codes = [e for e in db["codes"] if e["category"] == selected]

                def render(i, e):
                    print(f"  {YELLOW}[{i:>2}]{RESET}  {CYAN}{e['code']:<8}{RESET}{WHITE}{e['name']}{RESET}")

                paginated_list(codes, selected, render, caljobs_detail)
                return
            else:
                print(f"  {RED}Enter 1-{len(categories)}.{RESET}")
        except ValueError:
            print(f"  {RED}Enter a valid number.{RESET}")


def caljobs_lookup(db):
    clear_screen()
    print_header("CalJOBS Code Lookup")
    print(f"  {DIM}Examples: E20, E03, 181, E92{RESET}\n")
    query = input(f"  {YELLOW}Enter code: {RESET}").strip().upper()
    if not query:
        return

    for entry in db["codes"]:
        if entry["code"].upper() == query:
            caljobs_detail(entry)
            return

    print(f"\n  {RED}Code \"{query}\" not found.{RESET}")
    print(f"  {DIM}Include the prefix (e.g., E20 not 20).{RESET}")
    pause()


def caljobs_quick(db):
    def render(i, e):
        print(f"  {YELLOW}[{i:>2}]{RESET}  {CYAN}{e['code']:<8}{RESET}{WHITE}{e['name']}{RESET}")
    paginated_list(db["codes"], "All CalJOBS Codes", render, caljobs_detail)


def caljobs_menu(db):
    while True:
        clear_screen()
        total = len(db["codes"])
        cats = len(db["metadata"]["categories"])
        print_header("CalJOBS Activity Codes")
        print(f"  {DIM}{total} codes across {cats} categories{RESET}\n")
        print(f"  {YELLOW}[1]{RESET}  Search by keyword")
        print(f"  {YELLOW}[2]{RESET}  Browse by category")
        print(f"  {YELLOW}[3]{RESET}  Look up by code number")
        print(f"  {YELLOW}[4]{RESET}  Show all codes")
        print(f"  {YELLOW}[0]{RESET}  Back to main menu\n")

        choice = input(f"  {YELLOW}Choose (0-4): {RESET}").strip()
        if   choice == "1": caljobs_search(db)
        elif choice == "2": caljobs_browse(db)
        elif choice == "3": caljobs_lookup(db)
        elif choice == "4": caljobs_quick(db)
        elif choice == "0": return
        else:
            print(f"\n  {RED}Invalid option.{RESET}")
            pause()


# ══════════════════════════════════════════════════════════════════════════════
#  NAICS CODES
# ══════════════════════════════════════════════════════════════════════════════

def naics_detail(entry, naics_db):
    clear_screen()
    code = entry["code"]
    name = entry["name"]
    level_name = entry["level_name"]
    sector_name = entry["sector_name"]

    print_header("NAICS Code Details")
    print(f"  {CYAN}{Style.BRIGHT}>>> {code} <<<{RESET}")
    print()
    print(f"  {WHITE}Title:{RESET}      {name}")
    print(f"  {WHITE}Level:{RESET}      {level_name} ({len(code)}-digit)")
    print(f"  {WHITE}Sector:{RESET}     [{entry['sector_code']}] {sector_name}")

    # Show hierarchy path
    print(f"\n  {WHITE}Hierarchy:{RESET}")
    path_codes = []
    for length in range(2, len(code) + 1):
        prefix = code[:length]
        match = next((c for c in naics_db["codes"] if c["code"] == prefix), None)
        if match:
            path_codes.append(match)

    for p in path_codes:
        indent = "  " * (p["level"] - 1)
        marker = " >>>" if p["code"] == code else ""
        color = CYAN if p["code"] == code else DIM
        print(f"    {color}{indent}{p['code']}  {p['name']}{marker}{RESET}")

    # Show children (next level down)
    children = [c for c in naics_db["codes"]
                if c.get("parent_code") == code and c["code"] != code]
    if children:
        print(f"\n  {WHITE}Sub-categories ({len(children)}):{RESET}")
        for ch in children[:15]:
            print(f"    {CYAN}{ch['code']:<8}{RESET}{ch['name']}")
        if len(children) > 15:
            print(f"    {DIM}... and {len(children) - 15} more{RESET}")

    # Show related codes (same parent)
    parent = entry.get("parent_code")
    if parent:
        siblings = [c for c in naics_db["codes"]
                    if c.get("parent_code") == parent and c["code"] != code]
        if siblings:
            print(f"\n  {WHITE}Related codes (same group):{RESET}")
            for sib in siblings[:10]:
                print(f"    {DIM}{sib['code']:<8}{sib['name']}{RESET}")
            if len(siblings) > 10:
                print(f"    {DIM}... and {len(siblings) - 10} more{RESET}")

    print()
    print_divider()

    detail_text = (
        f"NAICS Code: {code}\nTitle: {name}\n"
        f"Level: {level_name}\nSector: [{entry['sector_code']}] {sector_name}"
    )
    copy_or_save(detail_text, f"NAICS_{code}")


def naics_search(naics_db):
    clear_screen()
    print_header("Search NAICS Codes")
    print(f"  {DIM}Fuzzy matching enabled - typos OK!{RESET}")
    print(f"  {DIM}Examples: restaurant, software, plumbing, trucking{RESET}\n")
    query = input(f"  {YELLOW}Enter search term: {RESET}").strip()
    if not query:
        return

    query_lower = query.lower()
    scored = []

    for entry in naics_db["codes"]:
        name_lower = entry["name"].lower()

        # Exact substring match gets highest priority
        if query_lower in name_lower:
            score = 200 + (100 if name_lower.startswith(query_lower) else 0)
            # Whole-word bonus
            if re.search(r'\b' + re.escape(query_lower) + r'\b', name_lower):
                score += 50
        else:
            # Fuzzy match on name
            score = max(
                fuzz.token_set_ratio(query_lower, name_lower),
                fuzz.partial_ratio(query_lower, name_lower),
            )

        if score >= 60:
            scored.append((score, entry))

    scored.sort(key=lambda x: (-x[0], x[1]["code"]))
    results = [s[1] for s in scored[:50]]

    def render(i, e, star=" "):
        level_tag = f"{DIM}[{e['level_name'][:3]}]{RESET}"
        print(f"  {star}{YELLOW}[{i:>2}]{RESET}  {CYAN}{e['code']:<8}{RESET}{WHITE}{e['name']:<30}{RESET} {level_tag}")

    ranked_search_results(
        results,
        f'NAICS Search: "{query}"',
        render,
        lambda e: naics_detail(e, naics_db),
    )


def naics_browse_sectors(naics_db):
    clear_screen()
    print_header("NAICS Sectors")

    sectors = naics_db["sectors"]
    for i, s in enumerate(sectors, 1):
        print(f"  {YELLOW}[{i:>2}]{RESET}  {CYAN}{s['code']:>5}{RESET}  {WHITE}{s['name']}{RESET} {DIM}({s['code_count']}){RESET}")

    print(f"\n  {YELLOW}[ 0]{RESET}  Go back\n")

    while True:
        choice = input(f"  {YELLOW}Select a sector: {RESET}").strip()
        if choice == "0":
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(sectors):
                sector = sectors[idx]
                naics_drill_down(naics_db, sector)
                return
            else:
                print(f"  {RED}Enter 1-{len(sectors)}.{RESET}")
        except ValueError:
            print(f"  {RED}Enter a valid number.{RESET}")


def naics_drill_down(naics_db, sector):
    """Drill down: sector -> subsectors -> industry groups -> codes."""
    prefixes = sector.get("prefixes", [sector["code"]])

    # Start at subsector level (3-digit)
    current_level = 3
    current_parent_prefixes = prefixes
    breadcrumb = [sector["name"]]

    while True:
        # Find codes at current level whose sector_code matches
        codes_at_level = [
            c for c in naics_db["codes"]
            if c["level"] == current_level
            and c["sector_code"] in prefixes
            and (current_level == 3 or c.get("parent_code") in current_parent_prefixes)
        ]

        if not codes_at_level:
            # If no codes at this level, show the leaf-level entries
            leaf_codes = [
                c for c in naics_db["codes"]
                if c["sector_code"] in prefixes
                and any(c["code"].startswith(p) for p in current_parent_prefixes)
                and c["code"] not in current_parent_prefixes
            ]
            if leaf_codes:
                title = f"{' > '.join(breadcrumb)}"

                def render(i, e):
                    print(f"  {YELLOW}[{i:>2}]{RESET}  {CYAN}{e['code']:<8}{RESET}{WHITE}{e['name']}{RESET}")

                paginated_list(
                    leaf_codes, title, render,
                    lambda e: naics_detail(e, naics_db),
                )
            return

        clear_screen()
        level_names = {3: "Subsectors", 4: "Industry Groups", 5: "Industries", 6: "National Industries"}
        level_label = level_names.get(current_level, "Codes")
        title = f"{' > '.join(breadcrumb)}"
        print_header(title)
        print(f"  {DIM}{level_label}  |  {len(codes_at_level)} entries{RESET}\n")

        for i, c in enumerate(codes_at_level, 1):
            child_count = sum(
                1 for x in naics_db["codes"]
                if x.get("parent_code") == c["code"]
            )
            suffix = f" {DIM}({child_count}){RESET}" if child_count > 0 else ""
            print(f"  {YELLOW}[{i:>2}]{RESET}  {CYAN}{c['code']:<8}{RESET}{WHITE}{c['name']}{RESET}{suffix}")

        print(f"\n  {YELLOW}[ 0]{RESET}  Go back\n")

        choice = input(f"  {YELLOW}Select to drill down, or 0: {RESET}").strip()
        if choice == "0":
            return

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(codes_at_level):
                selected = codes_at_level[idx]

                # Check if this has children
                has_children = any(
                    c.get("parent_code") == selected["code"]
                    for c in naics_db["codes"]
                )
                if has_children:
                    breadcrumb.append(f"{selected['code']} {selected['name']}")
                    current_parent_prefixes = [selected["code"]]
                    current_level += 1
                else:
                    naics_detail(selected, naics_db)
                    return
            else:
                print(f"  {RED}Enter 1-{len(codes_at_level)}.{RESET}")
                pause()
        except ValueError:
            print(f"  {RED}Enter a valid number.{RESET}")
            pause()


def naics_lookup(naics_db):
    clear_screen()
    print_header("NAICS Code Lookup")
    print(f"  {DIM}Enter a 2-6 digit NAICS code (e.g., 722511, 54, 3254){RESET}\n")
    query = input(f"  {YELLOW}Enter NAICS code: {RESET}").strip()
    if not query:
        return

    match = next((c for c in naics_db["codes"] if c["code"] == query), None)
    if match:
        naics_detail(match, naics_db)
    else:
        # Try partial match
        partials = [c for c in naics_db["codes"] if c["code"].startswith(query)]
        if partials:
            print(f"\n  {YELLOW}Exact code \"{query}\" not found, but {len(partials)} codes start with it:{RESET}\n")

            def render(i, e):
                print(f"  {YELLOW}[{i:>2}]{RESET}  {CYAN}{e['code']:<8}{RESET}{WHITE}{e['name']}{RESET}")

            paginated_list(
                partials[:50],
                f'Codes starting with "{query}"',
                render,
                lambda e: naics_detail(e, naics_db),
            )
        else:
            print(f"\n  {RED}No NAICS code found matching \"{query}\".{RESET}")
            pause()


def naics_menu(naics_db):
    while True:
        clear_screen()
        total = naics_db["metadata"]["total_codes"]
        sectors = naics_db["metadata"]["sector_count"]
        print_header("NAICS Industry Codes")
        print(f"  {DIM}{total:,} codes across {sectors} sectors{RESET}\n")
        print(f"  {YELLOW}[1]{RESET}  Search by keyword {DIM}(fuzzy matching){RESET}")
        print(f"  {YELLOW}[2]{RESET}  Browse by sector {DIM}(drill-down){RESET}")
        print(f"  {YELLOW}[3]{RESET}  Look up by NAICS code")
        print(f"  {YELLOW}[0]{RESET}  Back to main menu\n")

        choice = input(f"  {YELLOW}Choose (0-3): {RESET}").strip()
        if   choice == "1": naics_search(naics_db)
        elif choice == "2": naics_browse_sectors(naics_db)
        elif choice == "3": naics_lookup(naics_db)
        elif choice == "0": return
        else:
            print(f"\n  {RED}Invalid option.{RESET}")
            pause()


# ══════════════════════════════════════════════════════════════════════════════
#  AI-GUIDED WIZARD
# ══════════════════════════════════════════════════════════════════════════════

def wizard_generate_template(result, naics_code=None):
    """Generate a fill-in-the-blank case note template."""
    codes_str = ", ".join(result["codes"])
    today = datetime.now().strftime("%m/%d/%Y")

    template = f"Date: {today}\n"
    template += "Staff: [YOUR NAME]\n"
    template += f"Activity Code(s): {codes_str}\n"
    if naics_code:
        template += f"NAICS: {naics_code}\n"
    template += "\nCase Note:\n"
    template += f"BSR [visited/contacted] [EMPLOYER NAME] regarding {result['description'].rstrip('.')}\n"
    template += "[ADDITIONAL DETAILS]\n"
    template += "\nNext Steps:\n"
    template += "- [FOLLOW-UP ACTION]\n"
    template += "- [TIMELINE]\n"

    return template


def wizard_show_result(result, caljobs_db, naics_db):
    """Display recommended codes and offer actions."""
    naics_code = None

    while True:
        clear_screen()
        print_header("Wizard Recommendation")

        print(f"  {WHITE}Recommended Code(s):{RESET}\n")
        for code_str in result["codes"]:
            # Look up code details
            entry = next((e for e in caljobs_db["codes"] if e["code"] == code_str), None)
            if entry:
                print(f"    {CYAN}{code_str:<8}{RESET}{WHITE}{entry['name']}{RESET}")
                print(f"    {DIM}{entry['category']}{RESET}")
            else:
                print(f"    {CYAN}{code_str}{RESET}")
            print()

        print(f"  {WHITE}Situation:{RESET}")
        word_wrap(result["description"])
        print()

        if result.get("naics_hint"):
            print(f"  {DIM}Tip: {result['naics_hint']}{RESET}")
            print()

        if naics_code:
            print(f"  {GREEN}NAICS selected: {naics_code}{RESET}\n")

        print_divider()

        # Validation prompt
        print(f"\n  {YELLOW}Does this match your situation? [Y/N]{RESET}")
        confirm = input(f"  {YELLOW}> {RESET}").strip().upper()

        if confirm == "N":
            print(f"\n  {YELLOW}[R]{RESET} Refine (go back one step)")
            print(f"  {YELLOW}[S]{RESET} Start over")
            refine = input(f"\n  {YELLOW}Choose: {RESET}").strip().upper()
            if refine == "R":
                return "REFINE"
            else:
                return "RESTART"

        if confirm != "Y":
            print(f"  {RED}Please enter Y or N.{RESET}")
            pause()
            continue

        # User confirmed — show action options
        save_recent(result)

        while True:
            clear_screen()
            print_header("Wizard Result Actions")

            codes_str = ", ".join(result["codes"])
            print(f"  {WHITE}Code(s):{RESET} {CYAN}{codes_str}{RESET}")
            print(f"  {WHITE}Situation:{RESET} {result['description']}")
            if naics_code:
                print(f"  {WHITE}NAICS:{RESET} {naics_code}")
            print()
            print_divider()
            print()

            print(f"  {YELLOW}[C]{RESET} Copy code(s) to clipboard")
            print(f"  {YELLOW}[D]{RESET} View code details")
            if naics_db and result.get("naics_hint"):
                print(f"  {YELLOW}[N]{RESET} Search NAICS for employer industry")
            print(f"  {YELLOW}[T]{RESET} Generate case note template")
            print(f"  {YELLOW}[0]{RESET} Done (back to main menu)\n")

            action = input(f"  {YELLOW}Choose: {RESET}").strip().upper()
            if action == "0":
                return "DONE"
            elif action == "C":
                try:
                    pyperclip.copy(codes_str)
                    print(f"\n  {GREEN}Copied: {codes_str}{RESET}")
                except pyperclip.PyperclipException:
                    print(f"\n  {RED}Clipboard not available.{RESET}")
                pause()
            elif action == "D":
                for code_str in result["codes"]:
                    entry = next((e for e in caljobs_db["codes"] if e["code"] == code_str), None)
                    if entry:
                        caljobs_detail(entry)
            elif action == "N" and naics_db and result.get("naics_hint"):
                naics_search(naics_db)
            elif action == "T":
                template = wizard_generate_template(result, naics_code)
                clear_screen()
                print_header("Case Note Template")
                print()
                for line in template.split("\n"):
                    print(f"    {line}")
                print()
                print_divider()
                copy_or_save(template, "case_note_template")
            else:
                print(f"  {RED}Invalid option.{RESET}")
                pause()


def wizard_run(caljobs_db, naics_db):
    """Run the AI-guided wizard with navigation."""

    while True:  # outer loop for restarts
        history = []  # stack of node keys for back navigation
        current = "root"

        while True:
            node = WIZARD_TREE[current]
            clear_screen()
            print_header("AI-Guided Wizard")

            # Breadcrumbs
            if history:
                crumbs = " > ".join(history + [current])
                print(f"  {DIM}{crumbs}{RESET}\n")

            # Quick Select (only at root)
            if current == "root":
                recent = load_recent()
                print(f"  {MAG}Quick Select:{RESET}")
                for key, scenario in QUICK_SCENARIOS.items():
                    print(f"    {YELLOW}[{key}]{RESET}  {scenario['label']}")
                if recent:
                    print(f"    {YELLOW}[R]{RESET}  Recently used")
                print()
                print_divider()
                print()

            # Question
            print(f"  {WHITE}{node['question']}{RESET}\n")

            for i, opt in enumerate(node["options"], 1):
                print(f"  {YELLOW}[{i}]{RESET}  {opt['label']}")

            print()
            if history:
                print(f"  {YELLOW}[B]{RESET}  Back")
            print(f"  {YELLOW}[0]{RESET}  Exit wizard")
            print(f"  {DIM}Type ? or help for an example{RESET}\n")

            choice = input(f"  {YELLOW}> {RESET}").strip().upper()

            if choice in ("?", "HELP"):
                if node.get("help"):
                    print(f"\n  {DIM}{node['help']}{RESET}")
                else:
                    print(f"\n  {DIM}No help available for this step.{RESET}")
                pause()
                continue

            if choice == "0":
                return

            if choice == "B" and history:
                current = history.pop()
                continue

            # Quick select (root only)
            if current == "root" and choice in QUICK_SCENARIOS:
                scenario = QUICK_SCENARIOS[choice]
                result_action = wizard_show_result(scenario, caljobs_db, naics_db)
                if result_action == "RESTART":
                    break  # break inner loop, outer restarts
                elif result_action == "REFINE":
                    continue  # stay at root
                else:
                    return

            # Recently used (root only)
            if current == "root" and choice == "R":
                recent = load_recent()
                if recent:
                    clear_screen()
                    print_header("Recently Used Codes")
                    for i, r in enumerate(recent, 1):
                        codes_str = ", ".join(r["codes"])
                        print(f"  {YELLOW}[{i}]{RESET}  {CYAN}{codes_str:<12}{RESET}{WHITE}{r['description']}{RESET}")
                        print(f"       {DIM}{r['timestamp']}{RESET}")
                        print()
                    print(f"  {YELLOW}[0]{RESET}  Back\n")
                    rchoice = input(f"  {YELLOW}Select: {RESET}").strip()
                    if rchoice == "0":
                        continue
                    try:
                        ridx = int(rchoice) - 1
                        if 0 <= ridx < len(recent):
                            result_action = wizard_show_result(recent[ridx], caljobs_db, naics_db)
                            if result_action == "RESTART":
                                break
                            elif result_action == "REFINE":
                                continue
                            else:
                                return
                    except ValueError:
                        pass
                continue

            # Normal option selection
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(node["options"]):
                    selected = node["options"][idx]
                    if "result" in selected:
                        result_action = wizard_show_result(selected["result"], caljobs_db, naics_db)
                        if result_action == "RESTART":
                            break  # restart wizard
                        elif result_action == "REFINE":
                            continue  # stay at current node (go back one step)
                        else:
                            return
                    elif "next" in selected:
                        history.append(current)
                        current = selected["next"]
                    else:
                        print(f"  {RED}Invalid tree node.{RESET}")
                        pause()
                else:
                    print(f"  {RED}Enter 1-{len(node['options'])}.{RESET}")
                    pause()
            except ValueError:
                print(f"  {RED}Invalid input.{RESET}")
                pause()


# ══════════════════════════════════════════════════════════════════════════════
#  QUICK ACTIONS
# ══════════════════════════════════════════════════════════════════════════════

def find_code(db, code_str):
    """Find a code entry in the database by code number (case-insensitive)."""
    code_upper = code_str.upper()
    for entry in db["codes"]:
        if entry["code"].upper() == code_upper:
            return entry
    return None


def quick_simple(db, code_str, tip, header="QUICK ACTION"):
    """Quick action for a single code lookup with a tip."""
    entry = find_code(db, code_str)
    if not entry:
        print(f"\n  {RED}Code {code_str} not found in database.{RESET}")
        pause()
        return
    show_code_detail(entry, header_title=header, tip=tip, back_label="Main Menu")


def quick_q1(db):
    """Q1: Workshop completion incentive - code 183."""
    quick_simple(db, "183",
                 tip="$300 for completing all 6 INVEST workshops + 5 GetYourEdge modules",
                 header="WORKSHOP COMPLETION INCENTIVE")


def quick_q2(db):
    """Q2: Transportation assistance - code 181."""
    quick_simple(db, "181",
                 tip="TAP card for commute to AJCC, job search, training",
                 header="TRANSPORTATION ASSISTANCE")


def quick_q3(db):
    """Q3: Work clothing / tools - code 188."""
    quick_simple(db, "188",
                 tip="Use when client needs work attire or tools for employment",
                 header="WORK CLOTHING / TOOLS")


def quick_q4(db):
    """Q4: Employer contact/visit - multi-choice selector."""
    EMPLOYER_CODES = [
        ("E20", "Employer Contact/Visit",
         "General outreach - phone call, email, or in-person visit"),
        ("E22", "Employer Contact - Job Development",
         "Contacting employer specifically to develop a job opportunity for a client"),
        ("E60", "Job Order Placed/Received",
         "Employer has an open position - creating or updating a job order"),
        ("E69", "Employer Provided Information",
         "Gave employer info about services, tax credits, programs"),
        ("E57", "Employer Follow-up",
         "Following up on a previous contact, job order, or placement"),
    ]

    while True:
        clear_screen()
        print()
        print(f"  {GREEN}{'=' * 49}")
        print(f"    EMPLOYER CONTACT / VISIT")
        print(f"  {'=' * 49}{RESET}")
        print()
        print(f"  {WHITE}What best describes your employer interaction?{RESET}")
        print()

        for i, (code, label, desc) in enumerate(EMPLOYER_CODES, 1):
            print(f"  {YELLOW}[{i}]{RESET}  {CYAN}{code:<6}{RESET}{WHITE}{label}{RESET}")
            print(f"        {DIM}{desc}{RESET}")
            print()

        print(f"  {YELLOW}[0]{RESET}  Back to main menu")
        print()

        choice = input(f"  {YELLOW}Choose (0-{len(EMPLOYER_CODES)}): {RESET}").strip()

        if choice == "0":
            return

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(EMPLOYER_CODES):
                code_str = EMPLOYER_CODES[idx][0]
                entry = find_code(db, code_str)
                if entry:
                    show_code_detail(entry,
                                     header_title="EMPLOYER CONTACT / VISIT",
                                     tip=EMPLOYER_CODES[idx][2],
                                     back_label="Back to selection")
                else:
                    print(f"\n  {RED}Code {code_str} not found in database.{RESET}")
                    pause()
            else:
                print(f"\n  {RED}Enter 0-{len(EMPLOYER_CODES)}.{RESET}")
                pause()
        except ValueError:
            print(f"\n  {RED}Invalid input.{RESET}")
            pause()


def quick_q5(db, naics_db):
    """Q5: Training + industry codes - two-step guide."""
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

    while True:
        clear_screen()
        print()
        print(f"  {GREEN}{'=' * 49}")
        print(f"    TRAINING + INDUSTRY CODE GUIDE")
        print(f"  {'=' * 49}{RESET}")
        print()
        print(f"  {WHITE}Step 1: Select the training type{RESET}")
        print()

        for i, (code, label) in enumerate(TRAINING_CODES, 1):
            print(f"  {YELLOW}[{i:>2}]{RESET}  {CYAN}{code:<6}{RESET}{label}")

        print()
        print(f"  {YELLOW}[S]{RESET}   Search for other training codes")
        print(f"  {YELLOW}[0]{RESET}   Back to main menu")
        print()

        choice = input(f"  {YELLOW}Choose: {RESET}").strip().upper()

        if choice == "0":
            return
        elif choice == "S":
            caljobs_search(db)
            continue

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(TRAINING_CODES):
                code_str = TRAINING_CODES[idx][0]
                entry = find_code(db, code_str)
                if entry:
                    show_code_detail(entry,
                                     header_title="TRAINING CODE",
                                     tip="After copying, select the NAICS industry code next",
                                     back_label="Continue to NAICS")
                    # After viewing training code, go to Step 2: NAICS
                    _quick_q5_naics(naics_db)
                else:
                    print(f"\n  {RED}Code {code_str} not found in database.{RESET}")
                    pause()
            else:
                print(f"\n  {RED}Enter 1-{len(TRAINING_CODES)}, S, or 0.{RESET}")
                pause()
        except ValueError:
            print(f"\n  {RED}Invalid input.{RESET}")
            pause()


def _quick_q5_naics(naics_db):
    """Step 2 of Q5: Select NAICS industry code for training."""
    if not naics_db:
        print(f"\n  {RED}NAICS database not available.{RESET}")
        pause()
        return

    COMMON_TRADES = [
        ("2362", "Nonresidential Building Construction"),
        ("2381", "Foundation / Structure Contractors"),
        ("2382", "Building Equipment Contractors"),
        ("3361", "Motor Vehicle Manufacturing"),
        ("4411", "Automobile Dealers"),
        ("4451", "Grocery Stores"),
        ("4841", "General Freight Trucking"),
        ("5415", "Computer Systems Design"),
        ("5613", "Employment Services"),
        ("6211", "Offices of Physicians"),
        ("6216", "Home Health Care Services"),
        ("7225", "Restaurants / Eating Places"),
    ]

    while True:
        clear_screen()
        print()
        print(f"  {GREEN}{'=' * 49}")
        print(f"    STEP 2: SELECT NAICS INDUSTRY CODE")
        print(f"  {'=' * 49}{RESET}")
        print()
        print(f"  {WHITE}Common industries for training placements:{RESET}")
        print()

        for i, (code, label) in enumerate(COMMON_TRADES, 1):
            print(f"  {YELLOW}[{i:>2}]{RESET}  {CYAN}{code:<8}{RESET}{label}")

        print()
        print(f"  {YELLOW}[S]{RESET}   Search NAICS codes")
        print(f"  {YELLOW}[0]{RESET}   Skip / Back")
        print()

        choice = input(f"  {YELLOW}Choose: {RESET}").strip().upper()

        if choice == "0":
            return
        elif choice == "S":
            naics_search(naics_db)
            continue

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(COMMON_TRADES):
                code_str = COMMON_TRADES[idx][0]
                match = next((c for c in naics_db["codes"] if c["code"] == code_str), None)
                if match:
                    naics_detail(match, naics_db)
                else:
                    print(f"\n  {RED}NAICS {code_str} not found.{RESET}")
                    pause()
                return
            else:
                print(f"\n  {RED}Enter 1-{len(COMMON_TRADES)}, S, or 0.{RESET}")
                pause()
        except ValueError:
            print(f"\n  {RED}Invalid input.{RESET}")
            pause()


def quick_q6(db):
    """Q6: New client enrollment - codes 101 + 102."""
    clear_screen()
    print()
    print(f"  {GREEN}{'=' * 49}")
    print(f"    NEW CLIENT ENROLLMENT")
    print(f"  {'=' * 49}{RESET}")
    print()
    print(f"  {WHITE}New client enrollment requires two codes:{RESET}")
    print()
    print(f"    {CYAN}1.{RESET} {WHITE}101{RESET} - Orientation")
    print(f"    {CYAN}2.{RESET} {WHITE}102{RESET} - Initial Assessment")
    print()
    print(f"  {DIM}You'll view each code to copy what you need.{RESET}")
    print()

    input(f"  {YELLOW}Press Enter to view code 101 (Orientation)...{RESET}")

    entry_101 = find_code(db, "101")
    if entry_101:
        show_code_detail(entry_101,
                         header_title="ENROLLMENT STEP 1 OF 2",
                         tip="After copying, press back to continue to code 102",
                         back_label="Continue to code 102")

    entry_102 = find_code(db, "102")
    if entry_102:
        show_code_detail(entry_102,
                         header_title="ENROLLMENT STEP 2 OF 2",
                         tip="This is the second code for new client enrollment",
                         back_label="Done - Main Menu")


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN MENU
# ══════════════════════════════════════════════════════════════════════════════

def main():
    caljobs_db = load_json("codes_database_complete.json") or load_json("codes_database.json")
    naics_db   = load_json("naics_database.json")

    if not caljobs_db and not naics_db:
        print(f"{RED}No databases found. Exiting.{RESET}")
        sys.exit(1)

    while True:
        clear_screen()
        print()
        print(f"{GREEN}{'=' * 60}")
        print(f"       CALJOBS CODE ASSISTANT")
        print(f"{'=' * 60}{RESET}")
        print()
        cj_count = len(caljobs_db["codes"]) if caljobs_db else 0
        na_count = naics_db["metadata"]["total_codes"] if naics_db else 0
        print(f"  {DIM}{cj_count} activity codes  |  {na_count:,} NAICS codes{RESET}\n")

        # Quick Actions
        print(f"  {GREEN}--- Quick Actions ---{RESET}")
        print()
        print(f"  {YELLOW}[Q1]{RESET}  Workshop completion incentive  {DIM}(183){RESET}")
        print(f"  {YELLOW}[Q2]{RESET}  Transportation assistance      {DIM}(181){RESET}")
        print(f"  {YELLOW}[Q3]{RESET}  Work clothing / tools           {DIM}(188){RESET}")
        print(f"  {YELLOW}[Q4]{RESET}  Employer contact / visit        {DIM}(E20, E22, E60...){RESET}")
        print(f"  {YELLOW}[Q5]{RESET}  Training + industry code        {DIM}(training + NAICS){RESET}")
        print(f"  {YELLOW}[Q6]{RESET}  New client enrollment           {DIM}(101 + 102){RESET}")
        print()

        # Full Tools
        print(f"  {GREEN}--- Full Tools ---{RESET}")
        print()
        print(f"  {YELLOW}[7]{RESET}   Full search                    {DIM}(keyword search){RESET}")
        print(f"  {YELLOW}[8]{RESET}   Browse categories")
        print(f"  {YELLOW}[N]{RESET}   NAICS industry codes            {DIM}({na_count:,} codes){RESET}")
        print(f"  {YELLOW}[W]{RESET}   AI-Guided Wizard")
        print(f"  {YELLOW}[9]{RESET}   Exit")
        print()

        choice = input(f"  {YELLOW}Choose an option: {RESET}").strip().upper()

        if choice in ("Q1", "1"):
            if caljobs_db: quick_q1(caljobs_db)
        elif choice in ("Q2", "2"):
            if caljobs_db: quick_q2(caljobs_db)
        elif choice in ("Q3", "3"):
            if caljobs_db: quick_q3(caljobs_db)
        elif choice in ("Q4", "4"):
            if caljobs_db: quick_q4(caljobs_db)
        elif choice in ("Q5", "5"):
            if caljobs_db: quick_q5(caljobs_db, naics_db)
        elif choice in ("Q6", "6"):
            if caljobs_db: quick_q6(caljobs_db)
        elif choice == "7":
            if caljobs_db:
                caljobs_menu(caljobs_db)
        elif choice == "8":
            if caljobs_db:
                caljobs_browse(caljobs_db)
        elif choice == "N":
            if naics_db:
                naics_menu(naics_db)
        elif choice == "W":
            if caljobs_db:
                wizard_run(caljobs_db, naics_db)
            else:
                print(f"\n  {RED}CalJOBS database required for wizard.{RESET}")
                pause()
        elif choice == "9":
            clear_screen()
            print(f"\n  {GREEN}Goodbye!{RESET}\n")
            sys.exit(0)
        else:
            print(f"\n  {RED}Invalid option.{RESET}")
            pause()


if __name__ == "__main__":
    main()
