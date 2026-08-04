"""Exact Git and worktree state snapshots for read-only workflow proofs."""

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
class GitStateSnapshot:
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
    worktree_inventory: tuple[tuple[str, str, int, Optional[str], Optional[str]], ...]

    @property
    def local_refs(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            ref for ref in self.refs if not ref[0].startswith("refs/remotes/")
        )


def snapshot_git_state(repository_path: Path) -> GitStateSnapshot:
    repository = Path(repository_path).resolve()
    refs = tuple(
        tuple(line.split("\x00", 1))
        for line in _git(
            repository,
            ["for-each-ref", "--format=%(refname)%00%(objectname)"],
        ).splitlines()
        if line
    )
    symbolic_result = _git_process(
        repository,
        ["symbolic-ref", "--quiet", "HEAD"],
    )
    symbolic_head = (
        symbolic_result.stdout.strip()
        if symbolic_result.returncode == 0
        else None
    )
    head_sha = _git(repository, ["rev-parse", "--verify", "HEAD^{commit}"]).strip()
    index_path_text = _git(repository, ["rev-parse", "--git-path", "index"]).strip()
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

    return GitStateSnapshot(
        refs=refs,
        symbolic_head=symbolic_head,
        head_sha=head_sha,
        index_sha256=index_sha256,
        index_mode=index_mode,
        index_mtime_ns=index_mtime_ns,
        index_size=index_size,
        index_tree=index_tree,
        porcelain_status=_git(
            repository,
            ["status", "--porcelain=v2", "--branch", "--untracked-files=normal"],
        ),
        operation_state=_operation_state(repository),
        worktree_inventory=_worktree_inventory(repository),
    )


def _operation_state(repository: Path) -> tuple[tuple[str, str], ...]:
    git_dir_text = _git(repository, ["rev-parse", "--git-dir"]).strip()
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


def _worktree_inventory(
    repository: Path,
) -> tuple[tuple[str, str, int, Optional[str], Optional[str]], ...]:
    inventory: list[tuple[str, str, int, Optional[str], Optional[str]]] = []
    for directory, directory_names, file_names in os.walk(repository, topdown=True):
        directory_path = Path(directory)
        if directory_path == repository and ".git" in directory_names:
            directory_names.remove(".git")
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
                inventory.append(
                    (
                        relative_path,
                        "file",
                        mode,
                        None,
                        hashlib.sha256(path.read_bytes()).hexdigest(),
                    )
                )
            else:
                inventory.append((relative_path, "other", mode, None, None))
    return tuple(sorted(inventory))


def _git(repository: Path, args: list[str]) -> str:
    result = _git_process(repository, args)
    if result.returncode != 0:
        raise AssertionError(result.stderr.strip() or result.stdout.strip())
    return result.stdout


def _git_process(
    repository: Path,
    args: list[str],
    extra_environment: Optional[dict[str, str]] = None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    if extra_environment is not None:
        environment.update(extra_environment)
    return subprocess.run(
        ["git", "-C", str(repository), *args],
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
        env=environment,
    )


def _write_tree_from_index(repository: Path, index_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile() as temporary_index:
        temporary_index.write(index_bytes)
        temporary_index.flush()
        result = _git_process(
            repository,
            ["write-tree"],
            {"GIT_INDEX_FILE": temporary_index.name},
        )
    if result.returncode != 0:
        raise AssertionError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()
