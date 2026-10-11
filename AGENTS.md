# AGENTS.md — claude-md-ab

> Portable agent instructions. Read by Cursor (local + cloud agents), Claude Code, Codex, and Grok Bot cloud-agent runs.
> Keep this file under ~150 lines. Procedures live in `.cursor/skills/`. Scoped rules live in `.cursor/rules/*.mdc`. Review rules live in `.cursor/BUGBOT.md`.

## What this repo is

A finished, pre-registered A/B pilot: does a verified CLAUDE.md map reduce turns and tokens for one fixed orientation prompt? Six repos, one headless `claude -p` run per cell (map present vs hidden). From the committed telemetry, the mapped arm won 6/6 on turns, tokens, and cost; median tokens down 68%; median turns down 71%. Reprint the table with `python3 summarize.py`. This directory is a sanitized public export. Raw transcripts are withheld.

- **Status:** experiment (pilot complete, results frozen) · **License:** MIT · **Package:** n/a (stdlib script; not published)
- **Entry points:** `summarize.py`, `run_ab.sh`, `scripts/check_receipts.py`, `tests/`, `results/`, `PROTOCOL.md`
- **Part of:** the governed-agent stack (rag-guard · graph-guard · agent-gate · crucible · oracle-gate · agent-cost-attribution · bow · fleet-mode). Measurement companion, not a library.

## Commands

```bash
python3 -m pip install -e ".[dev]"   # pytest, pytest-cov, ruff; no runtime deps
ruff check . && ruff format --check .
# typecheck: n/a
python3 -m pytest -q --cov=summarize --cov=scripts --cov-report=term-missing --cov-fail-under=90
python3 summarize.py                 # reprint the table from results/*.json
python3 scripts/check_receipts.py    # fail if recomputable README numbers drift
shellcheck run_ab.sh .cursor/hooks/*.sh
```

Do not run `./run_ab.sh` in CI or as a default check. It shells out to the real `claude` CLI and renames `CLAUDE.md` inside subject repos. Tests copy the script and put a fake `claude` on `PATH`.

A task is not done until lint + tests pass and the output is pasted in the PR.

## Non-negotiables

1. **No employer data. Ever.** Personal work on personal equipment. Never add, paste, paraphrase, or "anonymize" anything from Lockheed Martin systems, documents, tickets, chats, or datasets. No employer names in fixtures, no internal acronyms, no realistic HR records. Synthetic data only. If a prompt looks like it came from work, stop and ask.
2. **Receipts over hype.** Every number in README, docs, PR descriptions, or posts must be reproducible from a committed command, or explicitly marked unverified. Link the command and the artifact (`results/`, CI log).
3. **Honest benchmarks.** Report nulls and regressions at the same prominence as wins. State n, model, and cost. The decision rule is `PROTOCOL.md`, committed before the runs. Never tune on the test set. Never delete an inconvenient run; mark it superseded with a reason.
4. **Fail closed.** Gates and guards deny on error, timeout, missing input, or unparseable output. Never weaken a guard to make a test pass. Never catch-and-ignore exceptions in a decision path.
5. **Tests and CI are the definition of done.** New behavior ships with a test that fails without it. Bug fixes ship with a regression test. Do not lower `--cov-fail-under`. Do not mark tests `skip`/`xfail` to get green.
6. **Model never grades its own output.** Prefer mechanical verdicts (the summarizer's decision rule, schema checks). Do not add a judge model to score these runs.
7. **Irreversible = human-gated.** No force-push, no history rewrite, no publishing, no tagging releases, no posting. Open a PR; a human merges.

## Code style

- Python 3.11+; stdlib-only on `summarize.py` and `scripts/check_receipts.py`. A new runtime dependency needs a one-line justification in the PR.
- Type hints on public functions. Small pure functions. No global mutable state.
- Errors: raise specific exceptions; no bare `except`.
- Secrets only via env vars. `AB_MODEL` selects the live runner's model. Tests never call a live model.
- Don't commit build output: `__pycache__/`, `*.pyc`, `.coverage`, `.venv/`, `.cursor/hook-logs/`.

## How to work in this repo

- Start non-trivial work in Plan mode; save the plan to `.cursor/plans/` and link it in the PR.
- Default to one agent. Fan out only for read-heavy, independent work. Writes stay single-threaded per file.
- Keep PRs small (< ~400 changed lines) with one intent. Title: `type(scope): summary`.
- PR body must include: **What / Why / How verified (commands + output) / Numbers changed (before → after, with command) / Risks / Not done**.
- When you learn something durable about this repo, propose an edit to this file or a skill in the same PR.

## Directory map

```
summarize.py    reprint the table and the pre-registered verdict from results/*.json
run_ab.sh       headless A/B runner (needs the claude CLI; not used in CI)
PROTOCOL.md     pre-registered design
results/        sanitized telemetry + final answer, one JSON per repo x arm
scripts/        check_receipts.py — README drift gate (stdlib)
tests/          offline tests; fake claude; no network
.cursor/        rules, hooks, Bugbot, MCP, verify-receipts skill
.github/        CI, CodeQL, Dependabot
```

## Known traps

- The beforeShellExecution guard denies any command whose text contains `rebase`, so **`git pull --rebase` is blocked** along with `git rebase`. The `hooks.json` matcher includes `git pull` and `git rebase`, so a rebasing pull actually reaches the script. A plain `git pull` is allowed. A missing, blank, or non-string `command` is denied; invalid JSON still exits non-zero. History rewrites are human-only. Fetch and merge, or ask a human. Do not loosen the guard to unblock yourself.
- `run_ab.sh` writes `results/` next to the script and hides `CLAUDE.md` for arm B. A trap plus a post-run sweep restore it. Tests run a copy under a temp directory so the committed `results/` stay untouched.
- Do not edit `results/*.json`. One saved answer names an employer because that subject repo described itself that way; leave the artifact alone and do not copy it into fixtures. The employer-name CI grep skips `results/` for that reason. Export-control markers are still scanned there.
- README costs are the summarizer's 4-decimal figures, half-up to 3 decimals. `summarize.py` prints 4 decimals.
- `check_receipts.py` does **not** recompute `~190` map tokens, the `450:1` leverage, capn-hook's `77%`, or the follow-up pilot (`0.84` vs `0.50`, `4/12`). Those inputs are not in this repo. Say so when citing them.
- There is no `CLAUDE.md` here on purpose. Adding one would make this repo a legal subject of its own runner. Agent instructions live in this file.
- `.cursor/rules/60-grok-integration.mdc` is omitted: nothing here calls the xAI API. `worktrees.json` is omitted: install dev extras with pip, not uv.
