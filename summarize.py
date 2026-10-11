#!/usr/bin/env python3
"""Summarize the CLAUDE.md orientation A/B (see PROTOCOL.md). Reads results/*.json."""

from __future__ import annotations

import glob
import json
import os
import statistics
from pathlib import Path
from typing import Any

RESULTS = Path(__file__).resolve().parent / "results"


def payload_record(payload: Any) -> dict[str, Any]:
    """CLI 2.1.x emits a message list; telemetry is the last 'result' item."""
    if isinstance(payload, list):
        return next((item for item in reversed(payload) if item.get("type") == "result"), {})
    if isinstance(payload, dict):
        return payload
    return {}


def token_total(usage: dict[str, Any] | None) -> int:
    usage = usage or {}
    return (
        usage.get("input_tokens", 0)
        + usage.get("output_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
    )


def row_from_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "turns": record.get("num_turns"),
        "tokens": token_total(record.get("usage")),
        "cost": record.get("total_cost_usd"),
        "ms": record.get("duration_ms"),
        "answer": (record.get("result") or "")[:2000],
    }


def load_rows(results_dir: str | os.PathLike[str]) -> dict[str, dict[str, dict[str, Any]]]:
    rows: dict[str, dict[str, dict[str, Any]]] = {}
    for path in sorted(glob.glob(os.path.join(os.fspath(results_dir), "*.json"))):
        name = os.path.basename(path)[:-5]  # e.g. graph-guard-A
        repo, arm = name.rsplit("-", 1)
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
        rows.setdefault(repo, {})[arm] = row_from_record(payload_record(payload))
    return rows


def verdict(
    median_turns_a: float,
    median_turns_b: float,
    median_tokens_a: float,
    median_tokens_b: float,
) -> str:
    if median_turns_a < median_turns_b and median_tokens_a < median_tokens_b:
        return "MAPPED WINS"
    if median_turns_a > median_turns_b and median_tokens_a > median_tokens_b:
        return "MAPPED LOSES"
    return "MIXED"


def render(rows: dict[str, dict[str, dict[str, Any]]]) -> str:
    hdr = (
        f"{'repo':<24} {'A turns':>7} {'B turns':>7} {'A tokens':>9} "
        f"{'B tokens':>9} {'A $':>7} {'B $':>7}"
    )
    lines = [hdr, "-" * len(hdr)]
    turns_a: list[Any] = []
    turns_b: list[Any] = []
    tokens_a: list[int] = []
    tokens_b: list[int] = []
    for repo, arms in sorted(rows.items()):
        arm_a, arm_b = arms.get("A"), arms.get("B")
        if not (arm_a and arm_b):
            lines.append(f"{repo:<24} INCOMPLETE")
            continue
        turns_a.append(arm_a["turns"])
        turns_b.append(arm_b["turns"])
        tokens_a.append(arm_a["tokens"])
        tokens_b.append(arm_b["tokens"])
        lines.append(
            f"{repo:<24} {arm_a['turns']:>7} {arm_b['turns']:>7} "
            f"{arm_a['tokens']:>9,} {arm_b['tokens']:>9,} "
            f"{arm_a['cost']:>7.4f} {arm_b['cost']:>7.4f}"
        )
    if turns_a:
        lines.append("-" * len(hdr))
        median_turns_a, median_turns_b = statistics.median(turns_a), statistics.median(turns_b)
        median_tokens_a, median_tokens_b = statistics.median(tokens_a), statistics.median(tokens_b)
        lines.append(
            f"{'MEDIAN':<24} {median_turns_a:>7g} {median_turns_b:>7g} "
            f"{median_tokens_a:>9,.0f} {median_tokens_b:>9,.0f}"
        )
        lines.append("")
        lines.append(
            "Pre-registered decision rule verdict: "
            f"{verdict(median_turns_a, median_turns_b, median_tokens_a, median_tokens_b)}"
        )
        lines.append("(answers saved in results/*.json for the manual correctness spot-check)")
    return "\n".join(lines) + "\n"


def main() -> None:
    print(render(load_rows(RESULTS)), end="")


if __name__ == "__main__":
    main()
