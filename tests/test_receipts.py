"""Receipts checker: README primary numbers must match results/*.json.

Numbers the artifacts cannot support must not become assertions.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.check_receipts import (
    UNVERIFIED,
    check,
    cost_to_readme,
    main,
    parse_readme_table,
    parse_render,
)
from summarize import load_rows, render

ROOT = Path(__file__).resolve().parents[1]


def _copy_repo(tmp_path: Path) -> Path:
    shutil.copy(ROOT / "README.md", tmp_path / "README.md")
    shutil.copy(ROOT / "summarize.py", tmp_path / "summarize.py")
    results = tmp_path / "results"
    results.mkdir()
    for path in (ROOT / "results").glob("*.json"):
        shutil.copy(path, results / path.name)
    return tmp_path


def test_shipped_readme_matches_results() -> None:
    assert check(ROOT) == []


def test_cli_exits_zero_and_names_unverifiable_numbers() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_receipts.py")],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "receipts ok" in proc.stdout
    for item in UNVERIFIED:
        assert item.split()[0] in proc.stdout
    assert "UNVERIFIED" in proc.stdout


def test_main_accepts_an_explicit_root() -> None:
    assert main([str(ROOT)]) == 0


def test_token_drift_fails(tmp_path: Path) -> None:
    root = _copy_repo(tmp_path)
    readme = root / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8").replace("40,370", "40,371", 1), encoding="utf-8"
    )
    problems = check(root)
    assert problems
    assert any("graph-guard" in problem and "tokens" in problem for problem in problems)
    assert main([str(root)]) == 1


def test_headline_percent_drift_fails(tmp_path: Path) -> None:
    root = _copy_repo(tmp_path)
    readme = root / "README.md"
    text = readme.read_text(encoding="utf-8").replace(
        "median tokens down 68%", "median tokens down 90%", 1
    )
    readme.write_text(text, encoding="utf-8")
    problems = check(root)
    assert any("68" in problem for problem in problems)


def test_readme_cost_rounds_half_up_from_the_four_decimal_display() -> None:
    assert cost_to_readme("0.1675") == "0.168"
    assert cost_to_readme("0.1141") == "0.114"
    assert cost_to_readme("0.1701") == "0.170"


def test_parser_skips_incomplete_rows_and_rejects_a_headless_report() -> None:
    rows, _median, verdict_text = parse_render(
        "partial                  INCOMPLETE\nnot a data row\n"
        + render(load_rows(ROOT / "results"))
    )
    assert "graph-guard" in rows
    assert verdict_text == "MAPPED WINS"
    with pytest.raises(RuntimeError):
        parse_render("no median here\n")
    with pytest.raises(RuntimeError):
        parse_readme_table("| repo | A turns |\n| --- | --- |\n| only | 1 |\n")


def test_result_repo_absent_from_the_readme_is_reported(tmp_path: Path) -> None:
    root = _copy_repo(tmp_path)
    for arm in ("A", "B"):
        shutil.copy(
            root / "results" / f"graph-guard-{arm}.json",
            root / "results" / f"extra-repo-{arm}.json",
        )
    problems = check(root)
    assert any("extra-repo" in problem for problem in problems)


def test_missing_arm_incomplete_pair_and_repo_drift(tmp_path: Path) -> None:
    root = _copy_repo(tmp_path)
    (root / "results" / "graph-guard-A.json").unlink()
    problems = check(root)
    assert any("repo set differs" in problem for problem in problems)
    assert any("graph-guard" in problem for problem in problems)


def test_headline_median_verdict_and_repeated_percent_drift(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _copy_repo(tmp_path)
    readme = root / "README.md"
    text = readme.read_text(encoding="utf-8")
    text = text.replace("**MAPPED WINS.**", "**MIXED.**", 1)
    text = text.replace(
        "| **median** | **1** | **3.5** | **40,828** | **125,780** | | |",
        "| **median** | **9** | **3.5** | **40,828** | **125,780** | | |",
        1,
    )
    text = text.replace(
        "Across 6 repos, the mapped arm won 6/6 on turns, tokens, and cost",
        "Across 6 repos, the mapped arm won 1/6 on turns, tokens, and cost",
        1,
    )
    text = text.replace("median agent turns down 71%", "median agent turns down 10%", 1)
    text = text.replace("(77% vs 68%)", "(77% vs 10%)", 1)
    readme.write_text(text, encoding="utf-8")
    problems = check(root)
    joined = "\n".join(problems)
    assert "verdict" in joined
    assert "median A turns" in joined
    assert "headline says" in joined
    assert "median agent turns down" in joined
    assert "related-work" in joined
    assert main([str(root)]) == 1
    assert "README drift:" in capsys.readouterr().out


def test_missing_headline_sentences_are_reported(tmp_path: Path) -> None:
    root = _copy_repo(tmp_path)
    readme = root / "README.md"
    text = readme.read_text(encoding="utf-8")
    text = text.replace(
        "Across 6 repos, the mapped arm won 6/6 on turns, tokens, and cost",
        "Across several repos the mapped arm won",
        1,
    )
    text = text.replace("median tokens down 68%", "tokens moved", 1)
    text = text.replace("median agent turns down 71%", "turns moved", 1)
    readme.write_text(text, encoding="utf-8")
    joined = "\n".join(check(root))
    assert "headline win count sentence is missing" in joined
    assert "median tokens down" in joined
    assert "median agent turns down" in joined


def test_unverifiable_numbers_are_not_gated(tmp_path: Path) -> None:
    """Changing a figure the artifacts cannot re-derive must not fail the check."""
    root = _copy_repo(tmp_path)
    readme = root / "README.md"
    text = readme.read_text(encoding="utf-8")
    text = text.replace("~190 tokens", "~999 tokens", 1)
    text = text.replace("450:1", "999:1", 1)
    text = text.replace("77% fewer tokens", "12% fewer tokens", 1)
    text = text.replace("Median token ratio 0.84", "Median token ratio 0.11", 1)
    text = text.replace("4/12 correctness", "9/12 correctness", 1)
    readme.write_text(text, encoding="utf-8")
    assert check(root) == []
