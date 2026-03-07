"""
CalJOBS Navigator — Knowledge Base Module
==========================================
RAG (Retrieval-Augmented Generation) engine that stores, indexes, and retrieves
CalJOBS knowledge across multiple domains using ChromaDB vector storage.

Architecture Overview:
    Documents → Chunking → Embedding → ChromaDB (vector store)
    User Query → Embedding → Similarity Search → Top-K Chunks → Claude API

Domains:
    - codes:       Activity codes (E20, 181, 300, etc.)
    - case_notes:  Real case note templates and descriptions
    - navigation:  Screen-by-screen CalJOBS procedures
    - procedures:  Enrollment, exit, transfer workflows
    - compliance:  Audit requirements, documentation standards
    - directives:  State-level policy directives (EDD, CWDB)

Each chunk stored with metadata for filtered retrieval:
    { domain, source_file, code (if applicable), category, chunk_index }
"""

import json
import os
import re
import hashlib
from pathlib import Path
from datetime import datetime

import chromadb
from chromadb.config import Settings


# ─── Configuration ───────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
CHROMA_DIR = BASE_DIR / "chroma_db"          # Persistent vector store location
COLLECTION_NAME = "caljobs_knowledge"         # Single collection, domain-filtered

# Chunking defaults
DEFAULT_CHUNK_SIZE = 800        # ~800 chars ≈ ~200 tokens — sweet spot for retrieval
DEFAULT_CHUNK_OVERLAP = 100     # Overlap prevents cutting mid-thought
MAX_RETRIEVAL_RESULTS = 8       # Top-K chunks returned per query


# ─── ChromaDB Client ─────────────────────────────────────────────────────────

def get_client():
    """
    Initialize and return a persistent ChromaDB client.
    
    ChromaDB stores data in two forms:
    1. The raw documents and metadata (in SQLite, inside chroma_db/)
    2. The vector embeddings (in an index file, also in chroma_db/)
    
    'Persistent' means data survives between app restarts — unlike
    Streamlit session_state which dies when the tab closes.
    """
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    
    client = chromadb.PersistentClient(
        path=str(CHROMA_DIR),
        settings=Settings(
            anonymized_telemetry=False,   # No data sent to ChromaDB Inc.
        )
    )
    return client


def get_collection(client=None):
    """
    Get or create the main knowledge collection.
    
    ChromaDB uses a default embedding function (all-MiniLM-L6-v2) which is
    a sentence-transformer model that runs locally — no API key needed.
    It converts text into 384-dimensional vectors that capture semantic meaning.
    
    'get_or_create' is idempotent: safe to call repeatedly.
    """
    if client is None:
        client = get_client()
    
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={
            "description": "CalJOBS Navigator knowledge base",
            "hnsw:space": "cosine",   # Cosine similarity for semantic search
        }
    )
    return collection


# ─── Document ID Generation ──────────────────────────────────────────────────

def make_chunk_id(domain, source, index, code=None):
    """
    Generate a deterministic, unique ID for each chunk.
    
    Why deterministic? So re-ingesting the same document overwrites
    existing chunks instead of creating duplicates. This is critical
    for maintainability — you can update a directive PDF and re-run
    ingestion without polluting the database.
    
    Format: {domain}_{source_hash}_{index}[_{code}]
    """
    source_hash = hashlib.md5(source.encode()).hexdigest()[:8]
    parts = [domain, source_hash, str(index)]
    if code:
        parts.append(code)
    return "_".join(parts)


# ─── Chunking Functions ──────────────────────────────────────────────────────

def chunk_text(text, chunk_size=DEFAULT_CHUNK_SIZE, overlap=DEFAULT_CHUNK_OVERLAP):
    """
    Split text into overlapping chunks at sentence boundaries.
    
    Why overlap? Imagine a procedure that says:
        "...click the Programs tab. Then select WIOA from the dropdown..."
    If you split right between those sentences, neither chunk has
    the full instruction. Overlap ensures continuity.
    
    Why sentence boundaries? Cutting mid-sentence creates fragments
    that embed poorly — the vector won't capture the full meaning.
    
    Returns list of (chunk_text, char_start, char_end) tuples.
    """
    if not text or not text.strip():
        return []
    
    # Split into sentences (handles abbreviations reasonably)
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    
    chunks = []
    current_chunk = ""
    current_start = 0
    char_pos = 0
    
    for sentence in sentences:
        # If adding this sentence would exceed chunk_size, save current chunk
        if current_chunk and len(current_chunk) + len(sentence) + 1 > chunk_size:
            chunks.append((current_chunk.strip(), current_start, char_pos))
            
            # Overlap: keep the last portion of the current chunk
            overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
            current_chunk = overlap_text + " " + sentence
            current_start = max(0, char_pos - overlap)
        else:
            if current_chunk:
                current_chunk += " " + sentence
            else:
                current_chunk = sentence
                current_start = char_pos
        
        char_pos += len(sentence) + 1  # +1 for the space
    
    # Don't forget the last chunk
    if current_chunk.strip():
        chunks.append((current_chunk.strip(), current_start, char_pos))
    
    return chunks


