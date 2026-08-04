"""Efficient exact-state proofs for the large external Linux fixture."""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class LinuxFixtureSnapshot:
    """Repository state that a direct read-only integration run must preserve."""

    refs: tuple[tuple[str, str], ...]
    symbolic_head: Optional[str]
    head_sha: str
    index_sha256: Optional[str]
    index_mode: Optional[int]
    index_mtime_ns: Optional[int]
    index_size: Optional[int]
    index_tree: str
    porcelain_status: str
    operation_state: tuple[tuple[str, str], ...]
    worktree_inventory: tuple[
        tuple[str, str, int, Optional[str], Optional[str]], ...
    ]


def snapshot_linux_fixture(repository_path: Path) -> LinuxFixtureSnapshot:
    """Capture all mutable Git state and every non-Git worktree path."""
    repository = Path(repository_path).resolve()
    refs = tuple(
        tuple(line.split("\x00", 1))
        for line in _git_text(
            repository,
            ["for-each-ref", "--format=%(refname)%00%(objectname)"],
        ).splitlines()
        if line
    )
    symbolic_result = _git_process(repository, ["symbolic-ref", "--quiet", "HEAD"])
    symbolic_head = (
        symbolic_result.stdout.decode("utf-8", errors="replace").strip()
        if symbolic_result.returncode == 0
        else None
    )
    head_sha = _git_text(
        repository, ["rev-parse", "--verify", "HEAD^{commit}"]
    ).strip()
    index_path_text = _git_text(
        repository, ["rev-parse", "--git-path", "index"]
    ).strip()
    index_path = Path(index_path_text)
    if not index_path.is_absolute():
        index_path = repository / index_path

    if index_path.exists():
        index_bytes = index_path.read_bytes()
        index_stat = index_path.stat()
        index_sha256 = hashlib.sha256(index_bytes).hexdigest()
        index_mode = stat.S_IMODE(index_stat.st_mode)
        index_mtime_ns = index_stat.st_mtime_ns
        index_size = index_stat.st_size
        index_tree = _write_tree_from_index(repository, index_bytes)
    else:
        index_sha256 = None
        index_mode = None
        index_mtime_ns = None
        index_size = None
        index_tree = ""

    porcelain_status = _git_text(
        repository,
        ["status", "--porcelain=v2", "--branch", "--untracked-files=all"],
    )
    return LinuxFixtureSnapshot(
        refs=refs,
        symbolic_head=symbolic_head,
        head_sha=head_sha,
        index_sha256=index_sha256,
        index_mode=index_mode,
        index_mtime_ns=index_mtime_ns,
        index_size=index_size,
        index_tree=index_tree,
        porcelain_status=porcelain_status,
        operation_state=_operation_state(repository),
        worktree_inventory=_worktree_inventory(repository),
    )


def _worktree_inventory(
    repository: Path,
) -> tuple[tuple[str, str, int, Optional[str], Optional[str]], ...]:
    indexed_objects = _indexed_objects(repository)
    worktree_modified = set(
        _nul_paths(_git_bytes(repository, ["diff", "--name-only", "-z", "--"]))
    )
    inventory: list[tuple[str, str, int, Optional[str], Optional[str]]] = []

    for directory, directory_names, file_names in os.walk(repository, topdown=True):
        directory_path = Path(directory)
        if directory_path == repository:
            if ".git" in directory_names:
                directory_names.remove(".git")
            if ".git" in file_names:
                file_names.remove(".git")

        for name in sorted(directory_names + file_names):
            path = directory_path / name
            relative_path = path.relative_to(repository).as_posix()
            path_stat = path.lstat()
            mode = stat.S_IMODE(path_stat.st_mode)
            if path.is_symlink():
                inventory.append(
                    (relative_path, "symlink", mode, os.readlink(path), None)
                )
            elif path.is_dir():
                inventory.append((relative_path, "directory", mode, None, None))
            elif path.is_file():
                indexed_object = indexed_objects.get(relative_path)
                if indexed_object is not None and relative_path not in worktree_modified:
                    content_hash = f"git:{indexed_object}"
                else:
                    content_hash = f"sha256:{_sha256_file(path)}"
                inventory.append(
                    (relative_path, "file", mode, None, content_hash)
                )
            else:
                inventory.append((relative_path, "other", mode, None, None))
    return tuple(sorted(inventory))


def _indexed_objects(repository: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for record in _git_bytes(repository, ["ls-files", "--stage", "-z"]).split(b"\x00"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        _, object_id, stage = metadata.decode("ascii").split()
        if stage == "0" and object_id.strip("0"):
            entries[raw_path.decode("utf-8", errors="surrogateescape")] = object_id
    return entries


def _nul_paths(output: bytes) -> tuple[str, ...]:
    return tuple(
        path.decode("utf-8", errors="surrogateescape")
        for path in output.split(b"\x00")
        if path
    )


def _operation_state(repository: Path) -> tuple[tuple[str, str], ...]:
    git_dir_text = _git_text(repository, ["rev-parse", "--git-dir"]).strip()
    git_dir = Path(git_dir_text)
    if not git_dir.is_absolute():
        git_dir = repository / git_dir
    state: list[tuple[str, str]] = []
    for name in (
        "FETCH_HEAD",
        "MERGE_HEAD",
        "CHERRY_PICK_HEAD",
        "REVERT_HEAD",
        "rebase-apply",
        "rebase-merge",
    ):
        path = git_dir / name
        if path.is_file():
            state.append((name, hashlib.sha256(path.read_bytes()).hexdigest()))
        elif path.is_dir():
            state.append((name, "directory"))
    return tuple(state)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_tree_from_index(repository: Path, index_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile() as temporary_index:
        temporary_index.write(index_bytes)
        temporary_index.flush()
        output = _git_text(
            repository,
            ["write-tree"],
            {"GIT_INDEX_FILE": temporary_index.name},
        )
    return output.strip()


def _git_text(
    repository: Path,
    args: list[str],
    extra_environment: Optional[dict[str, str]] = None,
) -> str:
    return _git_bytes(repository, args, extra_environment).decode(
        "utf-8", errors="replace"
    )


def _git_bytes(
    repository: Path,
    args: list[str],
    extra_environment: Optional[dict[str, str]] = None,
) -> bytes:
    result = _git_process(repository, args, extra_environment)
    if result.returncode != 0:
        raise AssertionError(
            result.stderr.decode("utf-8", errors="replace").strip()
            or result.stdout.decode("utf-8", errors="replace").strip()
        )
    return result.stdout


def _git_process(
    repository: Path,
    args: list[str],
    extra_environment: Optional[dict[str, str]] = None,
) -> subprocess.CompletedProcess[bytes]:
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    if extra_environment is not None:
        environment.update(extra_environment)
    return subprocess.run(
        ["git", "-C", str(repository), *args],
        capture_output=True,
        check=False,
        env=environment,
    )
