"""
English regex helpers for pulling numeric lifestyle values straight out of text,
independent of the LLM. Used by the extractor to cross-check (and where they
disagree by more than 20%, override) the LLM's normalised numbers.
"""

import re
from typing import Optional

_RANGE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")

_NUMBER_OR_RANGE = r"\d+(?:\.\d+)?(?:\s*(?:-|to)\s*\d+(?:\.\d+)?)?"

_WORD_NUMBERS = {
    "once": 1,
    "twice": 2,
    "thrice": 3,
}


def _parse_number_or_range(matched_text: str) -> Optional[float]:
    range_match = _RANGE_RE.search(matched_text)
    if range_match:
        low, high = float(range_match.group(1)), float(range_match.group(2))
        return (low + high) / 2
    single_match = _NUMBER_RE.search(matched_text)
    if single_match:
        return float(single_match.group(0))
    return None


def extract_hours(text: str) -> Optional[float]:
    """'7 hours', '7-8 hours', '5 to 6 hrs' -> a float (ranges averaged)."""
    text_l = text.lower()
    match = re.search(rf"({_NUMBER_OR_RANGE})\s*(?:hours?|hrs?|hr\b)", text_l)
    if match:
        return _parse_number_or_range(match.group(0))
    if re.search(r"half\s+an?\s+hour", text_l):
        return 0.5
    return None


def extract_litres(text: str) -> Optional[float]:
    """Litres, millilitres, or glasses (assumed 250 ml each) -> litres."""
    text_l = text.lower()

    litre_match = re.search(
        rf"({_NUMBER_OR_RANGE})\s*(?:litres?|liters?|ltr\.?|l\b)", text_l
    )
    if litre_match:
        return _parse_number_or_range(litre_match.group(0))

    ml_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:ml|millilit(?:er|re)s?)", text_l)
    if ml_match:
        return round(float(ml_match.group(1)) / 1000, 3)

    glass_match = re.search(rf"({_NUMBER_OR_RANGE})\s*glass(?:es)?", text_l)
    if glass_match:
        glasses = _parse_number_or_range(glass_match.group(0))
        if glasses is not None:
            return round(glasses * 0.25, 3)

    return None


def extract_days_per_week(text: str) -> Optional[int]:
    """'twice a week', '3 times a week', 'every day', 'never' -> a day count."""
    text_l = text.lower()

    if re.search(r"every\s*day|daily|each\s*day", text_l):
        return 7

    if re.search(r"\bnever\b|no\s+exercise|don'?t\s+exercise|does\s*n'?t\s+exercise", text_l):
        return 0

    numeric_match = re.search(r"(\d+)\s*(?:times|days?)\s*(?:a|per|/)\s*week", text_l)
    if numeric_match:
        return int(numeric_match.group(1))

    for word, value in _WORD_NUMBERS.items():
        if re.search(rf"\b{word}\b.*\bweek\b", text_l):
            return value

    return None


def extract_minutes(text: str) -> Optional[int]:
    """'30 minutes', 'half an hour', 'a 1 hour session' -> minutes."""
    text_l = text.lower()

    match = re.search(rf"({_NUMBER_OR_RANGE})\s*(?:minutes?|mins?)\b", text_l)
    if match:
        value = _parse_number_or_range(match.group(0))
        return int(round(value)) if value is not None else None

    if re.search(r"half\s+an?\s+hour", text_l):
        return 30

    hour_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\b", text_l)
    if hour_match and re.search(r"session|exercise|workout|gym|walk|run", text_l):
        return int(round(float(hour_match.group(1)) * 60))

    return None


def extract_cigarettes_per_day(text: str) -> Optional[int]:
    """'10 cigarettes a day', 'a pack a day', 'half a pack' -> cigarettes/day (1 pack = 20)."""
    text_l = text.lower()

    if re.search(r"half\s+a\s+pack", text_l):
        return 10

    pack_match = re.search(
        r"(?:(\d+(?:\.\d+)?)|an?)\s*packs?\s*(?:a|per)\s*day", text_l
    )
    if pack_match:
        count = float(pack_match.group(1)) if pack_match.group(1) else 1.0
        return int(round(count * 20))

    cig_match = re.search(r"(\d+)\s*cigarettes?", text_l)
    if cig_match:
        return int(cig_match.group(1))

    return None
