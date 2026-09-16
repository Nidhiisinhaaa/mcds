"""
Guideline-grounded recommendations: for each (non-red-flag) risk flag,
retrieve relevant guideline excerpts and ask the LLM to write specific,
practical advice grounded ONLY in those excerpts. Falls back to static
general guidance when retrieval finds nothing for a flag, and never crashes
(an empty or missing ChromaDB collection just means everything falls back).

Age-group matching: guideline PDFs like WHO's physical activity guidelines
cover several age bands (children/adolescents, adults, older adults,
pregnancy) in the same document. Chunks are tagged with an age group at
ingest time (knowledge/chunking.py); retrieval here is filtered to the
patient's own age group (or "unknown"-tagged, generally-applicable chunks),
the system prompt is told which age group the patient is in, and a
post-generation check drops - and falls back for - any item that still slips
through mentioning the wrong age group.
"""

import functools
import json
import logging
import re
from pathlib import Path
from typing import List

from pydantic import BaseModel

from assessment.engine import red_flags
from assessment.models import Recommendation
from core.services import groq_client
from knowledge import retriever

logger = logging.getLogger("assessment.recommender")

FALLBACK_PATH = Path(__file__).resolve().parent / "data" / "fallback_recommendations.json"
RETRIEVAL_K = 4

# code -> (fallback/topic key, retrieval query)
FLAG_TOPICS = {
    "poor_sleep": ("sleep", "sleep hygiene recommendations for better sleep quality and duration"),
    "sedentary_lifestyle": (
        "exercise",
        "physical activity and exercise recommendations, how much and how often",
    ),
    "high_stress": ("stress", "stress management and relaxation techniques"),
    "unhealthy_diet": (
        "diet",
        "healthy diet and dietary guidelines for Indian food habits",
    ),
    "low_water_intake": ("water", "daily water intake and hydration recommendations"),
    "tobacco_use": ("smoking", "tobacco use and smoking cessation guidance"),
    "alcohol_risk": ("alcohol", "reducing alcohol consumption guidance"),
    "overweight": ("weight", "healthy weight management through diet and physical activity"),
    "obese": ("weight", "healthy weight management through diet and physical activity"),
    "obesity_risk": ("weight", "healthy weight management through diet and physical activity"),
    "hypertension_risk": (
        "hypertension",
        "lifestyle changes to reduce blood pressure risk through diet and physical activity",
    ),
}

SYSTEM_PROMPT_TEMPLATE = (
    "You are writing lifestyle recommendations for a doctor's review, based ONLY on the "
    "numbered excerpts provided below. Do not use outside knowledge and do not invent "
    "numbers not present in the excerpts. Be specific and practical, citing numbers where "
    "the excerpts give them. Adapt suggestions to typical Indian diets and daily routines. "
    "Each recommendation must be 1-2 sentences. Never mention medications, supplements, or "
    "give a diagnosis. For every recommendation, list the ref ids (e.g. \"R1\") of the "
    "excerpts it actually draws on in source_refs - only ids that appear below. Output "
    "between 4 and 6 recommendation items total, covering the topics given.\n\n{age_guard}"
)

AGE_GUARDS = {
    "adults": (
        "This patient is an adult. Write every recommendation for a general adult audience. "
        "Never phrase advice around children, adolescents, kids, school-age, or pregnancy "
        "unless an excerpt is explicitly about adults in general."
    ),
    "older_adults": (
        "This patient is an older adult (65+). Write every recommendation appropriate for an "
        "older adult. Never phrase advice around children, adolescents, kids, school-age, or "
        "pregnancy."
    ),
}
_CHILD_AGE_GUARD = (
    "This patient is under 18 (a child or adolescent). Write recommendations appropriate for "
    "children/adolescents where the excerpts support it, and never frame advice around "
    "pregnancy or older adults."
)

# Post-generation safety net: catches wording that slipped through despite
# retrieval filtering and the prompt guard (e.g. an "unknown"-tagged excerpt
# that mentions a specific age group in passing).
_WRONG_AGE_TERMS_RE = re.compile(
    r"\bchild(?:ren)?\b|\bkids?\b|\badolescents?\b|\bpregnan\w*|\bschool[- ]age\b|\bteen(?:agers?)?\b",
    re.I,
)


class _RecommendationItem(BaseModel):
    category: str
    text_english: str
    source_refs: List[str] = []


class _RecommendationBatch(BaseModel):
    items: List[_RecommendationItem] = []


