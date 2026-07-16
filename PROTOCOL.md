# CLAUDE.md orientation A/B — pre-registered protocol

Written and committed BEFORE any run. If a later commit changes this file, the diff is the
record of what moved. Author wants the mapped arm to win; pre-registration is the defense.

## Claim under test

H1: A fresh headless Claude Code session answering a fixed orientation question inside a
repo that has a verified CLAUDE.md map uses fewer agent turns and fewer tokens than the
same session in the same repo with the map hidden.

## Design

- Subjects (fixed, chosen before any run): graph-guard, harness-v1, nitro-ceo-agent,
  hunt-prospector, metric-contracts-lab, verent-engine (Documents). Chosen for variety of
  size/type; no live-money repos.
- Arms: A = CLAUDE.md present (as shipped 2026-07-15). B = CLAUDE.md temporarily renamed
  to CLAUDE.md.ab-hidden for the run, restored immediately after (trap-guaranteed).
- Runs: 6 repos x 2 arms x 1 run = 12 headless `claude -p` calls. No re-rolls: the first
  completed run per cell is the run, even if unflattering.
- Order: repos 1,3,5 (graph-guard, nitro-ceo-agent, metric-contracts-lab) run A then B;
  repos 2,4,6 run B then A.
- Fixed prompt (identical every run):
  "Orient yourself in this repository: state what this project is, its main entry points,
  and the exact command to run its tests. Keep the answer under 120 words."
- Model pinned: sonnet. --max-turns 12. Default permission mode (read-only tools allowed;
  anything needing permission is denied equally in both arms).
- Constant in both arms: the user's global ~/.claude/CLAUDE.md loads either way.

## Metrics (primary, from the CLI's own JSON telemetry)

1. num_turns
2. total tokens = input + output + cache_creation + cache_read
3. total_cost_usd as reported
4. duration_ms (secondary; wall time is noisy)

Answers are saved verbatim to results/ for a manual correctness spot-check by Jeff
(does the stated test command actually work?). Correctness is reported but is NOT a
primary metric in this pilot.

## Decision rule (fixed in advance)

Mapped arm WINS if median num_turns AND median total tokens across the 6 repos are both
lower in arm A. Mixed result = report honestly as mixed. If arm A loses both medians,
the maps' token claim is refuted and the receipt says so.

## Exclusions

A run that errors (nonzero exit / no JSON) is retried once; if it errors again the repo
is dropped from both arms and reported as dropped.
