"""
Parse the official CalJOBS Activity Codes Dictionary (wsd24-05att1.txt)
and build a comprehensive codes_database_complete.json.
"""

import json
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_FILE = os.path.join(os.path.expanduser("~"), "Downloads", "wsd24-05att1.txt")
EXISTING_DB = os.path.join(BASE_DIR, "codes_database.json")
OUTPUT_DB = os.path.join(BASE_DIR, "codes_database_complete.json")


# ─── Category assignment ────────────────────────────────────────────────────

def assign_category(code):
    """Assign a category based on code prefix/range."""
    if code.startswith("E"):
        return "Employer Services"
    if code.startswith("F"):
        return "Follow-Up Activities"

    # YEOP codes
    if code.startswith("6"):
        return "YEOP (Youth Employment Opportunity Program)"

    # Numeric codes
    if code in ("06M",):
        return "Self-Service Activities"

    # Try numeric parse for non-prefix codes
    try:
        num = int(code)
    except ValueError:
        return "Other"

    if 2 <= num <= 97:
        return "Self-Service Activities"
    elif 101 <= num <= 109:
        return "Assessments & Orientation"
    elif 110 <= num <= 126:
        return "Job Search & Referrals"
    elif 130 <= num <= 135:
        return "Career Development & Workshops"
    elif 140 <= num <= 169:
        return "Referrals to Programs"
    elif 179 <= num <= 179:
        return "Job Search & Referrals"
    elif 180 <= num <= 197:
        return "Supportive Services"
    elif 200 <= num <= 227:
        return "Counseling & Career Planning"
    elif 231 <= num <= 245:
        return "TAA (Trade Adjustment Assistance)"
    elif 300 <= num <= 355:
        return "Training & Education"
    elif 400 <= num <= 439:
        return "Youth Services"
    elif 480 <= num <= 494:
        return "Youth Supportive Services"
    elif 500 <= num <= 590:
        return "Job Referrals (System)"
    else:
        return "Other"


# ─── Keyword generation ─────────────────────────────────────────────────────

def generate_keywords(code, name, description, category):
    """Generate searchable keywords from the code entry."""
    keywords = set()

    # Add the code itself
    keywords.add(code)

    # Common keyword patterns from name
    name_lower = name.lower()

    # Extract meaningful words from name (skip very short/common ones)
    stop_words = {
        "a", "an", "the", "and", "or", "of", "to", "in", "for", "with",
        "is", "was", "by", "on", "at", "from", "as", "be", "are", "this",
        "that", "not", "but", "has", "had", "its", "it", "do", "does",
        "their", "them", "they", "who", "which", "such", "may", "can",
        "will", "shall", "must", "should", "would", "could",
    }
    for word in re.findall(r'[a-zA-Z]+', name_lower):
        if len(word) > 2 and word not in stop_words:
            keywords.add(word)

    # Add specific domain keywords based on content
    desc_lower = description.lower()

    keyword_map = {
        "ojt": ["OJT", "on-the-job"],
        "on-the-job": ["OJT", "on-the-job training"],
        "wioa": ["WIOA"],
        "wotc": ["WOTC", "tax credit"],
        "tax credit": ["WOTC", "tax credit"],
        "veteran": ["veteran", "veterans", "JVSG"],
        "youth": ["youth"],
        "resume": ["resume"],
        "job fair": ["job fair", "hiring event"],
        "ui ": ["UI", "unemployment insurance"],
        "unemployment": ["UI", "unemployment"],
        "etpl": ["ETPL", "training provider"],
        "apprenticeship": ["apprenticeship"],
        "supportive service": ["supportive service"],
        "transportation": ["transportation", "bus", "transit"],
        "child": ["childcare", "dependent care"],
        "housing": ["housing", "shelter"],
        "medical": ["medical", "health"],
        "counseling": ["counseling", "guidance"],
        "assessment": ["assessment", "testing"],
        "referral": ["referral"],
        "employer": ["employer"],
        "training": ["training"],
        "education": ["education"],
        "ged": ["GED", "high school equivalency"],
        "iep": ["IEP", "individual employment plan"],
        "rapid response": ["rapid response", "layoff"],
        "layoff": ["layoff", "closure", "rapid response"],
        "bonding": ["bonding", "fidelity bond"],
        "etp": ["ETP", "Employment Training Panel"],
        "calworks": ["CalWORKs", "welfare"],
        "calfresh": ["CalFresh", "SNAP"],
        "nfjp": ["NFJP", "farmworker"],
        "taa": ["TAA", "trade adjustment"],
        "yeop": ["YEOP", "youth employment"],
        "resea": ["RESEA", "reemployment"],
        "financial literacy": ["financial literacy", "budgeting"],
        "ell": ["ELL", "English language learner"],
        "internship": ["internship"],
        "mentoring": ["mentoring", "mentor"],
        "work experience": ["work experience"],
        "job shadowing": ["job shadowing"],
        "career pathway": ["career pathway"],
    }

    for trigger, kws in keyword_map.items():
        if trigger in desc_lower or trigger in name_lower:
            keywords.update(kws)

    return sorted(keywords)