def chunk_by_sections(text, section_pattern=r'\n(?=[A-Z][A-Z\s]{2,})'):
    """
    Split text at section headers (e.g., directive documents).
    Falls back to regular chunking if no sections found.
    """
    sections = re.split(section_pattern, text)
    if len(sections) <= 1:
        return chunk_text(text)
    
    chunks = []
    for i, section in enumerate(sections):
        section = section.strip()
        if not section:
            continue
        # If a section is too long, sub-chunk it
        if len(section) > DEFAULT_CHUNK_SIZE * 2:
            sub_chunks = chunk_text(section)
            chunks.extend(sub_chunks)
        else:
            chunks.append((section, 0, len(section)))
    
    return chunks


# ─── Ingestion Functions (one per data type) ─────────────────────────────────

def ingest_codes_json(collection, json_path, domain="codes"):
    """
    Ingest CalJOBS activity codes from codes_database_complete.json.
    
    Each code becomes ONE chunk. Why? Because codes are discrete, 
    self-contained units of knowledge. You'd never want half a code 
    description in one chunk and half in another — that would break 
    retrieval quality.
    
    The document text combines all fields into a rich, searchable string.
    The metadata preserves structured fields for filtering.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        db = json.load(f)
    
    documents = []
    metadatas = []
    ids = []
    
    source_name = Path(json_path).name
    
    for i, entry in enumerate(db["codes"]):
        code = entry["code"]
        name = entry["name"]
        desc = entry.get("description", "")
        category = entry.get("category", "")
        keywords = entry.get("keywords", [])
        when_to_use = entry.get("when_to_use", [])
        requirements = entry.get("requirements", [])
        related = entry.get("related_codes", [])
        
        # Build a rich document string — this is what gets embedded.
        # Include all relevant text so semantic search can match on any aspect.
        doc_parts = [
            f"CalJOBS Activity Code {code}: {name}",
            f"Category: {category}",
            f"Description: {desc}",
        ]
        if when_to_use:
            doc_parts.append(f"When to use: {'; '.join(when_to_use)}")
        if requirements:
            doc_parts.append(f"Requirements: {'; '.join(requirements)}")
        if related:
            doc_parts.append(f"Related codes: {', '.join(related)}")
        if keywords:
            doc_parts.append(f"Keywords: {', '.join(keywords)}")
        
        document = "\n".join(doc_parts)
        
        documents.append(document)
        metadatas.append({
            "domain": domain,
            "source": source_name,
            "code": code,
            "code_name": name,
            "category": category,
            "chunk_index": i,
            "ingested_at": datetime.now().isoformat(),
        })
        ids.append(make_chunk_id(domain, source_name, i, code))
    
    # Upsert = insert or update. Safe for re-ingestion.
    collection.upsert(
        documents=documents,
        metadatas=metadatas,
        ids=ids,
    )
    
    return len(documents)


def ingest_case_notes(collection, txt_path, domain="case_notes"):
    """
    Ingest case note templates from Case_Notes.txt.
    
    This file has a complex structure with two sections:
    1. Employer E-codes: code → #N marker → subject (multi-line) → description
    2. Supportive services: 3-digit code → type → description
    Plus some standalone templates (e.g., Timesheet Upload) without codes.
    
    This is domain knowledge that doesn't exist in any manual — it's
    institutional knowledge captured from real practice.
    """
    with open(txt_path, "r", encoding="utf-8") as f:
        raw = f.read()
    
    # ── Strategy: split the file at code boundaries ──
    # A "code line" is either E## (1-2 digits) or ### (3 digits) on its own line.
    # Everything between two code lines belongs to the first code.
    
    lines = raw.split("\n")
    entries = []
    current_entry = None
    
    # Header lines to skip (appear at top of sections)
    SKIP_LINES = {
        "code", "subject", "description", "supportive service",
        "type", "supportive service \ntype"
    }
    
    for line in lines:
        stripped = line.strip()
        
        # Detect code lines: E01-E99 or 3-digit numbers (100-999)
        is_ecode = bool(re.match(r'^E\d{1,2}$', stripped))
        is_numcode = bool(re.match(r'^\d{3}$', stripped))
        
        if is_ecode or is_numcode:
            # Save previous entry if it has content
            if current_entry and current_entry["content_lines"]:
                entries.append(current_entry)
            
            current_entry = {
                "code": stripped,
                "content_lines": [],
            }
        elif current_entry is not None:
            # Skip empty lines, header labels, and #N markers
            if not stripped:
                continue
            if stripped.lower() in SKIP_LINES:
                continue
            if re.match(r'^#\d+$', stripped):  # Skip "#1", "#2", etc.
                continue
            
            current_entry["content_lines"].append(stripped)
    
    # Don't forget the last entry
    if current_entry and current_entry["content_lines"]:
        entries.append(current_entry)
    
    # ── Also capture standalone templates (no code, like "Timesheet Upload") ──
    # These appear after the coded sections — look for blocks that start
    # with a title-like line followed by description text
    
    documents = []
    metadatas = []
    ids = []
    
    source_name = Path(txt_path).name
    
    for idx, entry in enumerate(entries):
        code = entry["code"]
        content_lines = entry["content_lines"]
        
        if not content_lines:
            continue
        
        # First meaningful line is usually the subject/title
        subject = content_lines[0] if content_lines else ""
        
        # Rest is the description (may include asterisk notes, which are useful)
        description = " ".join(content_lines[1:]).strip() if len(content_lines) > 1 else subject
        
        # Build the full document text
        doc_parts = [
            f"Case Note Template for CalJOBS Code {code}",
            f"Subject: {subject}",
        ]
        if description and description != subject:
            doc_parts.append(f"Description: {description}")
        
        document = "\n".join(doc_parts)
        
        documents.append(document)
        metadatas.append({
            "domain": domain,
            "source": source_name,
            "code": code,
            "category": "case_note_template",
            "subject": subject[:200],  # Truncate for metadata limit
            "chunk_index": idx,
            "ingested_at": datetime.now().isoformat(),
        })
        ids.append(make_chunk_id(domain, source_name, idx, code))
    
    if documents:
        collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )
    
    return len(documents)


def ingest_text_document(collection, file_path, domain="procedures",
                          metadata_extra=None):
    """
    Generic text document ingestion — for directives, procedures, etc.
    
    This is your general-purpose ingester. Any .txt or .md file can be
    fed through here. It chunks the text and stores each chunk with
    domain metadata.
    
    metadata_extra: dict of additional metadata to attach to every chunk
                    (e.g., {"directive_number": "WSD24-05"})
    """
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()
    
    chunks = chunk_text(text)
    
    if not chunks:
        return 0
    
    documents = []
    metadatas = []
    ids = []
    
    source_name = Path(file_path).name
    
    for idx, (chunk_text_str, start, end) in enumerate(chunks):
        meta = {
            "domain": domain,
            "source": source_name,
            "chunk_index": idx,
            "char_start": start,
            "char_end": end,
            "ingested_at": datetime.now().isoformat(),
        }
        if metadata_extra:
            meta.update(metadata_extra)
        
        documents.append(chunk_text_str)
        metadatas.append(meta)
        ids.append(make_chunk_id(domain, source_name, idx))
    
    collection.upsert(
        documents=documents,
        metadatas=metadatas,
        ids=ids,
    )
    
    return len(documents)


def ingest_pdf(collection, pdf_path, domain="directives", metadata_extra=None):
    """
    Ingest a PDF document. Extracts text, chunks it, stores it.

    Tries PyMuPDF first, falls back to pdfminer.six if unavailable.

    For scanned PDFs (images, not text), you'd need OCR — but most
    EDD/CWDB directives are text-based PDFs, so this covers the
    primary use case.
    """
    full_text = ""

    # Try PyMuPDF first (faster), fall back to pdfminer.six
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        for page in doc:
            full_text += page.get_text() + "\n"
        doc.close()
    except (ImportError, Exception):
        # PyMuPDF unavailable or DLL blocked — try pdfminer.six
        try:
            from pdfminer.high_level import extract_text
            full_text = extract_text(pdf_path)
        except ImportError:
            raise ImportError(
                "PDF ingestion requires PyMuPDF or pdfminer.six. Install with: "
                "pip install pdfminer.six"
            )
    
    if not full_text.strip():
        return 0
    
    chunks = chunk_text(full_text)
    
    documents = []
    metadatas = []
    ids = []
    
    source_name = Path(pdf_path).name
    
    for idx, (chunk_text_str, start, end) in enumerate(chunks):
        meta = {
            "domain": domain,
            "source": source_name,
            "chunk_index": idx,
            "char_start": start,
            "char_end": end,
            "ingested_at": datetime.now().isoformat(),
        }
        if metadata_extra:
            meta.update(metadata_extra)
        
        documents.append(chunk_text_str)
        metadatas.append(meta)
        ids.append(make_chunk_id(domain, source_name, idx))
    
    collection.upsert(
        documents=documents,
        metadatas=metadatas,
        ids=ids,
    )
    
    return len(documents)


# ─── Retrieval Functions ─────────────────────────────────────────────────────

def retrieve(query, collection=None, n_results=MAX_RETRIEVAL_RESULTS,
             domain_filter=None):
    """
    Semantic search: find the most relevant knowledge chunks for a query.
    
    How it works under the hood:
    1. Your query text gets embedded into a 384-dim vector (same model
       that embedded the documents)
    2. ChromaDB computes cosine similarity between your query vector
       and every stored document vector
    3. Returns the top-N most similar chunks, ranked by relevance
    
    Cosine similarity measures the angle between two vectors — if they
    point in the same direction (similar meaning), the score approaches 1.0.
    If they're perpendicular (unrelated), score is 0.
    
    domain_filter: restrict search to specific domain(s)
        - None = search all domains
        - "codes" = only search codes
        - ["codes", "case_notes"] = search codes and case notes
    """
    if collection is None:
        collection = get_collection()
    
    # Build the where filter for domain restriction
    where_filter = None
    if domain_filter:
        if isinstance(domain_filter, str):
            where_filter = {"domain": domain_filter}
        elif isinstance(domain_filter, list) and len(domain_filter) == 1:
            where_filter = {"domain": domain_filter[0]}
        elif isinstance(domain_filter, list):
            where_filter = {"domain": {"$in": domain_filter}}
    
    # Execute the query
    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )
    
    # Unpack results into a cleaner format
    chunks = []
    if results and results["documents"] and results["documents"][0]:
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            chunks.append({
                "text": doc,
                "metadata": meta,
                "distance": dist,          # Lower = more similar (cosine distance)
                "relevance": 1 - dist,     # Higher = more relevant (0 to 1 scale)
            })
    
    return chunks


def retrieve_for_prompt(query, collection=None, n_results=MAX_RETRIEVAL_RESULTS,
                         domain_filter=None, min_relevance=0.3):
    """
    Retrieve chunks and format them for inclusion in a Claude API prompt.
    
    This is the bridge between retrieval and generation — it takes raw
    chunks and formats them into a structured context block that Claude
    can reason over.
    
    min_relevance: filter out low-quality matches. 0.3 is conservative;
    raise it if you get too much noise, lower it if you miss results.
    """
    chunks = retrieve(query, collection, n_results, domain_filter)
    
    # Filter by minimum relevance
    chunks = [c for c in chunks if c["relevance"] >= min_relevance]
    
    if not chunks:
        return "", []
    
    # Format for Claude's context
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk["metadata"]
        domain = meta.get("domain", "unknown")
        source = meta.get("source", "unknown")
        code = meta.get("code", "")
        relevance = f"{chunk['relevance']:.0%}"
        
        header = f"[Source {i}: {domain}"
        if code:
            header += f" | Code {code}"
        header += f" | {source} | Relevance: {relevance}]"
        
        context_parts.append(f"{header}\n{chunk['text']}")
    
    context_block = "\n\n---\n\n".join(context_parts)
    
    return context_block, chunks


# ─── Knowledge Base Stats ────────────────────────────────────────────────────

def get_stats(collection=None):
    """
    Get summary statistics about the knowledge base.
    Useful for the UI dashboard and debugging.
    """
    if collection is None:
        collection = get_collection()
    
    total = collection.count()
    
    # Get domain breakdown
    domain_counts = {}
    if total > 0:
        # Sample all items to count domains
        # (ChromaDB doesn't have GROUP BY, so we peek at metadata)
        all_items = collection.peek(limit=min(total, 10000))
        if all_items and all_items["metadatas"]:
            for meta in all_items["metadatas"]:
                domain = meta.get("domain", "unknown")
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
    
    return {
        "total_chunks": total,
        "domains": domain_counts,
        "storage_path": str(CHROMA_DIR),
    }


def clear_domain(domain, collection=None):
    """
    Remove all chunks from a specific domain.
    Useful when re-ingesting updated documents.
    """
    if collection is None:
        collection = get_collection()
    
    # Get all IDs with this domain
    results = collection.get(
        where={"domain": domain},
        include=[],   # We only need the IDs
    )
    
    if results and results["ids"]:
        collection.delete(ids=results["ids"])
        return len(results["ids"])
    
    return 0


def clear_all(collection=None):
    """Nuclear option: remove everything. Use with caution."""
    client = get_client()
    try:
        client.delete_collection(COLLECTION_NAME)
    except ValueError:
        pass  # Collection didn't exist
    return get_collection(client)