@functools.lru_cache(maxsize=1)
def _load_fallback() -> dict:
    with open(FALLBACK_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def derive_patient_age_group(age):
    """PatientProfile.age -> retrieval age_group: a single group string for
    retrieve()'s filter, or a list of acceptable groups for the <18 bucket
    (guideline PDFs commonly tag that range as "children" and/or
    "adolescents" separately). Missing age defaults to adults, per spec."""
    if age is None:
        return "adults"
    if age < 18:
        return ["children", "adolescents"]
    if age <= 64:
        return "adults"
    return "older_adults"


def _non_red_flag_flags(consultation):
    return list(
        consultation.risk_flags.exclude(code__in=red_flags.KNOWN_CODES).order_by("id")
    )


def _retrieve_for_flag(flag, age_group):
    topic, query = FLAG_TOPICS.get(flag.code, (flag.code, flag.label))
    try:
        chunks = retriever.retrieve(query, k=RETRIEVAL_K, age_group=age_group)
    except Exception:
        logger.exception("recommender.retrieve_failed", extra={"flag": flag.code})
        chunks = []
    return topic, chunks


def _build_llm_section(flag, topic, section_refs):
    lines = [f"Topic: {topic} (risk flag: {flag.label})"]
    for ref_id, chunk in section_refs:
        meta = chunk.get("metadata") or {}
        lines.append(f"[{ref_id}] (from {meta.get('file')}, page {meta.get('page')}): {chunk['text']}")
    return "\n".join(lines)


def _system_prompt_for(age_group) -> str:
    if isinstance(age_group, list):
        guard = _CHILD_AGE_GUARD
    else:
        guard = AGE_GUARDS.get(age_group, AGE_GUARDS["adults"])
    return SYSTEM_PROMPT_TEMPLATE.format(age_guard=guard)


def _call_llm(sections, chunks_by_ref, age_group) -> list:
    user_content = "\n\n".join(sections)
    try:
        result = groq_client.chat_json(
            _system_prompt_for(age_group),
            [{"role": "user", "content": user_content}],
            _RecommendationBatch,
            temperature=0.2,
        )
    except Exception:
        logger.exception("recommender.chat_json_failed")
        return []

    valid_refs = set(chunks_by_ref)
    items = []
    for item in result.items:
        cleaned_refs = [ref for ref in item.source_refs if ref in valid_refs]
        sources = []
        seen = set()
        for ref in cleaned_refs:
            meta = chunks_by_ref[ref].get("metadata") or {}
            key = (meta.get("file"), meta.get("page"))
            if key not in seen:
                seen.add(key)
                sources.append({"file": meta.get("file"), "page": meta.get("page")})
        items.append(
            {"category": item.category, "text_english": item.text_english, "sources": sources}
        )
    return items


def _drop_age_mismatched_items(items, age_group, fallback_data) -> list:
    """Adult/older-adult patients only: drop any item whose text is framed
    around children/adolescents/pregnancy, substituting fallback content for
    that item's topic when available (silently dropping it otherwise)."""
    if isinstance(age_group, list):
        return items  # patient IS a child/adolescent - no guard needed

    checked = []
    for item in items:
        if _WRONG_AGE_TERMS_RE.search(item["text_english"]):
            logger.warning(
                "recommender.dropped_age_mismatched_item",
                extra={"category": item["category"], "age_group": age_group},
            )
            fallback = fallback_data.get(item["category"])
            if fallback:
                checked.append(
                    {
                        "category": fallback["category"],
                        "text_english": fallback["text_english"],
                        "sources": ["general guidance"],
                    }
                )
            # else: no fallback for this category - drop it entirely.
        else:
            checked.append(item)
    return checked


def generate_recommendations(consultation) -> list:
    profile = getattr(consultation, "lifestyle_profile", None)
    if profile is None:
        return []

    flags = _non_red_flag_flags(consultation)
    if not flags:
        return []

    patient_profile = getattr(consultation.patient, "patient_profile", None)
    age_group = derive_patient_age_group(getattr(patient_profile, "age", None))

    fallback_data = _load_fallback()

    fallback_items = []
    llm_sections = []
    chunks_by_ref = {}
    ref_counter = 0

    for flag in flags:
        topic, chunks = _retrieve_for_flag(flag, age_group)

        if chunks:
            section_refs = []
            for chunk in chunks:
                ref_counter += 1
                ref_id = f"R{ref_counter}"
                chunks_by_ref[ref_id] = chunk
                section_refs.append((ref_id, chunk))
            llm_sections.append(_build_llm_section(flag, topic, section_refs))
        else:
            fallback = fallback_data.get(topic)
            if fallback:
                fallback_items.append(
                    {
                        "category": fallback["category"],
                        "text_english": fallback["text_english"],
                        "sources": ["general guidance"],
                    }
                )
            else:
                logger.info(
                    "recommender.no_content_for_flag", extra={"flag": flag.code, "topic": topic}
                )

    llm_items = _call_llm(llm_sections, chunks_by_ref, age_group) if llm_sections else []
    llm_items = _drop_age_mismatched_items(llm_items, age_group, fallback_data)

    combined = fallback_items + llm_items
    if not combined:
        return []

    texts = [item["text_english"] for item in combined]
    try:
        translations = groq_client.translate_batch(
            texts, source_lang="en", target_lang=consultation.language
        )
    except Exception:
        logger.exception("recommender.translate_batch_failed")
        translations = list(texts)

    created = []
    for order, (item, translated) in enumerate(zip(combined, translations)):
        created.append(
            Recommendation.objects.create(
                consultation=consultation,
                category=item["category"],
                text_english=item["text_english"],
                text_patient_language=translated,
                sources=item["sources"],
                order=order,
            )
        )
    return created
