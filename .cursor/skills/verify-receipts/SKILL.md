---
name: verify-receipts
description: Use before opening or updating a PR, or when README/docs numbers change. Re-runs lint, tests, and the offline receipts check, cross-checks every recomputable published number, and writes a receipts block for the PR body.
---
# Verify receipts

This repo's primary table is recomputed from `results/*.json`. Do not run `./run_ab.sh` for this check: it calls the live `claude` CLI and renames `CLAUDE.md` in subject repos.

1. Read AGENTS.md "Commands". From the repo root run:
   - `python3 -m pip install -e ".[dev]"`
   - `ruff check . && ruff format --check .`
   - `python3 -m pytest -q --cov=summarize --cov=scripts --cov-report=term-missing --cov-fail-under=90`
   - `python3 scripts/check_receipts.py`
   - `shellcheck run_ab.sh .cursor/hooks/*.sh`
   Capture exit codes and the last ~20 lines of each.
2. `git diff origin/main -- README.md PROTOCOL.md` — list every number that changed. Re-run `python3 scripts/check_receipts.py`. If you can't reproduce a number the checker claims to cover, mark it UNVERIFIED and stop; do not open the PR as ready.
3. The checker prints these as UNVERIFIED. Keep them labeled that way in the PR. Do not invent a fixture so they "pass":
   - `~190` tokens of map, and the `450:1` leverage that depends on it
   - capn-hook's `77%`
   - follow-up pilot `0.84` vs `0.50`, and `4/12` correctness violations
4. Grep the diff for employer-data and secret patterns (see `.cursor/rules/40-security-and-data.mdc`). Any new hit outside the already-shipped `results/` answer text = stop and report. Do not edit historical `results/*.json` to scrub them.
5. Confirm no thresholds were lowered (`--cov-fail-under`, the one-retry bound in `run_ab.sh`) and no tests were skipped/removed.
6. Output a Markdown block:
   - Commands run + pass/fail
   - Numbers: before → after → command → reproduced? (Y/N)
   - Not verified / known gaps (the list in step 3, plus anything you did not run)
7. Paste that block into the PR's "How verified" section. Never claim a check passed that you didn't run.
