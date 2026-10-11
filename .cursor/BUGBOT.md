# .cursor/BUGBOT.md — review rules for claude-md-ab
# (Bugbot does NOT read .cursor/rules/*.mdc; it reads this file.)

Flag as **blocking**:
1. Any guard, gate, validator, or refusal path that now fails OPEN (returns allow/True/answer on exception, timeout, empty, or malformed input). The shell guard must keep denying `git pull --rebase` (the `rebase` pattern).
2. Lowered thresholds: `--cov-fail-under`, mutation score floors, MIN_SCORE-style constants, retry/timeout bounds removed. `run_ab.sh` retries a failed cell once; do not raise that or drop the second-failure `dropped` marker.
3. Tests that were deleted, skipped, xfailed, or had assertions weakened without a stated reason in the PR body.
4. README/docs numbers that changed without a reproducing command or artifact in the PR. `results/*.json` are raw run outputs: do not edit them to chase a README figure.
5. Any content that looks like employer/corporate data: employer names or abbreviations, internal acronyms, CUI/ITAR markings, real-looking employee records, internal URLs. This repo is personal work only. Do not copy the historical answer text out of `results/` into new fixtures. Also blocking: any change that removes `.github/blocked-terms.sha256`, empties it, makes `scripts/scan_blocked_terms.py` pass when it is missing, or adds an exclusion for a data folder such as `results/`.
6. Secrets, tokens, `.env` files, or absolute personal paths committed.
7. Unpinned GitHub Actions (must be full SHA) or widened workflow `permissions:`.
8. Live network / model calls added to the default test path. `./run_ab.sh` invokes the real `claude` CLI; tests must keep using a fake on `PATH`.
9. A check that "verifies" the ~190 map tokens, the 450:1 leverage, capn-hook's 77%, or the follow-up 0.84 / 4/12 figures by hardcoding them. Those inputs are not in this repo.

Flag as **non-blocking**:
- New runtime dependency without justification. The summarizer is stdlib-only.
- Non-deterministic code in eval paths (unseeded RNG, unordered iteration in hashes/output).
- Exceptions swallowed in non-decision code.

Do not comment on: formatting handled by ruff; naming bikesheds.
