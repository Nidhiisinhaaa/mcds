"""Pure text-processing helpers for guideline ingestion - kept dependency-free
(no pypdf/chromadb imports) so they're trivial to unit test."""

import re

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list:
    """Slide a window of `chunk_size` characters over `text`, advancing by
    `chunk_size - overlap` each step, so consecutive chunks overlap by
    `overlap` characters. Returns [] for blank text."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    step = chunk_size - overlap
    if step <= 0:
        step = chunk_size  # guard against a misconfigured overlap >= chunk_size

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start += step
    return chunks


def slugify_topic(filename: str) -> str:
    """Derive a topic slug from a PDF filename, e.g.
    "WHO Physical Activity Guidelines.pdf" -> "who_physical_activity_guidelines"."""
    stem = re.sub(r"\.pdf$", "", filename, flags=re.IGNORECASE)
    slug = re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_")
    return slug or "guideline"


# Priority order matters: "older_adults" must be checked before "adults" (an
# "older adults" heading also contains the substring "adults"), and
# "pregnancy" before either (a pregnancy section can mention "women" but
# shouldn't be miscategorised as adults/older_adults).
AGE_GROUPS = ["pregnancy", "older_adults", "adolescents", "children", "adults", "unknown"]

_AGE_GROUP_PATTERNS = [
    ("pregnancy", re.compile(r"pregnan\w*|postpartum|breastfeeding", re.I)),
    ("older_adults", re.compile(r"older adults?|\baged\s*(?:65|60)\b|\b(?:65|60)\+|elderly", re.I)),
    ("adolescents", re.compile(r"adolescents?|\bteen(?:agers?)?\b|\byouth\b", re.I)),
    ("children", re.compile(r"\bchildren\b|\bchild\b|\bkids?\b|school[- ]age|\binfants?\b|\btoddlers?\b", re.I)),
    ("adults", re.compile(r"\badults?\b", re.I)),
]


def detect_age_group(text: str) -> str:
    """Best-effort age-group keyword match against a piece of text. Returns
    one of AGE_GROUPS, defaulting to "unknown" when nothing matches."""
    text = text or ""
    for label, pattern in _AGE_GROUP_PATTERNS:
        if pattern.search(text):
            return label
    return "unknown"


def detect_page_heading_age_group(page_text: str, current: str = "unknown") -> str:
    """Scan a page's short, heading-like lines for an age-group signal (e.g.
    "Children and adolescents (aged 5-17 years)"), returning the last one
    found - or `current` unchanged if this page has no such heading. Meant
    to be threaded page-by-page through a document so a section heading's
    age group carries over to the pages that follow it, until the next
    heading changes it."""
    updated = current
    for line in (page_text or "").splitlines():
        line = line.strip()
        if not line or len(line) > 100:
            continue  # not heading-like - full paragraphs are excluded
        group = detect_age_group(line)
        if group != "unknown":
            updated = group
    return updated
