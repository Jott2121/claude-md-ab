#!/bin/bash
# CLAUDE.md orientation A/B runner. See PROTOCOL.md for the pre-registered design.
#
# Usage:  ./run_ab.sh <repo-dir> [<repo-dir> ...]
# Each repo must contain a CLAUDE.md (arm A = present, arm B = temporarily hidden).
# Results land in ./results/ as <repo>-A.json / <repo>-B.json; then: python3 summarize.py
set -u
OUT="$(cd "$(dirname "$0")" && pwd)/results"
mkdir -p "$OUT"
PROMPT="Orient yourself in this repository: state what this project is, its main entry points, and the exact command to run its tests. Keep the answer under 120 words."
MODEL="${AB_MODEL:-sonnet}"

if [ $# -lt 1 ]; then echo "usage: $0 <repo-dir> [<repo-dir> ...]" >&2; exit 2; fi
REPOS=("$@")
for r in "${REPOS[@]}"; do
  [ -f "$r/CLAUDE.md" ] || { echo "SKIP $r: no CLAUDE.md (both arms need one to exist)" >&2; exit 2; }
done

CURRENT_HIDDEN=""
restore() {
  if [ -n "$CURRENT_HIDDEN" ] && [ -f "$CURRENT_HIDDEN/CLAUDE.md.ab-hidden" ]; then
    mv "$CURRENT_HIDDEN/CLAUDE.md.ab-hidden" "$CURRENT_HIDDEN/CLAUDE.md"
    echo "[restore-on-exit] restored map in $CURRENT_HIDDEN"
  fi
}
trap restore EXIT

run_one() { # $1=repo $2=arm(A|B)
  local repo="$1" arm="$2"
  local name; name=$(basename "$repo")
  local f="$OUT/${name}-${arm}.json"
  echo "== $name arm $arm =="
  if [ "$arm" = "B" ]; then
    CURRENT_HIDDEN="$repo"
    mv "$repo/CLAUDE.md" "$repo/CLAUDE.md.ab-hidden"
  fi
  ( cd "$repo" && claude -p "$PROMPT" --model "$MODEL" --max-turns 12 --output-format json > "$f" 2>"$OUT/${name}-${arm}.err" )
  local rc=$?
  if [ "$arm" = "B" ]; then
    mv "$repo/CLAUDE.md.ab-hidden" "$repo/CLAUDE.md"
    CURRENT_HIDDEN=""
  fi
  if [ $rc -ne 0 ] || [ ! -s "$f" ]; then
    echo "   RETRY (rc=$rc)"
    if [ "$arm" = "B" ]; then CURRENT_HIDDEN="$repo"; mv "$repo/CLAUDE.md" "$repo/CLAUDE.md.ab-hidden"; fi
    ( cd "$repo" && claude -p "$PROMPT" --model "$MODEL" --max-turns 12 --output-format json > "$f" 2>"$OUT/${name}-${arm}.err" )
    rc=$?
    if [ "$arm" = "B" ]; then mv "$repo/CLAUDE.md.ab-hidden" "$repo/CLAUDE.md"; CURRENT_HIDDEN=""; fi
    [ $rc -ne 0 ] && echo "   DROPPED (rc=$rc twice)" && echo "dropped" > "$OUT/${name}-${arm}.dropped"
  fi
  echo "   done rc=$rc"
}

i=0
for repo in "${REPOS[@]}"; do
  if [ $((i % 2)) -eq 0 ]; then
    run_one "$repo" A; run_one "$repo" B
  else
    run_one "$repo" B; run_one "$repo" A
  fi
  i=$((i+1))
done

# Post-run safety sweep: every subject must have its map back.
for repo in "${REPOS[@]}"; do
  if [ ! -f "$repo/CLAUDE.md" ]; then
    [ -f "$repo/CLAUDE.md.ab-hidden" ] && mv "$repo/CLAUDE.md.ab-hidden" "$repo/CLAUDE.md" && echo "[sweep] restored $repo"
    [ -f "$repo/CLAUDE.md" ] || echo "[sweep] WARNING: map missing in $repo"
  fi
done
echo "ALL RUNS COMPLETE — now: python3 summarize.py"
