"""Logging setup with review-content redaction (constitution: Security & Data Handling).

Review text and reviewer names MUST NOT be logged beyond what's strictly necessary for
debugging. This module gives callers a `redact_review_text` helper instead of ever logging
raw review content directly.
"""

from __future__ import annotations

import logging
import sys

from src.config.settings import SETTINGS

_CONFIGURED = False


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=getattr(logging, SETTINGS.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)


def redact_review_text(text: str | None, max_chars: int = 40) -> str:
    """Truncated, non-identifying preview safe for INFO-level logs.

    Full review text may only appear in DEBUG-level logs, and only for the duration needed
    to resolve the specific issue being debugged — never persisted long-term.
    """
    if not text:
        return "<empty>"
    preview = text.strip().replace("\n", " ")[:max_chars]
    suffix = "…" if len(text.strip()) > max_chars else ""
    return f"{preview}{suffix} ({len(text)} chars)"


def redact_reviewer_name(name: str | None) -> str:
    if not name:
        return "<unknown>"
    parts = name.strip().split()
    if not parts:
        return "<unknown>"
    first = parts[0]
    return f"{first[0]}." if first else "<unknown>"
