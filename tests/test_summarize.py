"""Core summarizer behavior. The shipped results must keep printing the same table."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from summarize import (
    load_rows,
    main,
    payload_record,
    render,
    row_from_record,
    token_total,
    verdict,
)

ROOT = Path(__file__).resolve().parents[1]

# Byte-for-byte stdout of summarize.py against the committed results/, captured
# before the importable refactor. This is the behavior lock.
SHIPPED_STDOUT = """\
repo                     A turns B turns  A tokens  B tokens     A $     B $
----------------------------------------------------------------------------
graph-guard                    1       2    40,370    81,952  0.1141  0.1394
harness-v1                     1       6    40,094   214,633  0.1112  0.2134
hunt-prospector                1       2    41,222    80,874  0.1173  0.1323
metric-contracts-lab           3       4   124,756   126,364  0.1675  0.1788
nitro-ceo-agent                2       3    81,340   125,197  0.1339  0.1701
verent-engine                  1       5    40,435   213,364  0.1149  0.2054
----------------------------------------------------------------------------
MEDIAN                         1     3.5    40,828   125,780

Pre-registered decision rule verdict: MAPPED WINS
(answers saved in results/*.json for the manual correctness spot-check)
"""


def test_shipped_results_render_matches_locked_stdout() -> None:
    assert render(load_rows(ROOT / "results")) == SHIPPED_STDOUT


def test_cli_stdout_matches_library(capsys: pytest.CaptureFixture[str]) -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "summarize.py")],
        check=True,
        capture_output=True,
        text=True,
    )
    assert proc.stdout == SHIPPED_STDOUT
    assert capsys.readouterr().out == ""


def test_token_total_sums_the_four_telemetry_fields_only() -> None:
    usage = {
        "input_tokens": 2,
        "output_tokens": 403,
        "cache_creation_input_tokens": 16846,
        "cache_read_input_tokens": 23119,
        "server_tool_use": {"web_search_requests": 5},
    }
    assert token_total(usage) == 40370
    assert token_total({}) == 0
    assert token_total(None) == 0


def test_list_payload_uses_the_last_result_message() -> None:
    payload = [
        {"type": "assistant", "num_turns": 9, "usage": {"input_tokens": 999}},
        {
            "type": "result",
            "num_turns": 1,
            "usage": {"input_tokens": 1, "output_tokens": 1},
            "total_cost_usd": 0.2,
            "result": "first",
        },
        {
            "type": "result",
            "num_turns": 4,
            "usage": {"input_tokens": 3, "output_tokens": 4},
            "total_cost_usd": 1.5,
            "duration_ms": 8,
            "result": "x" * 2001,
        },
    ]
    record = payload_record(payload)
    row = row_from_record(record)
    assert row["turns"] == 4
    assert row["tokens"] == 7
    assert row["cost"] == 1.5
    assert row["ms"] == 8
    assert row["answer"] == "x" * 2000


def test_non_object_payload_is_empty() -> None:
    assert payload_record("nope") == {}
    assert payload_record(None) == {}


def test_main_prints_the_shipped_table(capsys: pytest.CaptureFixture[str]) -> None:
    main()
    assert capsys.readouterr().out == SHIPPED_STDOUT


def test_missing_result_message_is_an_empty_record() -> None:
    row = row_from_record(payload_record([{"type": "assistant"}]))
    assert row["turns"] is None
    assert row["tokens"] == 0
    assert row["answer"] == ""


def test_object_payload_is_used_directly() -> None:
    row = row_from_record(
        payload_record({"num_turns": 2, "usage": {"output_tokens": 5}, "result": None})
    )
    assert row["turns"] == 2
    assert row["tokens"] == 5
    assert row["answer"] == ""


def test_incomplete_pair_is_excluded_from_the_verdict(tmp_path: Path) -> None:
    _write(tmp_path, "alpha-A", turns=1, tokens=10, cost=0.1)
    text = render(load_rows(tmp_path))
    assert "alpha" in text and "INCOMPLETE" in text
    assert "MEDIAN" not in text
    assert "verdict" not in text


def test_decision_rule_wins_loses_and_mixed(tmp_path: Path) -> None:
    assert verdict(1, 3.5, 10, 20) == "MAPPED WINS"
    assert verdict(5, 1, 20, 10) == "MAPPED LOSES"
    assert verdict(1, 3, 30, 10) == "MIXED"
    assert verdict(2, 2, 10, 11) == "MIXED"

    _write(tmp_path, "alpha-A", turns=5, tokens=50, cost=0.5)
    _write(tmp_path, "alpha-B", turns=1, tokens=10, cost=0.1)
    text = render(load_rows(tmp_path))
    assert "MAPPED LOSES" in text
    assert "MEDIAN" in text


def test_even_count_median_matches_shipped_rounding(tmp_path: Path) -> None:
    # Same even-n median the shipped six-repo token columns hit (.5 rounds to even).
    for name, turns, tokens in (
        ("a-A", 1, 1),
        ("a-B", 2, 2),
        ("b-A", 1, 2),
        ("b-B", 2, 3),
    ):
        _write(tmp_path, name, turns=turns, tokens=tokens, cost=0.1)
    text = render(load_rows(tmp_path))
    median_line = next(line for line in text.splitlines() if line.startswith("MEDIAN"))
    # 1.5 and 2.5 both format with .0f by round-half-to-even, so both token medians print as 2.
    assert median_line.split() == ["MEDIAN", "1", "2", "2", "2"]


def test_hyphenless_filename_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "noarm.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        load_rows(tmp_path)


def test_malformed_json_raises(tmp_path: Path) -> None:
    (tmp_path / "repo-A.json").write_text("{", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_rows(tmp_path)


def _write(directory: Path, stem: str, *, turns: int, tokens: int, cost: float) -> None:
    payload = {
        "num_turns": turns,
        "usage": {"input_tokens": tokens},
        "total_cost_usd": cost,
        "duration_ms": 1,
        "result": "ok",
    }
    (directory / f"{stem}.json").write_text(json.dumps(payload), encoding="utf-8")