# ─── When-to-use generation ─────────────────────────────────────────────────

def generate_when_to_use(code, name, description, category):
    """Generate key scenarios for when to use this code."""
    scenarios = []
    name_lower = name.lower()
    desc_lower = description.lower()

    if "self-service" in name_lower or "system generated" in desc_lower:
        scenarios.append("System-generated when participant performs self-service activity in CalJOBS")

    if "staff provided" in desc_lower or "staff assisted" in desc_lower:
        scenarios.append("Staff-assisted service requiring documentation")

    if "staff referred" in desc_lower:
        scenarios.append("When making a referral on behalf of a participant")

    if "participant received" in desc_lower:
        scenarios.append("When providing a direct service to a participant")

    if "enrolled" in desc_lower:
        scenarios.append("When enrolling a participant in a program or training")

    if "supportive service" in name_lower:
        scenarios.append("Must be provided in conjunction with a career service or training")

    if code.startswith("E"):
        scenarios.append("Employer-facing activity for BSR case notes")

    if code.startswith("F"):
        scenarios.append("Post-exit follow-up activity")

    if not scenarios:
        scenarios.append("See description for applicable situations")

    return scenarios


# ─── Requirements extraction ────────────────────────────────────────────────

def extract_requirements(description):
    """Extract prerequisites or requirements mentioned in the description."""
    reqs = []
    desc_lower = description.lower()

    if "case note" in desc_lower and ("must" in desc_lower or "requires" in desc_lower):
        reqs.append("Case note documentation required")

    if "must be provided in conjunction" in desc_lower:
        reqs.append("Must be concurrent with a career service or training service")

    if "service dates" in desc_lower:
        reqs.append("Service dates must fall within career/training service dates")

    if "must be used in conjunction" in desc_lower:
        # Try to extract the related codes
        reqs.append("Must be used with specific companion codes (see description)")

    if "etpl" in desc_lower:
        reqs.append("Training provider must be on CA ETPL")

    if "ita" in desc_lower:
        reqs.append("Requires Individual Training Account (ITA)")

    if "onet code" in desc_lower:
        reqs.append("Must include ONET occupational code")

    if "training contract" in desc_lower:
        reqs.append("Requires a training contract")

    if "local area policy" in desc_lower or "local board" in desc_lower:
        reqs.append("Subject to Local Area/Board policy")

    return reqs


# ─── Related codes extraction ───────────────────────────────────────────────

def extract_related_codes(description):
    """Extract references to other activity codes mentioned in the description."""
    related = []
    # Find patterns like (123), (E03), code 123, activity 123
    patterns = re.findall(r'\((\d{2,3}|E\d{2}|F\d{2})\)', description)
    for p in patterns:
        if p not in related:
            related.append(p)

    # Also find "code NNN" references
    code_refs = re.findall(r'(?:code|activity)\s+(\d{2,3}|E\d{2}|F\d{2})', description, re.IGNORECASE)
    for c in code_refs:
        if c not in related:
            related.append(c)

    return related


# ─── Main parser ────────────────────────────────────────────────────────────

