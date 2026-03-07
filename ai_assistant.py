"""
CalJOBS Navigator — AI Assistant (RAG-Powered)
================================================
Replaces the old build_system_prompt() approach that stuffed all 326 codes
into the system prompt. Instead, retrieves only the relevant knowledge
chunks for each query, producing more accurate and more capable responses.

The old approach:
    System prompt = "Here are ALL 326 codes: [giant table]"
    Problem: Works for codes, but can't scale to navigation, procedures, etc.

The new approach:
    1. User asks a question
    2. We retrieve the 6-8 most relevant chunks from ChromaDB
    3. Those chunks become the context in the prompt
    4. Claude reasons over ONLY the relevant information
    
    Benefits:
    - Can handle unlimited knowledge (not limited by context window)
    - More accurate (less noise from irrelevant codes)
    - Supports ALL domains (codes, case notes, navigation, procedures)
    - Answers include source attribution

Usage in web_app.py:
    from ai_assistant import get_ai_response, build_rag_system_prompt
"""

from knowledge_base import retrieve_for_prompt, get_collection


# ─── System Prompt (base — always included) ──────────────────────────────────

BASE_SYSTEM_PROMPT = """You are the CalJOBS Navigator — an expert AI assistant for California's 
America's Job Centers of California (AJCC) workforce development system.

You help Business Service Representatives (BSRs), case managers, and workforce 
staff with:
- Finding the correct activity codes for case notes
- Navigating the CalJOBS platform (where to click, which screens, which tabs)
- Writing case note descriptions that pass compliance review
- Understanding procedures for enrollment, exits, transfers, and follow-ups
- Answering questions about state directives and local policies
- Explaining NAICS industry codes for employer services

## How to Use the Retrieved Context Below

You have been provided with RETRIEVED KNOWLEDGE CHUNKS that are the most relevant 
pieces of documentation for the user's question. These chunks come from:
- Official CalJOBS activity code definitions
- Real case note templates used in practice
- Navigation procedures (screen-by-screen instructions)
- State directives and local AJCC policies
- Compliance and audit requirements

IMPORTANT RULES:
1. Base your answers PRIMARILY on the retrieved context below
2. If the retrieved context contains the answer, use it — don't guess
3. If the context is insufficient, say so honestly and suggest what 
   additional information might help
4. Bold code numbers (e.g., **E20**, **181**) for easy scanning
5. When referencing a procedure, give step-by-step instructions
6. When suggesting codes, explain WHY each code applies
7. Mention related codes the user might also need
8. Be concise — staff are busy and need actionable answers
9. If you reference a source, mention which domain it came from 
   (e.g., "According to the activity code definition..." or 
   "Based on the case note template for this code...")

## Common Workflows (always available as background knowledge)
- New client enrollment: 101 (Orientation) + 102 (Initial Assessment)
- Employer outreach: E20 (Contact) → E28 (Services Provided) → E03 (Job Order)
- Supportive services: 181 (Transportation), 182 (Training Support), 183 (Incentive), 188 (Other)
- Training: 300-330 range codes + NAICS industry code
- Follow-up: E60 (Job Order), E57 (Employer Follow-up)
"""


def build_rag_system_prompt(query, collection=None, domain_filter=None):
    """
    Build a complete system prompt with retrieved context for a specific query.
    
    This is called ONCE per user message. The flow:
    1. Take the user's question
    2. Retrieve relevant chunks from ChromaDB
    3. Inject them into the system prompt
    4. Return the complete prompt for the Claude API call
    
    Returns:
        (system_prompt: str, retrieved_chunks: list)
    """
    if collection is None:
        collection = get_collection()
    
    # Retrieve relevant knowledge
    context_block, chunks = retrieve_for_prompt(
        query=query,
        collection=collection,
        n_results=8,
        domain_filter=domain_filter,
        min_relevance=0.25,
    )
    
    # Build the complete system prompt
    if context_block:
        system_prompt = (
            f"{BASE_SYSTEM_PROMPT}\n\n"
            f"## Retrieved Knowledge (most relevant to the user's question)\n\n"
            f"{context_block}"
        )
    else:
        system_prompt = (
            f"{BASE_SYSTEM_PROMPT}\n\n"
            f"## Note: No specific documentation was found for this query.\n"
            f"Answer based on your general knowledge of CalJOBS and workforce "
            f"development, but let the user know that you don't have specific "
            f"documentation for their question."
        )
    
    return system_prompt, chunks


def detect_query_domains(query):
    """
    Heuristic: guess which knowledge domains are most relevant to a query.
    
    This is optional — you can always search all domains. But filtering
    improves precision when the intent is clear.
    
    Returns None (search all) or a list of domain strings.
    """
    query_lower = query.lower()
    
    # Navigation-focused queries
    nav_keywords = [
        "where", "how do i", "navigate", "find", "screen", "tab", "click",
        "go to", "menu", "button", "page", "where is", "how to get to",
        "location", "path"
    ]
    
    # Code-focused queries
    code_keywords = [
        "code", "activity code", "e-code", "what code", "which code",
        "code for", "e20", "e60", "e03", "181", "183", "101", "102"
    ]
    
    # Case note-focused queries  
    note_keywords = [
        "case note", "description", "subject line", "document", "write",
        "template", "how to write", "note for", "case note for"
    ]
    
    # Procedure-focused queries
    proc_keywords = [
        "procedure", "process", "steps", "enroll", "exit", "transfer",
        "how do i", "workflow", "what happens when"
    ]
    
    detected = []
    
    if any(kw in query_lower for kw in nav_keywords):
        detected.append("navigation")
    if any(kw in query_lower for kw in code_keywords):
        detected.append("codes")
    if any(kw in query_lower for kw in note_keywords):
        detected.extend(["case_notes", "codes"])
    if any(kw in query_lower for kw in proc_keywords):
        detected.extend(["procedures", "navigation"])
    
    # Deduplicate
    detected = list(dict.fromkeys(detected))
    
    # If nothing specific detected, search everything
    if not detected:
        return None
    
    # Always include codes as a fallback — they're the most common need
    if "codes" not in detected:
        detected.append("codes")
    
    return detected


def format_sources_for_display(chunks):
    """
    Format retrieved chunks into a human-readable sources list
    for display below the AI response in the UI.
    
    This gives users transparency into WHERE the answer came from,
    building trust in the system.
    """
    if not chunks:
        return ""
    
    sources = []
    seen = set()
    
    for chunk in chunks:
        meta = chunk["metadata"]
        domain = meta.get("domain", "unknown")
        code = meta.get("code", "")
        source = meta.get("source", "")
        relevance = chunk.get("relevance", 0)
        
        # Create a unique key to avoid duplicate source entries
        key = f"{domain}_{code}_{source}"
        if key in seen:
            continue
        seen.add(key)
        
        label = f"**{domain.replace('_', ' ').title()}**"
        if code:
            label += f" — Code {code}"
        label += f" ({relevance:.0%} match)"
        
        sources.append(label)
    
    if sources:
        return "📚 **Sources:** " + " · ".join(sources)
    return ""
