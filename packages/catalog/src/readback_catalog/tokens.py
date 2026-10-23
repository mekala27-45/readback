"""The tokenizer shared by the index, the synonym table and the floor's entity matching."""

from __future__ import annotations

import re

_WORD = re.compile(r"[a-z0-9]+")
STOP = frozenset(
    "a an and are as at be by did do does for from had has have how in is it its of on or per "
    "than that the their there this to was were what when where which who why with".split()
)


def stem(word: str) -> str:
    """A light stem: plural and a few verb endings, so share and shares meet."""
    for suffix, keep in (("ies", "y"), ("sses", "ss"), ("s", "")):
        if len(word) > 3 and word.endswith(suffix) and not word.endswith("ss"):
            return word[: -len(suffix)] + keep
    return word


def tokens(text: str) -> list[str]:
    lowered = text.lower().replace("_", " ").replace(".", " ")
    return [stem(w) for w in _WORD.findall(lowered) if w not in STOP]
