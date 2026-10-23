"""Redaction: emails, phone numbers and identifiers removed from a question before any model sees it
and before it is stored. The original is never kept; the redacted question is what the log holds."""

from __future__ import annotations

import re
from dataclasses import dataclass

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE = re.compile(r"(?<![\w.])(?:\+?1[ .-]?)?\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}(?![\w])")
SSN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
CARD = re.compile(r"(?<![\w.-])(?:\d[ -]?){13,19}(?![\w-])")
# A customer, account or loan identifier: letters and digits a person would copy from a statement.
IDENT = re.compile(r"\b(?:[A-Z]{1,3}-?\d{5,}|\d{8,12}|(?:acct|account|customer|loan)[ #:]*[A-Z0-9-]{5,})\b", re.I)


@dataclass(frozen=True)
class Redacted:
    text: str
    removed: dict[str, int]


def redact(question: str) -> Redacted:
    removed: dict[str, int] = {}
    text = question
    for name, pattern, mark in (
        ("email", EMAIL, "[email]"),
        ("ssn", SSN, "[id]"),
        ("card", CARD, "[number]"),
        ("phone", PHONE, "[phone]"),
        ("identifier", IDENT, "[id]"),
    ):
        text, n = pattern.subn(mark, text)
        if n:
            removed[name] = n
    return Redacted(text, removed)
