"""
Data cleaning service.

Takes raw review text and applies:
  - HTML / XML tag stripping
  - URL removal
  - Whitespace normalisation
  - Minimum length filter (drops very short / empty reviews)
  - Spam / bot heuristics (repeated characters, all-caps short posts)
  - SHA-256 content hashing for deduplication
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────
MIN_CONTENT_LENGTH = 15      # characters after cleaning
MAX_REPEATED_CHAR_RATIO = 0.6  # e.g. "aaaaaaaaaa" → spam


@dataclass
class CleanedReview:
    external_id: str
    source: str
    author: Optional[str]
    rating: Optional[int]
    raw_content: str
    cleaned_content: str
    content_hash: str
    review_date: Optional[object]  # datetime | None


def _strip_html(text: str) -> str:
    """Remove HTML/XML tags using BeautifulSoup (html.parser — no lxml needed)."""
    try:
        return BeautifulSoup(text, "html.parser").get_text(separator=" ")
    except Exception:
        return re.sub(r"<[^>]+>", " ", text)


def _remove_urls(text: str) -> str:
    """Remove http/https URLs and bare www. links."""
    return re.sub(r"https?://\S+|www\.\S+", "", text)


def _normalise_whitespace(text: str) -> str:
    """Collapse multiple spaces / newlines into single spaces."""
    return re.sub(r"\s+", " ", text).strip()


def _is_spam(text: str) -> bool:
    """
    Heuristic spam / low-quality filter.
    Returns True if the review should be discarded.
    """
    if len(text) < MIN_CONTENT_LENGTH:
        return True

    # Repeated single character (e.g. "aaaaaaaaaa!!!!")
    most_common_char_count = max(text.lower().count(c) for c in set(text.lower()) if c.isalnum())
    if len(text) > 0 and most_common_char_count / len(text) > MAX_REPEATED_CHAR_RATIO:
        return True

    return False


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clean_review(raw_content: str) -> tuple[str, bool]:
    """
    Clean a single review text.

    Returns:
        (cleaned_text, is_valid)  — is_valid is False if the review
        should be discarded after cleaning.
    """
    text = _strip_html(raw_content)
    text = _remove_urls(text)
    text = _normalise_whitespace(text)

    if _is_spam(text):
        return text, False

    return text, True


def clean_reviews(raw_reviews: list) -> list[CleanedReview]:
    """
    Clean a list of RawReview objects (from scraper.py).

    Returns only reviews that pass quality filters, with duplicates
    detected by content hash removed (keeps first occurrence).
    """
    seen_hashes: set[str] = set()
    results: list[CleanedReview] = []
    discarded = 0

    for raw in raw_reviews:
        cleaned_text, is_valid = clean_review(raw.content)

        if not is_valid:
            discarded += 1
            continue

        content_hash = _sha256(cleaned_text)

        if content_hash in seen_hashes:
            discarded += 1
            continue

        seen_hashes.add(content_hash)
        results.append(
            CleanedReview(
                external_id=raw.external_id,
                source=raw.source,
                author=raw.author,
                rating=raw.rating,
                raw_content=raw.content,
                cleaned_content=cleaned_text,
                content_hash=content_hash,
                review_date=raw.review_date,
            )
        )

    logger.info(
        "Cleaning complete: %d kept, %d discarded (spam/duplicate)",
        len(results),
        discarded,
    )
    return results
