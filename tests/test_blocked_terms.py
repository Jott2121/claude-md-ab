"""Hashed blocked-term scanner: catches planted terms, passes clean trees, fails closed.

Planted terms here are synthetic. Real blocked terms exist only as digests.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.scan_blocked_terms import (
    HASH_FILE,
    ConfigError,
    digest,
    load_digests,
    load_markers,
    main,
    scan,
    tracked_files,
)

ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / "scripts" / "scan_blocked_terms.py"
PLANTED = "zorblax quintet"
MARKER = "zorblax[ -]quintet|other-made-up-term"


def _hash_file(tmp_path: Path, *terms: str) -> Path:
    path = tmp_path / "terms.sha256"
    path.write_text("# test digests\n" + "".join(f"{digest(t)}\n" for t in terms), encoding="utf-8")
    return path


def _git_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    repo = tmp_path / "repo"
    (repo / ".github").mkdir(parents=True)
    shutil.copy(HASH_FILE, repo / ".github" / "blocked-terms.sha256")
    for name, text in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    return repo


def _cli(*args: str, env_terms: str | None = None) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k != "EMPLOYER_MARKERS"}
    if env_terms is not None:
        env["EMPLOYER_MARKERS"] = env_terms
    return subprocess.run(
        [sys.executable, str(SCANNER), *args],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_committed_hash_file_is_nonempty_and_well_formed() -> None:
    assert len(load_digests(HASH_FILE)) >= 1


def test_committed_tree_is_clean() -> None:
    proc = _cli()
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "blocked-terms: ok" in proc.stdout


def test_planted_term_is_caught_and_clean_tree_passes(tmp_path: Path) -> None:
    clean = _git_repo(tmp_path / "clean", {"results/a.json": '{"result": "fine"}\n'})
    assert _cli("--root", str(clean), env_terms=MARKER).returncode == 0

    dirty = _git_repo(
        tmp_path / "dirty",
        {"results/a.json": '{"result": "built at Zorblax-Quintet HQ"}\n', "README.md": "ok\n"},
    )
    proc = _cli("--root", str(dirty), env_terms=MARKER)
    assert proc.returncode == 1
    assert "results/a.json:1: blocked term" in proc.stdout
    assert "zorblax" not in proc.stdout.lower()


def test_single_words_phrases_across_lines_and_case_are_matched(tmp_path: Path) -> None:
    digests = load_digests(_hash_file(tmp_path, "zorblax", PLANTED))
    target = tmp_path / "note.md"
    target.write_text("one\nZORBLAX here\nends with Zorblax\nquintet starts\n", encoding="utf-8")
    hits = scan([target], digests)
    assert [hit.split(": ")[0] for hit in hits] == [
        f"{target}:2",
        f"{target}:3",
        f"{target}:3",
    ]


def test_substrings_of_other_words_do_not_match(tmp_path: Path) -> None:
    digests = load_digests(_hash_file(tmp_path, "lm"))
    target = tmp_path / "note.md"
    target.write_text("LLM and LMS are fine\n", encoding="utf-8")
    assert scan([target], digests) == []


def test_hash_list_catches_a_term_with_no_env_var_set(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path, {"AGENTS.md": "clean\n"})
    (repo / ".github" / "blocked-terms.sha256").write_text(f"{digest(PLANTED)}\n", encoding="utf-8")
    (repo / ".cursor").mkdir()
    (repo / ".cursor" / "rules.mdc").write_text("see Zorblax Quintet\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    proc = _cli("--root", str(repo))
    assert proc.returncode == 1
    assert ".cursor/rules.mdc:1: blocked term (sha256" in proc.stdout


def test_hash_file_itself_is_not_scanned(tmp_path: Path) -> None:
    repo = _git_repo(tmp_path, {"a.txt": "clean\n"})
    hash_file = repo / ".github" / "blocked-terms.sha256"
    hash_file.write_text(f"{digest(PLANTED)}\n", encoding="utf-8")
    assert _cli("--root", str(repo), env_terms=digest(PLANTED)).returncode == 0


def test_markers_are_a_case_insensitive_regex(tmp_path: Path) -> None:
    assert load_markers(None) is None
    assert load_markers("  ") is None
    markers = load_markers(" " + MARKER + " ")
    assert markers is not None
    digests = load_digests(_hash_file(tmp_path, "unrelated"))
    target = tmp_path / "note.md"
    target.write_text("ok\nZORBLAX QUINTET\n", encoding="utf-8")
    assert scan([target], digests, markers) == [
        f"{target}:2: blocked term (EMPLOYER_MARKERS marker)"
    ]


@pytest.mark.parametrize("value", ["(unclosed", "a|"], ids=["invalid", "matches-empty"])
def test_bad_markers_fail_closed(value: str) -> None:
    with pytest.raises(ConfigError, match="EMPLOYER_MARKERS"):
        load_markers(value)
    assert _cli(env_terms=value).returncode == 2


def test_excluded_dirs_are_skipped(tmp_path: Path) -> None:
    digests = load_digests(_hash_file(tmp_path, "zorblax"))
    junk = tmp_path / "node_modules" / "pkg.js"
    junk.parent.mkdir()
    junk.write_text("zorblax\n", encoding="utf-8")
    egg = tmp_path / "x.egg-info" / "PKG-INFO"
    egg.parent.mkdir()
    egg.write_text("zorblax\n", encoding="utf-8")
    assert scan([junk, egg], digests) == []


@pytest.mark.parametrize(
    "contents",
    [None, "", "# only a comment\n\n"],
    ids=["missing", "empty", "comments-only"],
)
def test_missing_or_empty_hash_file_fails_closed(tmp_path: Path, contents: str | None) -> None:
    repo = _git_repo(tmp_path, {"a.txt": "clean\n"})
    hash_file = repo / ".github" / "blocked-terms.sha256"
    if contents is None:
        hash_file.unlink()
    else:
        hash_file.write_text(contents, encoding="utf-8")
    proc = _cli("--root", str(repo), env_terms=MARKER)
    assert proc.returncode == 2
    assert "blocked-terms:" in proc.stderr


def test_malformed_digest_fails_closed(tmp_path: Path) -> None:
    bad = tmp_path / "terms.sha256"
    bad.write_text("not-a-digest\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="not a lowercase sha256"):
        load_digests(bad)


def test_unreadable_target_fails_closed(tmp_path: Path) -> None:
    digests = load_digests(_hash_file(tmp_path, "zorblax"))
    with pytest.raises(ConfigError, match="cannot read"):
        scan([tmp_path / "missing.txt"], digests)


def test_non_git_root_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="git ls-files failed"):
        tracked_files(tmp_path)


def test_empty_git_repo_fails_closed(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    with pytest.raises(ConfigError, match="no tracked files"):
        tracked_files(tmp_path)


def test_main_scans_explicit_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMPLOYER_MARKERS", MARKER)
    target = tmp_path / "note.txt"
    target.write_text("Zorblax Quintet\n", encoding="utf-8")
    assert main([str(target)]) == 1
    target.write_text("clean\n", encoding="utf-8")
    assert main([str(target)]) == 0


def test_main_rejects_root_without_a_path() -> None:
    assert main(["--root"]) == 2


def test_main_returns_two_on_config_error(tmp_path: Path) -> None:
    assert main(["--root", str(tmp_path)]) == 2
