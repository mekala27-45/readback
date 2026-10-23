"""The statement that appears on every surface.

Written once here. Every page of the site, every API and MCP response, every rendered document and
every answer reads it from this module, and a gate checks each surface for it verbatim.
"""

from __future__ import annotations

PROJECT = "readback"

STATEMENT = (
    "Answers are drawn from the published tables of three portfolio builds by Ajay Mekala: doorstep "
    "(public housing data from FHFA, the Census Bureau, HUD, the CFPB and Freddie Mac), turnaround "
    "(public flight data from the Bureau of Transportation Statistics, the FAA and OurAirports, with "
    "weather from Open-Meteo under CC BY 4.0) and ledger (a fictional bank, Harborline, with public "
    "HMDA, CFPB, FDIC and macro series). No person appears in any table, and questions are redacted "
    "before a model sees them. Every number is read back to the warehouse before it is shown. This is "
    "a portfolio demonstration, not financial, travel or lending advice."
)

REFUSAL = (
    "That is outside what readback can answer. It answers questions about the published tables of "
    "doorstep, turnaround and ledger, and never about an individual, a forecast or advice."
)


def statement_markdown() -> str:
    return f"> {STATEMENT}"


def statement_payload() -> dict[str, str]:
    return {"statement": STATEMENT}


def contains_statement(text: str) -> bool:
    flat = " ".join(text.split())
    return " ".join(STATEMENT.split()) in flat
