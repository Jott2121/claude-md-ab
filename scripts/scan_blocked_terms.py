#!/usr/bin/env python3
"""Fail if any tracked file contains a blocked term.

The committed list holds only SHA-256 hex digests of lowercased terms, so the
terms themselves never appear in the tree. Each file is lowercased and split
into alphanumeric words; every word and every adjacent two-word phrase (joined
by one space) is hashed and compared against the list.

The EMPLOYER_MARKERS env var (e.g. an Actions secret of the same name) may add
a case-insensitive regex alternation such as "foo|bar baz". It only adds to the
hash list; the hash list is required whether or not the variable is set.
Hits are reported by path, line, and digest prefix or "marker" only, never the
matched text.

Exit codes: 0 clean, 1 blocked term found, 2 configuration or read error.
A missing, empty, or malformed hash file, or an invalid EMPLOYER_MARKERS regex,
is an error, so the check fails closed.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HASH_FILE = ROOT / ".github" / "blocked-terms.sha256"
ENV_VAR = "EMPLOYER_MARKERS"
EXCLUDED_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        "build",
        "dist",
        "__pycache__",
        ".venv",
        "venv",
        ".tox",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
    }
)
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_WORD = re.compile(r"[a-z0-9]+")


class ConfigError(Exception):
    """The scan cannot run safely; callers must treat this as a failure."""


def digest(term: str) -> str:
    return hashlib.sha256(term.encode("utf-8")).hexdigest()


def load_digests(hash_file: Path) -> frozenset[str]:
    try:
        text = hash_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot read {hash_file}: {exc}") from exc
    digests: set[str] = set()
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not _DIGEST.match(line):
            raise ConfigError(f"{hash_file}:{number}: not a lowercase sha256 hex digest")
        digests.add(line)
    if not digests:
        raise ConfigError(f"{hash_file} has no digests")
    return frozenset(digests)


def load_markers(value: str | None) -> re.Pattern[str] | None:
    if value is None or not value.strip():
        return None
    try:
        pattern = re.compile(value.strip(), re.IGNORECASE)
    except re.error as exc:
        raise ConfigError(f"{ENV_VAR} is not a valid regex: {exc}") from exc
    if pattern.search(""):
        raise ConfigError(f"{ENV_VAR} matches the empty string")
    return pattern


def candidates(text: str) -> Iterator[tuple[int, str]]:
    """Yield (line number, word or two-word phrase); phrases may span a line break."""
    words = [
        (number, match.group())
        for number, line in enumerate(text.lower().splitlines(), start=1)
        for match in _WORD.finditer(line)
    ]
    for index, (number, word) in enumerate(words):
        yield number, word
        if index + 1 < len(words):
            yield number, f"{word} {words[index + 1][1]}"


def is_excluded(path: Path, root: Path | None = None) -> bool:
    """True when a directory inside the scanned tree is junk.

    Names in ``EXCLUDED_DIRS`` apply only under ``root``. Ancestors of the
    repo, and the repo directory itself, do not count: a checkout under
    ``build/`` or named ``venv`` is still scanned.
    """
    parts = path.parts
    if root is not None:
        try:
            parts = path.resolve().relative_to(root.resolve()).parts
        except ValueError:
            parts = path.parts
    return any(part in EXCLUDED_DIRS or part.endswith(".egg-info") for part in parts)


def tracked_files(root: Path) -> list[Path]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ConfigError(f"git ls-files failed in {root}: {exc}") from exc
    names = [name for name in proc.stdout.decode("utf-8").split("\0") if name]
    if not names:
        raise ConfigError(f"no tracked files under {root}")
    return [root / name for name in names]


def scan(
    paths: Iterable[Path],
    digests: frozenset[str],
    markers: re.Pattern[str] | None = None,
    skip: frozenset[Path] = frozenset(),
    root: Path | None = None,
) -> list[str]:
    hits: list[str] = []
    for path in paths:
        if is_excluded(path, root) or path.is_symlink() or path.resolve() in skip:
            continue
        try:
            text = path.read_bytes().decode("utf-8", errors="replace")
        except OSError as exc:
            raise ConfigError(f"cannot read {path}: {exc}") from exc
        seen: set[tuple[int, str]] = set()
        for number, candidate in candidates(text):
            found = digest(candidate)
            if found in digests and (number, found) not in seen:
                seen.add((number, found))
                hits.append(f"{path}:{number}: blocked term (sha256 {found[:12]}...)")
        if markers is not None:
            for number, line in enumerate(text.splitlines(), start=1):
                if markers.search(line):
                    hits.append(f"{path}:{number}: blocked term ({ENV_VAR} marker)")
    return hits


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    root = ROOT
    hash_file = HASH_FILE
    if args[:1] == ["--root"]:
        if len(args) < 2:
            print("blocked-terms: --root needs a path", file=sys.stderr)
            return 2
        root = Path(args[1]).resolve()
        hash_file = root / ".github" / "blocked-terms.sha256"
        args = args[2:]
    try:
        digests = load_digests(hash_file)
        markers = load_markers(os.environ.get(ENV_VAR))
        paths = [Path(arg) for arg in args] if args else tracked_files(root)
        hits = scan(paths, digests, markers, skip=frozenset({hash_file.resolve()}), root=root)
    except ConfigError as exc:
        print(f"blocked-terms: {exc}", file=sys.stderr)
        return 2
    for hit in hits:
        print(hit)
    if hits:
        print(f"blocked-terms: {len(hits)} hit(s)")
        return 1
    extra = f", {ENV_VAR} set" if markers is not None else ""
    print(f"blocked-terms: ok ({len(paths)} files, {len(digests)} digests{extra})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
