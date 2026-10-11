"""Runner behavior with a fake claude binary. No network and no live model."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPT = (
    "Orient yourself in this repository: state what this project is, its main entry points, "
    "and the exact command to run its tests. Keep the answer under 120 words."
)


def _install_runner(tmp_path: Path) -> Path:
    script = tmp_path / "run_ab.sh"
    shutil.copy(ROOT / "run_ab.sh", script)
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


def _install_claude(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "claude"
    fake.write_text(
        textwrap.dedent(
            """\
            #!/usr/bin/env python3
            import json, os, sys
            from pathlib import Path
            log = Path(os.environ["CLAUDE_FAKE_LOG"])
            cwd = Path.cwd()
            with log.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "repo": cwd.name,
                    "present": (cwd / "CLAUDE.md").is_file(),
                    "args": sys.argv[1:],
                }) + "\\n")
            fails = cwd / ".fail_remaining"
            if fails.is_file():
                left = int(fails.read_text() or "0")
                if left > 0:
                    fails.write_text(str(left - 1))
                    sys.exit(1)
            if (cwd / ".silent_once").is_file():
                (cwd / ".silent_once").unlink()
                sys.exit(0)
            print(json.dumps({
                "num_turns": 1,
                "usage": {"input_tokens": 1, "output_tokens": 1},
                "total_cost_usd": 0.01,
                "duration_ms": 1,
                "result": "ok",
            }))
            """
        ),
        encoding="utf-8",
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    return bin_dir


def _repo(parent: Path, name: str) -> Path:
    repo = parent / name
    repo.mkdir()
    (repo / "CLAUDE.md").write_text(f"# {name}\n", encoding="utf-8")
    return repo


def _run(
    script: Path,
    repos: list[Path],
    bin_dir: Path,
    log: Path,
    env_extra: dict[str, str] | None = None,
):
    env = os.environ.copy()
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env["CLAUDE_FAKE_LOG"] = str(log)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [str(script), *[str(repo) for repo in repos]],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def _log(log: Path) -> list[dict]:
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line]


def test_usage_and_missing_map(tmp_path: Path) -> None:
    script = _install_runner(tmp_path)
    empty = subprocess.run([str(script)], check=False, capture_output=True, text=True)
    assert empty.returncode == 2
    assert "usage" in empty.stderr

    bare = tmp_path / "bare"
    bare.mkdir()
    missing = subprocess.run([str(script), str(bare)], check=False, capture_output=True, text=True)
    assert missing.returncode == 2
    assert "no CLAUDE.md" in missing.stderr


def test_order_alternates_and_arm_b_hides_the_map(tmp_path: Path) -> None:
    script = _install_runner(tmp_path)
    bin_dir = _install_claude(tmp_path)
    log = tmp_path / "calls.jsonl"
    first = _repo(tmp_path, "even-repo")
    second = _repo(tmp_path, "odd-repo")
    proc = _run(script, [first, second], bin_dir, log)
    assert proc.returncode == 0, proc.stderr
    calls = _log(log)
    assert [(c["repo"], c["present"]) for c in calls] == [
        ("even-repo", True),
        ("even-repo", False),
        ("odd-repo", False),
        ("odd-repo", True),
    ]
    for call in calls:
        assert call["args"][:2] == ["-p", PROMPT]
        assert (
            "--model" in call["args"]
            and call["args"][call["args"].index("--model") + 1] == "sonnet"
        )
        assert "--max-turns" in call["args"] and "12" in call["args"]
        assert "--output-format" in call["args"] and "json" in call["args"]
    for repo in (first, second):
        assert (repo / "CLAUDE.md").is_file()
        assert not (repo / "CLAUDE.md.ab-hidden").exists()
    out = tmp_path / "results"
    assert (out / "even-repo-A.json").is_file()
    assert (out / "odd-repo-B.json").is_file()


def test_model_override(tmp_path: Path) -> None:
    script = _install_runner(tmp_path)
    bin_dir = _install_claude(tmp_path)
    log = tmp_path / "calls.jsonl"
    repo = _repo(tmp_path, "only")
    proc = _run(script, [repo], bin_dir, log, {"AB_MODEL": "opus"})
    assert proc.returncode == 0, proc.stderr
    calls = _log(log)
    assert calls[0]["args"][calls[0]["args"].index("--model") + 1] == "opus"


def test_retry_once_then_keep_the_successful_run(tmp_path: Path) -> None:
    script = _install_runner(tmp_path)
    bin_dir = _install_claude(tmp_path)
    log = tmp_path / "calls.jsonl"
    repo = _repo(tmp_path, "flaky")
    (repo / ".fail_remaining").write_text("1", encoding="utf-8")
    proc = _run(script, [repo], bin_dir, log)
    assert proc.returncode == 0, proc.stderr
    assert "RETRY" in proc.stdout
    calls = _log(log)
    # Arm A fails once, then succeeds. Arm B runs once.
    assert [c["present"] for c in calls] == [True, True, False]
    assert not (tmp_path / "results" / "flaky-A.dropped").exists()
    assert (repo / "CLAUDE.md").is_file()
    saved = json.loads((tmp_path / "results" / "flaky-A.json").read_text(encoding="utf-8"))
    assert saved["result"] == "ok"


def test_empty_stdout_is_retried(tmp_path: Path) -> None:
    script = _install_runner(tmp_path)
    bin_dir = _install_claude(tmp_path)
    log = tmp_path / "calls.jsonl"
    repo = _repo(tmp_path, "quiet")
    (repo / ".silent_once").write_text("1", encoding="utf-8")
    proc = _run(script, [repo], bin_dir, log)
    assert proc.returncode == 0, proc.stderr
    assert "RETRY" in proc.stdout
    assert len(_log(log)) == 3


def test_second_failure_drops_the_cell_and_restores_the_map(tmp_path: Path) -> None:
    script = _install_runner(tmp_path)
    bin_dir = _install_claude(tmp_path)
    log = tmp_path / "calls.jsonl"
    repo = _repo(tmp_path, "down")
    (repo / ".fail_remaining").write_text("9", encoding="utf-8")
    proc = _run(script, [repo], bin_dir, log)
    assert proc.returncode == 0, proc.stderr
    assert "DROPPED" in proc.stdout
    dropped = tmp_path / "results" / "down-A.dropped"
    assert dropped.read_text(encoding="utf-8").strip() == "dropped"
    assert (repo / "CLAUDE.md").is_file()
    assert not (repo / "CLAUDE.md.ab-hidden").exists()
    # Both arms retried: A hidden? No, A keeps the map. Two failures each arm.
    assert len(_log(log)) == 4
    assert all(call["present"] for call in _log(log)[:2])
