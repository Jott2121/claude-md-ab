#!/usr/bin/env python3
"""Fail if the README's primary table drifts from results/*.json.

Re-derived here (the process exits 1 on disagreement):
- per-repo turns and tokens
- per-repo cost: the summarizer's 4-decimal display, half-up to 3 decimals
- median turns and median tokens, as summarize.py prints them
- mapped-arm win count on turns, tokens, and cost (the "6/6" headline)
- percent reductions from those printed medians
- the pre-registered verdict

Printed as UNVERIFIED and never asserted, because this repo does not contain
the inputs:
- ~190 tokens of map, and the 450:1 leverage ratio that divides by it
- capn-hook's 77% (related work, not a local measurement)
- the follow-up pilot: median token ratio 0.84, bar 0.50, 4/12 correctness
"""

from __future__ import annotations

import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from summarize import load_rows, render

UNVERIFIED = (
    "~190 tokens of map (the subject maps are not in this repo)",
    "450:1 leverage (saved tokens divided by that map size)",
    "77% fewer tokens (capn-hook's figure, cited as related work)",
    (
        "follow-up median token ratio 0.84, bar 0.50, and 4/12 correctness "
        "(that pilot's artifacts were not exported)"
    ),
)


def cost_to_readme(four_decimals: str) -> str:
    """README prints the summarizer's 4-decimal cost, half-up, at 3 decimals."""
    quantized = Decimal(four_decimals).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    return f"{quantized:.3f}"


def _percent_down(larger: float, smaller: float) -> int:
    return round((larger - smaller) / larger * 100)


def parse_render(text: str) -> tuple[dict[str, tuple[str, ...]], tuple[str, ...], str]:
    rows: dict[str, tuple[str, ...]] = {}
    median: tuple[str, ...] | None = None
    verdict_text: str | None = None
    for line in text.splitlines():
        if line.startswith("Pre-registered decision rule verdict: "):
            verdict_text = line.split(": ", 1)[1]
            continue
        if line.startswith("MEDIAN"):
            parts = line.split()
            median = (parts[1], parts[2], parts[3].replace(",", ""), parts[4].replace(",", ""))
            continue
        if not line.strip() or line.startswith(("repo", "-", "(")):
            continue
        if "INCOMPLETE" in line:
            continue
        parts = line.split()
        if len(parts) != 7:
            continue
        repo, turns_a, turns_b, tokens_a, tokens_b, cost_a, cost_b = parts
        rows[repo] = (
            turns_a,
            turns_b,
            tokens_a.replace(",", ""),
            tokens_b.replace(",", ""),
            cost_a,
            cost_b,
        )
    if median is None or verdict_text is None:
        raise RuntimeError("summarizer output has no median or verdict")
    return rows, median, verdict_text


def parse_readme_table(readme: str) -> tuple[dict[str, tuple[str, ...]], tuple[str, ...]]:
    rows: dict[str, tuple[str, ...]] = {}
    median: tuple[str, ...] | None = None
    in_table = False
    for line in readme.splitlines():
        if line.startswith("| repo |"):
            in_table = True
            continue
        if not in_table:
            continue
        if not line.startswith("|"):
            break
        if re.match(r"^\|\s*-+", line):
            continue
        cells = [
            cell.strip().strip("*").replace(",", "") for cell in line.strip().strip("|").split("|")
        ]
        cells = [cell.strip() for cell in cells]
        name = cells[0]
        if name.lower() == "median":
            median = (cells[1], cells[2], cells[3], cells[4])
        else:
            rows[name] = tuple(cells[1:7])
    if median is None:
        raise RuntimeError("README result table has no median row")
    return rows, median


def _win_count(results_dir: Path) -> tuple[int, int]:
    wins = 0
    total = 0
    for arms in load_rows(results_dir).values():
        arm_a, arm_b = arms.get("A"), arms.get("B")
        if not (arm_a and arm_b):
            continue
        total += 1
        if (
            arm_a["turns"] < arm_b["turns"]
            and arm_a["tokens"] < arm_b["tokens"]
            and arm_a["cost"] < arm_b["cost"]
        ):
            wins += 1
    return wins, total


def check(root: Path) -> list[str]:
    """Return human-readable drift messages. Empty means the verifiable numbers match."""
    readme = (root / "README.md").read_text(encoding="utf-8")
    rendered_rows, median, verdict_text = parse_render(render(load_rows(root / "results")))
    readme_rows, readme_median = parse_readme_table(readme)
    problems: list[str] = []

    if set(rendered_rows) != set(readme_rows):
        problems.append(
            f"repo set differs: results={sorted(rendered_rows)} readme={sorted(readme_rows)}"
        )

    for repo, rendered in sorted(rendered_rows.items()):
        published = readme_rows.get(repo)
        if published is None:
            continue
        labels = ("A turns", "B turns", "A tokens", "B tokens", "A $", "B $")
        expected = (
            rendered[0],
            rendered[1],
            rendered[2],
            rendered[3],
            cost_to_readme(rendered[4]),
            cost_to_readme(rendered[5]),
        )
        for label, got, want in zip(labels, published, expected, strict=True):
            if got != want:
                problems.append(f"{repo} {label}: README has {got}, results have {want}")

    for label, got, want in zip(
        ("A turns", "B turns", "A tokens", "B tokens"),
        readme_median,
        median,
        strict=True,
    ):
        if got != want:
            problems.append(f"median {label}: README has {got}, results have {want}")

    if f"**{verdict_text}.**" not in readme:
        problems.append(f"verdict {verdict_text} is not marked in the README")

    wins, total = _win_count(root / "results")
    headline = re.search(
        r"Across (\d+) repos, the mapped arm won (\d+)/(\d+) on turns, tokens, and cost",
        readme,
    )
    if headline is None:
        problems.append("headline win count sentence is missing")
    else:
        across, won, of = (int(headline.group(i)) for i in range(1, 4))
        if (across, won, of) != (total, wins, total):
            problems.append(
                f"headline says {across} repos, won {won}/{of}; results say {total} repos, won {wins}/{total}"
            )

    turn_pct = _percent_down(float(median[1]), float(median[0]))
    token_pct = _percent_down(int(median[3]), int(median[2]))
    token_phrase = re.search(r"median tokens down (\d+)%", readme)
    turn_phrase = re.search(r"median agent turns down (\d+)%", readme)
    if token_phrase is None or int(token_phrase.group(1)) != token_pct:
        problems.append(f"median tokens down {token_pct}% is not what the README says")
    if turn_phrase is None or int(turn_phrase.group(1)) != turn_pct:
        problems.append(f"median agent turns down {turn_pct}% is not what the README says")
    repeated = re.search(r"\(\d+% vs (\d+)%\)", readme)
    if repeated is not None and int(repeated.group(1)) != token_pct:
        problems.append(
            f"related-work comparison quotes {repeated.group(1)}% against our {token_pct}% token reduction"
        )
    return problems


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(args[0]).resolve() if args else ROOT
    problems = check(root)
    for item in UNVERIFIED:
        print(f"UNVERIFIED {item}")
    if problems:
        print("README drift:")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print("receipts ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
