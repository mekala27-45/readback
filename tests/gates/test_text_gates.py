"""The three tests every gate has: a clean pass, a deliberate violation, and a refusal over nothing."""

from __future__ import annotations

from pathlib import Path

import pytest
from readback_core.statements import STATEMENT

from scripts import check_no_em_dash, check_statement, check_vocabulary, scan_for_planted_identifiers


def test_dash_gate_passes_clean_text(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text("Ranges use to, asides use commas.\n", encoding="utf-8")
    assert check_no_em_dash.check(tmp_path, [f]) == 1


def test_dash_gate_catches_an_em_dash(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text("one " + chr(0x2014) + " two\n", encoding="utf-8")
    with pytest.raises(ValueError, match="em dash"):
        check_no_em_dash.check(tmp_path, [f])


def test_dash_gate_refuses_nothing(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no files"):
        check_no_em_dash.check(tmp_path, [])


def test_vocabulary_gate_passes_plain_text(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text("The gate reads every number back.\n", encoding="utf-8")
    assert check_vocabulary.check(tmp_path, [f]) == 1


def test_vocabulary_gate_catches_a_banned_phrase(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text("We " + "lever" + "age the warehouse.\n", encoding="utf-8")
    with pytest.raises(ValueError, match="vocabulary"):
        check_vocabulary.check(tmp_path, [f])


def test_vocabulary_gate_refuses_nothing(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no files"):
        check_vocabulary.check(tmp_path, [])


def test_statement_gate_passes_a_surface_with_it(tmp_path: Path) -> None:
    f = tmp_path / "README.md"
    f.write_text("# x\n\n> " + STATEMENT + "\n", encoding="utf-8")
    assert check_statement.check(tmp_path, [f]) == 1


def test_statement_gate_catches_a_missing_statement(tmp_path: Path) -> None:
    f = tmp_path / "README.md"
    f.write_text("# x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing the statement"):
        check_statement.check(tmp_path, [f])


def test_statement_gate_refuses_nothing(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no surfaces"):
        check_statement.check(tmp_path, [])


def test_identifier_scan_passes_clean_text(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text("Metro 35620 had a payment share of 0.41.\n", encoding="utf-8")
    assert scan_for_planted_identifiers.check(tmp_path, [f], planted=set()) == 1


def test_identifier_scan_catches_an_email_a_card_and_a_planted_token(tmp_path: Path) -> None:
    f = tmp_path / "a.md"
    f.write_text("mail jane.doe@gmail.com card 4111 1111 1111 1111 acct ZZ-PLANTED-77\n", encoding="utf-8")
    with pytest.raises(ValueError) as err:
        scan_for_planted_identifiers.check(tmp_path, [f], planted={"zz-planted-77"})
    text = str(err.value)
    assert "email" in text and "card number" in text and "planted identifier" in text


def test_identifier_scan_catches_a_phone_number_in_the_answer_log(tmp_path: Path) -> None:
    log = tmp_path / "results" / "answers"
    log.mkdir(parents=True)
    f = log / "a.json"
    f.write_text('{"question": "call me at 201-555-0143"}', encoding="utf-8")
    with pytest.raises(ValueError, match="phone number"):
        scan_for_planted_identifiers.check(tmp_path, [f], planted=set())


def test_identifier_scan_skips_nanosecond_timestamps_but_not_the_same_digits_elsewhere(
    tmp_path: Path,
) -> None:
    luhn = "4111111111111111"
    clean = tmp_path / "spans.json"
    clean.write_text(f'{{"spans": [{{"start_ns": {luhn}, "name": "chat"}}]}}', encoding="utf-8")
    assert scan_for_planted_identifiers.check(tmp_path, [clean], planted=set()) == 1
    dirty = tmp_path / "rows.json"
    dirty.write_text(f'{{"rows": [{{"account": {luhn}}}]}}', encoding="utf-8")
    with pytest.raises(ValueError, match="card number"):
        scan_for_planted_identifiers.check(tmp_path, [dirty], planted=set())


def test_identifier_scan_refuses_nothing(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no files"):
        scan_for_planted_identifiers.check(tmp_path, [], planted=set())
