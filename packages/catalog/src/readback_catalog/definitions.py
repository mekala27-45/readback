"""Definitions lifted from each build's docs/definitions.md, with the line they sit on.

Three shapes occur in the three documents: a bullet that opens with a bold term ("- **The
payment.** Principal and interest..."), a bold term inside a paragraph ("**Padding** is..."), and
a section heading whose first paragraph is the definition. Each becomes an entry with the term, the
first sentence that carries it, and the line number, so a catalog entry can cite file and line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_BULLET = re.compile(r"^\s*-\s+\*\*(?P<term>[^*]+)\*\*\s*(?P<rest>.*)$")
_BOLD = re.compile(r"\*\*(?P<term>[^*]+)\*\*")
_HEADING = re.compile(r"^##\s+(?P<term>.+?)\s*$")
_SENTENCE_END = re.compile(r"(?<=[.;:])\s+(?=[A-Z(])")


@dataclass(frozen=True)
class Entry:
    term: str
    text: str
    line: int
    paragraph: str = ""


def _clean(text: str) -> str:
    text = text.replace("**", "").replace("`", "")
    return " ".join(text.split())


def first_sentence(text: str) -> str:
    text = _clean(text)
    parts = _SENTENCE_END.split(text, maxsplit=1)
    sentence = parts[0].strip()
    return sentence if sentence.endswith((".", ":", ";")) else sentence + "."


def _sentence_with(paragraph: str, term: str) -> str:
    clean = _clean(paragraph)
    for sentence in _SENTENCE_END.split(clean):
        if term.lower() in sentence.lower():
            return sentence.strip()
    return first_sentence(paragraph)


def parse(text: str) -> list[Entry]:
    lines = text.splitlines()
    out: list[Entry] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        heading = _HEADING.match(line)
        if heading:
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and not lines[j].lstrip().startswith(("#", "|", "```")):
                bullet = _BULLET.match(lines[j])
                body = bullet.group("rest") if bullet else lines[j]
                # A paragraph can wrap over several lines; read until a blank line.
                k = j + 1
                while (
                    not bullet
                    and k < len(lines)
                    and lines[k].strip()
                    and not lines[k].lstrip().startswith("-")
                ):
                    body += " " + lines[k]
                    k += 1
                out.append(Entry(heading.group("term"), first_sentence(body), j + 1, _clean(body)))
            i += 1
            continue
        bullet = _BULLET.match(line)
        if bullet:
            rest = bullet.group("rest")
            out.append(Entry(bullet.group("term").strip(), first_sentence(rest), i + 1, _clean(rest)))
            for bold in _BOLD.finditer(rest):
                out.append(
                    Entry(
                        bold.group("term").strip(),
                        _sentence_with(rest, bold.group("term")),
                        i + 1,
                        _clean(rest),
                    )
                )
        else:
            for bold in _BOLD.finditer(line):
                term = bold.group("term").strip()
                # The paragraph around the line, for the sentence that carries the term.
                start = i
                while start > 0 and lines[start - 1].strip():
                    start -= 1
                end = i
                while end + 1 < len(lines) and lines[end + 1].strip():
                    end += 1
                paragraph = " ".join(lines[start : end + 1])
                out.append(Entry(term, _sentence_with(paragraph, term), i + 1, _clean(paragraph)))
        i += 1
    return out


def by_term(entries: list[Entry]) -> dict[str, Entry]:
    found: dict[str, Entry] = {}
    for e in entries:
        found.setdefault(e.term, e)
    return found
