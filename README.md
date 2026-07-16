# claude-md-ab

**A pre-registered A/B pilot: what is a verified CLAUDE.md worth to an AI coding agent?
Across 6 repos, the mapped arm won 6/6 on turns, tokens, and cost — median tokens down 68%,
median agent turns down 71% — against ~190 tokens of map. n=6, one run per cell: directional,
honest, and reproducible on your own repos in ~15 minutes.**

Agents are stateless between sessions. Every fresh session in a repo re-derives the same
context: what is this project, where do things live, how do I run the tests. That orientation
loop is an invisible tax — and [CLAUDE.md](https://docs.claude.com/en/docs/claude-code/memory)
files (small, verified, machine-readable project maps) are the cheapest fix that exists.
This repo measures the tax and the fix, with the experiment design locked **before** any run.

> 🧩 A measurement companion to the [cost-governance stack](https://github.com/Jott2121/bow#the-system-a-cost-governance-stack):
> [agent-cost-attribution](https://github.com/Jott2121/agent-cost-attribution) meters agentic
> workflows; this pilot isolates one lever — context files — and prices it.

## The result

Same agent (`claude -p`, sonnet, fixed prompt), same six repos, two arms: CLAUDE.md present
(A) vs temporarily hidden (B). Order alternated, no re-rolls, metrics read from the CLI's own
telemetry.

| repo | A turns | B turns | A tokens | B tokens | A $ | B $ |
|---|---|---|---|---|---|---|
| graph-guard | 1 | 2 | 40,370 | 81,952 | 0.114 | 0.139 |
| harness-v1 | 1 | 6 | 40,094 | 214,633 | 0.111 | 0.213 |
| hunt-prospector | 1 | 2 | 41,222 | 80,874 | 0.117 | 0.132 |
| metric-contracts-lab | 3 | 4 | 124,756 | 126,364 | 0.168 | 0.179 |
| nitro-ceo-agent | 2 | 3 | 81,340 | 125,197 | 0.134 | 0.170 |
| verent-engine | 1 | 5 | 40,435 | 213,364 | 0.115 | 0.205 |
| **median** | **1** | **3.5** | **40,828** | **125,780** | | |

Pre-registered decision rule (mapped must win BOTH medians): **MAPPED WINS.** The mapped arm
also won every individual repo on every measure. Worst unmapped cases burned 5x the tokens
rediscovering what the map states in one screen. Leverage: roughly **450:1** (tokens saved
per session vs tokens of map loaded).

## Honest limits — read before quoting

1. **n=6 repos, 1 run per cell.** Directional and consistent, not a precision estimate.
2. **The prompt is orientation-shaped** — the exact question maps exist to answer. Savings on
   deep implementation tasks will be smaller. This measures the per-session orientation tax.
3. One model (sonnet), one CLI version. Token totals include cache reads/writes.
4. The maps were **verified** (every fact checked against the repo before writing). A wrong
   map is worse than no map — this pilot says nothing in favor of unverified boilerplate.

## Related work

[capn-hook](https://github.com/CyrusNuevoDia/capn-hook) reaches the same diagnosis from the
product side — persistent memory for coding agents, with sha256 cache-busting — and its eval
measured **77% fewer tokens** on repeat questions (60 questions, 5 production codebases).
Convergent number, complementary layer: capn charts dynamic Q→files discoveries as the agent
works; a CLAUDE.md is the verified static top-of-repo layer (identity, entry points, run
commands, constraints). An agent plausibly wants both. Independent evals landing in the same
band (77% vs 68%) is the most useful kind of corroboration for an n=6 pilot.

**Follow-up (2026-07-16):** we then ran a second pre-registered pilot testing whether capn-style
dynamic memory adds value *on top of* verified maps, on this fleet's two deepest repos (12 fixed
questions, 2 arms, correctness judged against repo ground truth before any aggregate was
computed). Verdict under the locked decision rule: **killed.** Median token ratio 0.84 vs the
required 0.50, and 4/12 correctness violations in the memory arm — including one confidently
recalled wrong answer the cold arm got right. Two honest readings: at this fleet's repo scale,
verified maps already absorb most of the discovery tax; and none of this refutes capn-hook's own
77% on much larger codebases with no map baseline. Different layer, different niche — measure in
*your* setting before adopting either. We kill things the same way we ship them: with the
protocol written first and the number reported either way.

## Pre-registration

[`PROTOCOL.md`](PROTOCOL.md) — hypothesis, subjects, prompt, model, metrics, decision rule,
and exclusion rules — was written and committed before any run, in the private lab repo where
this experiment ran. The author wanted the mapped arm to win; pre-registration is the defense.
This public repo is a sanitized export: [`results/`](results/) keeps every run's full telemetry
and final answer, but the raw session transcripts are withheld because they embed file contents
read from private repos during the unmapped arm's exploration. Nothing about the numbers changed
in export; the summarizer reproduces the table above from the shipped artifacts.

## Run it on your own repos

Requires [Claude Code](https://docs.claude.com/en/docs/claude-code) (`claude` on PATH).

```bash
git clone https://github.com/Jott2121/claude-md-ab && cd claude-md-ab
./run_ab.sh ~/my-repo-1 ~/my-repo-2 ~/my-repo-3   # each needs a CLAUDE.md
python3 summarize.py                               # per-repo table + medians + verdict
```

Arm B hides each repo's CLAUDE.md only for the duration of its run; restoration is
trap-guaranteed plus a post-run sweep. `AB_MODEL=opus ./run_ab.sh ...` to change model.

## Files

- `PROTOCOL.md` — the pre-registered design (verbatim)
- `run_ab.sh` — the runner (12 headless `claude -p` calls for 6 repos)
- `summarize.py` — rebuilds the table and applies the decision rule
- `results/` — sanitized per-run artifacts: telemetry + final answer, one file per repo x arm

## License

MIT
