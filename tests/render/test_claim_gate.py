"""The claim gate: a document renders from the manifest, drift is caught, typed numbers are refused."""

from __future__ import annotations

from pathlib import Path

import pytest

from readback_core.manifest import ManifestBuilder
from readback_render.render import ClaimGateError, Renderer, Target, hand_typed_numbers
from readback_render.targets import discover, template_roots


def manifest():  # type: ignore[no-untyped-def]
    b = ManifestBuilder("2026-10-23")
    b.value("golden.questions", 150, "int", origin="evals", population="the golden set", source="golden")
    b.value("floor.accuracy", 0.7312, "pct1", origin="evals", population="the test split", source="floor")
    return b.build()


def repo(tmp_path: Path) -> Path:
    t = tmp_path / "docs" / "templates"
    t.mkdir(parents=True)
    (t / "README.md.j2").write_text("Questions: {{ v('golden.questions') }}, floor {{ v('floor.accuracy') }}.\n")
    (t / "_partial.md.j2").write_text("partial\n")
    return tmp_path


def test_renders_and_then_matches(tmp_path: Path) -> None:
    root = repo(tmp_path)
    r = Renderer(root, manifest(), discover(root), template_roots(root))
    r.write_all()
    assert (root / "README.md").read_text() == "Questions: 150, floor 73.1%.\n"
    assert r.check_all() == []


def test_a_hand_edit_is_drift(tmp_path: Path) -> None:
    root = repo(tmp_path)
    r = Renderer(root, manifest(), discover(root), template_roots(root))
    r.write_all()
    (root / "README.md").write_text("Questions: 151, floor 73.1%.\n")
    drifts = r.check_all()
    assert len(drifts) == 1 and "151" in drifts[0].diff


def test_partials_do_not_render(tmp_path: Path) -> None:
    root = repo(tmp_path)
    assert [t.output for t in discover(root)] == ["README.md"]


def test_typed_numbers_are_found_outside_expressions() -> None:
    assert hand_typed_numbers("We graded 150 questions {{ v('x') }}", []) == ["150"]
    assert hand_typed_numbers("At revision 2026-07-28 {{ v('x') }}", ["2026-07-28"]) == []


def test_refuses_nothing_to_render(tmp_path: Path) -> None:
    with pytest.raises(ClaimGateError, match="no documents"):
        Renderer(tmp_path, manifest(), [], [])


def test_refuses_an_empty_manifest(tmp_path: Path) -> None:
    with pytest.raises(ClaimGateError, match="empty manifest"):
        Renderer(tmp_path, ManifestBuilder("2026-10-23").build(), [Target("a.j2", "a")], [])


def test_a_missing_key_fails_the_render(tmp_path: Path) -> None:
    root = repo(tmp_path)
    (root / "docs/templates/README.md.j2").write_text("{{ v('not.there') }}\n")
    r = Renderer(root, manifest(), discover(root), template_roots(root))
    with pytest.raises(KeyError):
        r.write_all()