def parse_document(filepath):
    """Parse the official CalJOBS Activity Codes Dictionary."""
    with open(filepath, "r", encoding="cp1252") as f:
        text = f.read()

    # Split into lines
    lines = text.split("\n")

    codes = []
    i = 0
    total_lines = len(lines)

    # Pattern for code lines: starts with a code like 002, 06M, E01, F01
    code_pattern = re.compile(r'^(0[0-9][0-9A-Z]|[1-9]\d{1,2}|E\d{2}|F\d{2})\s*$')

    while i < total_lines:
        line = lines[i].strip()

        # Skip table-of-contents lines, headers, page numbers, etc.
        if not line:
            i += 1
            continue

        match = code_pattern.match(line)
        if match:
            code = match.group(1)
            i += 1

            # Next non-empty line is the name
            name = ""
            while i < total_lines:
                next_line = lines[i].strip()
                if next_line:
                    name = next_line
                    i += 1
                    break
                i += 1

            # Check if name continues to next line (some names span 2 lines)
            # Only continue name if the line looks like a title fragment, not a description
            while i < total_lines:
                next_line = lines[i].strip()
                if not next_line:
                    i += 1
                    continue

                # If it's a new code, stop
                if code_pattern.match(next_line):
                    break

                # Lines that look like descriptions (contain action verbs) are NOT name continuations
                desc_starters = (
                    "An ", "A ", "The ", "Staff ", "This ", "Under ", "After ", "At ",
                    "TAA ", "YEOP ", "Local ", "Agent ",
                )
                desc_verbs = (
                    "provided", "received", "assisted", "conducted", "referred",
                    "enrolled", "attended", "tested", "contacted", "developed",
                    "determined", "informed", "coordinated", "verified", "processed",
                    "completed", "submitted", "established", "suspended", "tracked",
                    "participated", "used", "filed", "took part",
                )
                next_lower = next_line.lower()
                is_description = (
                    next_line.startswith(desc_starters) or
                    any(v in next_lower for v in desc_verbs) or
                    len(next_line) > 85
                )
                if is_description:
                    break

                # It's probably a name continuation (e.g., long official title)
                name += " " + next_line
                i += 1
                break  # Only allow one continuation line

            # Collect description lines until next code or section break
            desc_lines = []
            while i < total_lines:
                next_line = lines[i].strip()

                # Check if this is a new code
                if code_pattern.match(next_line):
                    break

                # Check for section headers/breaks we should skip
                if next_line in ("?", "Participant Activity Codes", "Follow-Up Activity Codes",
                                "Employer Activity Codes", "Contents"):
                    i += 1
                    continue

                # Skip page numbers and header repeats
                if next_line.startswith("WSD24-05") or next_line.startswith("Activity Code"):
                    i += 1
                    continue
                if next_line == "Activity Code Name and Definition":
                    i += 1
                    continue

                # Skip table of contents lines
                if re.match(r'^\d{3}\s*-\s*\d{3}\s+\d+$', next_line):
                    i += 1
                    continue

                if next_line:
                    desc_lines.append(next_line)

                i += 1

            description = " ".join(desc_lines)
            # Clean up description
            description = re.sub(r'\s+', ' ', description).strip()

            # Normalize Unicode special chars to ASCII for terminal compatibility
            for s in (description, name):
                pass  # done below
            def clean_text(s):
                s = s.replace("\u2019", "'").replace("\u2018", "'")  # smart quotes
                s = s.replace("\u201c", '"').replace("\u201d", '"')  # double quotes
                s = s.replace("\u2013", "-").replace("\u2014", "-")  # en/em dash
                s = s.replace("\u00e2\u0080\u0099", "'")  # mangled UTF-8
                return s
            description = clean_text(description)
            name = clean_text(name)

            # Post-processing: fix names that accidentally got description appended
            # If name contains a description-like sentence, split it
            # Look for pattern: "Real Name Staff did something..." or "Real Name An individual..."
            split_patterns = [
                r'^(.+?)\s+(Staff[\s\W])',
                r'^(.+?)\s+(An individual\s)',
                r'^(.+?)\s+(A participant\s)',
                r'^(.+?)\s+(A Youth\s)',
                r'^(.+?)\s+(A YEOP\s)',
                r'^(.+?)\s+(A UI\s)',
                r'^(.+?)\s+(The participant\s)',
                r'^(.+?)\s+(After\s)',
            ]
            for pat in split_patterns:
                m = re.match(pat, name, re.IGNORECASE)
                if m and len(m.group(1)) >= 8:
                    real_name = m.group(1).strip()
                    extra_desc = m.group(2) + name[m.end(2):]
                    name = real_name
                    if description:
                        description = extra_desc.strip() + " " + description
                    else:
                        description = extra_desc.strip()
                    break

            if name and code:
                codes.append({
                    "code": code,
                    "name": name,
                    "description": description,
                })

        else:
            i += 1

    return codes


