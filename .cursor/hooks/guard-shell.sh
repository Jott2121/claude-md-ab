#!/usr/bin/env bash
# beforeShellExecution guard. Reads {"command": "...", "cwd": "..."} on stdin.
# Denies irreversible / publishing commands; asks on network fetches. Fails closed (hooks.json failClosed: true).
# The matcher includes `git pull`, so `git pull --rebase` reaches the rebase deny arm.
# A plain `git pull` is allowed. A missing, blank, or non-string command is denied.
# Invalid JSON still exits non-zero (fail closed). See AGENTS.md.
set -euo pipefail
input="$(cat)"
cmd="$(printf '%s' "$input" | python3 -c 'import sys,json
data=json.load(sys.stdin)
cmd=data.get("command") if isinstance(data, dict) else None
sys.stdout.write(cmd if isinstance(cmd, str) else "")')"
deny() {
  python3 -c 'import json,sys; msg=sys.argv[1]; print(json.dumps({"permission":"deny","user_message":msg,"agent_message":msg+" Open a PR instead; a human will do this step."}))' "$1"
  exit 0
}
ask() {
  python3 -c 'import json,sys; print(json.dumps({"permission":"ask","user_message":sys.argv[1]}))' "$1"
  exit 0
}
if [ -z "${cmd//[[:space:]]/}" ]; then
  deny "Shell guard blocked a missing command."
fi
# Flags are not required to sit next to the subcommand: `git push origin --force`,
# `git push origin -f`, and `git reset HEAD --hard` are still denials. `push` and
# `reset` must be their own words, and `-f` its own short-option token, so a curl URL
# or an rm path that merely contains those letters is not a force-push.
push_word='(^|[[:space:]])push($|[[:space:]])'
reset_word='(^|[[:space:]])reset($|[[:space:]])'
force_short='(^|[[:space:]])-[A-Za-z]*f[A-Za-z]*($|[[:space:]])'
if [[ "$cmd" =~ $push_word && ( "$cmd" == *--force* || "$cmd" =~ $force_short ) ]]; then
  deny "Force-push blocked by repo policy."
fi
if [[ "$cmd" =~ $reset_word && "$cmd" == *--hard* ]]; then
  deny "History rewrite blocked by repo policy. This includes git pull --rebase."
fi
# SC2016: the $HOME arm matches the literal characters, not an expanded path.
# shellcheck disable=SC2016
case "$cmd" in
  *"rebase"*)                                         deny "History rewrite blocked by repo policy. This includes git pull --rebase." ;;
  *"git tag"*|*"twine upload"*|*"uv publish"*|*"gh release"*) deny "Releases/publishing are human-only." ;;
  *"rm -rf /"*|*"rm -rf ~"*|*'rm -rf $HOME'*)         deny "Destructive delete blocked." ;;
  *"curl"*"| sh"*|*"curl"*"| bash"*|*"wget"*"| sh"*)   deny "Pipe-to-shell blocked." ;;
  *"git push"*)                                       ask  "Agent wants to push a branch. Allow?" ;;
  *"curl"*|*"wget"*)                                  ask  "Agent wants network access: $cmd" ;;
esac
printf '{"permission":"allow"}\n'
