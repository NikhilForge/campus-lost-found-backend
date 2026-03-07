"""
Matching service — finds found_items that likely correspond to a lost_item.

Scoring logic:
  +40  exact location match
  +20  same category
  +10  per keyword overlap in item_name
  +5   per keyword overlap in description
  +10  date within 7 days
  +5   date within 30 days

A score >= 20 is returned as a potential match.
"""

from database import get_supabase_admin
import re
from typing import List, Dict, Any
from datetime import date, timedelta


_STOP_WORDS = {
    "a", "an", "the", "is", "it", "my", "was", "in", "at", "on", "of",
    "and", "or", "with", "have", "had", "has", "for", "to", "i",
}


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[a-z]+", text.lower())
    return {t for t in tokens if t not in _STOP_WORDS and len(t) > 2}


def _score(lost: dict, found: dict) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    # Location match
    if lost.get("location") and found.get("location"):
        if lost["location"].lower() == found["location"].lower():
            score += 40
            reasons.append(f"Same location: {lost['location']}")

    # Category match
    if lost.get("category") and found.get("category"):
        if lost["category"].lower() == found["category"].lower():
            score += 20
            reasons.append(f"Same category: {lost['category']}")

    # Item name keyword overlap
    lost_name_tokens = _tokenize(lost.get("item_name", ""))
    found_name_tokens = _tokenize(found.get("item_name", ""))
    name_overlap = lost_name_tokens & found_name_tokens
    if name_overlap:
        score += len(name_overlap) * 10
        reasons.append(f"Name keyword match: {', '.join(name_overlap)}")

    # Description keyword overlap
    lost_desc_tokens = _tokenize(lost.get("description", ""))
    found_desc_tokens = _tokenize(found.get("description", ""))
    desc_overlap = (lost_desc_tokens | lost_name_tokens) & (found_desc_tokens | found_name_tokens)
    desc_only = desc_overlap - name_overlap
    if desc_only:
        score += len(desc_only) * 5
        reasons.append(f"Description keyword match: {', '.join(list(desc_only)[:5])}")

    # Date proximity
    try:
        d_lost = date.fromisoformat(str(lost.get("date_lost", "")))
        d_found = date.fromisoformat(str(found.get("date_found", "")))
        delta = abs((d_found - d_lost).days)
        if delta <= 7:
            score += 10
            reasons.append("Found within 7 days of loss")
        elif delta <= 30:
            score += 5
            reasons.append("Found within 30 days of loss")
    except (ValueError, TypeError):
        pass

    return score, reasons


async def find_matches(lost_item: dict, threshold: float = 20.0) -> List[Dict[str, Any]]:
    """Return a ranked list of found_items that potentially match the lost_item."""
    db = get_supabase_admin()

    # Only consider open found items
    result = db.table("found_items").select("*").eq("status", "found").execute()
    found_items = result.data or []

    scored: list[tuple[float, list[str], dict]] = []
    for fi in found_items:
        sc, reasons = _score(lost_item, fi)
        if sc >= threshold:
            scored.append((sc, reasons, fi))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    return [
        {
            "found_item": item,
            "match_score": round(score, 1),
            "match_reasons": reasons,
        }
        for score, reasons, item in scored[:10]  # top 10
    ]