def merge_with_existing(parsed_codes, existing_db):
    """Merge parsed codes with existing database, preserving existing data where better."""
    existing_map = {}
    if existing_db:
        for entry in existing_db.get("codes", []):
            existing_map[entry["code"]] = entry

    final_codes = []
    new_count = 0
    updated_count = 0
    kept_count = 0

    seen_codes = set()

    for parsed in parsed_codes:
        code = parsed["code"]
        if code in seen_codes:
            continue
        seen_codes.add(code)

        category = assign_category(code)
        description = parsed["description"]
        name = parsed["name"]

        if code in existing_map:
            existing = existing_map[code]
            # Use the official name and description from the new document
            # since it's the authoritative source
            if len(description) > len(existing.get("description", "")):
                updated_count += 1
            else:
                # Keep existing description if it's longer/better
                description = existing.get("description", description)
                kept_count += 1

            # Keep existing keywords and merge with generated ones
            existing_kw = set(existing.get("keywords", []))
            new_kw = set(generate_keywords(code, name, description, category))
            merged_kw = sorted(existing_kw | new_kw)
        else:
            new_count += 1
            merged_kw = generate_keywords(code, name, description, category)

        entry = {
            "code": code,
            "name": name,
            "description": description,
            "category": category,
            "keywords": merged_kw,
            "when_to_use": generate_when_to_use(code, name, description, category),
            "requirements": extract_requirements(description),
            "related_codes": extract_related_codes(description),
        }
        final_codes.append(entry)

    # Check for codes in existing DB but NOT in the parsed document
    for code, existing in existing_map.items():
        if code not in seen_codes:
            category = assign_category(code)
            entry = {
                "code": code,
                "name": existing["name"],
                "description": existing["description"],
                "category": category,
                "keywords": existing.get("keywords", []),
                "when_to_use": generate_when_to_use(code, existing["name"], existing["description"], category),
                "requirements": extract_requirements(existing["description"]),
                "related_codes": extract_related_codes(existing["description"]),
            }
            final_codes.append(entry)
            kept_count += 1

    return final_codes, new_count, updated_count, kept_count


def sort_codes(codes):
    """Sort codes: numeric first (by number), then E-codes, then F-codes."""
    def sort_key(entry):
        code = entry["code"]
        if code.startswith("E"):
            return (2, int(code[1:]))
        elif code.startswith("F"):
            return (3, int(code[1:]))
        elif code == "06M":
            return (0, 6.5)
        else:
            try:
                return (0 if int(code) < 600 else 1, int(code))
            except ValueError:
                return (4, 0)
    return sorted(codes, key=sort_key)


def main():
    print("=" * 60)
    print("  CalJOBS Complete Database Builder")
    print("=" * 60)
    print()

    # Load existing database
    existing_db = None
    existing_count = 0
    if os.path.exists(EXISTING_DB):
        with open(EXISTING_DB, "r", encoding="utf-8") as f:
            existing_db = json.load(f)
            existing_count = len(existing_db.get("codes", []))
        print(f"  Existing database: {existing_count} codes")
    else:
        print("  No existing database found")

    # Parse the official document
    print(f"  Parsing: {SOURCE_FILE}")
    parsed = parse_document(SOURCE_FILE)
    print(f"  Parsed from document: {len(parsed)} codes")

    # Merge
    merged, new_count, updated_count, kept_count = merge_with_existing(parsed, existing_db)
    merged = sort_codes(merged)

    # Build categories list
    categories = sorted(set(e["category"] for e in merged))
    cat_counts = {}
    for e in merged:
        cat = e["category"]
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    # Build the output database
    db = {
        "metadata": {
            "title": "CalJOBS Activity Codes - Complete Official Dictionary",
            "source": "WSD24-05 Attachment 1 - CalJOBS Activity Codes Dictionary",
            "version": "2.0",
            "created": "2026-02-04",
            "total_codes": len(merged),
            "categories": categories,
        },
        "codes": merged,
    }

    # Write output
    with open(OUTPUT_DB, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

    print()
    print("=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print()
    print(f"  Old database:        {existing_count} codes")
    print(f"  Official document:   {len(parsed)} codes parsed")
    print(f"  New database:        {len(merged)} total codes")
    print()
    print(f"  New codes added:     {new_count}")
    print(f"  Codes updated:       {updated_count}")
    print(f"  Codes kept as-is:    {kept_count}")
    print()
    print("  Categories:")
    for cat in categories:
        print(f"    {cat_counts[cat]:>4}  {cat}")
    print()
    print(f"  Output: {OUTPUT_DB}")
    print()

    # Show sample of new codes
    if new_count > 0:
        print("  Sample new codes:")
        count = 0
        for e in merged:
            if existing_db and e["code"] not in {x["code"] for x in existing_db.get("codes", [])}:
                print(f"    {e['code']:<6} {e['name']}")
                count += 1
                if count >= 20:
                    remaining = new_count - 20
                    if remaining > 0:
                        print(f"    ... and {remaining} more")
                    break
        print()


if __name__ == "__main__":
    main()
