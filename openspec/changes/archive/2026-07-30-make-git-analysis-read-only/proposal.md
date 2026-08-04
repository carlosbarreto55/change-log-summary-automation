## Why

Release analysis currently fetches and rebases the checked-out branch on every run, which can rewrite local history and modify a developer's source worktree. Read-only analysis over explicit, frozen boundaries is required for safe CI use, reproducibility, detached-ref analysis, and repositories that contain local work.

## What Changes

- **BREAKING**: remove mandatory `fetch --prune` and `rebase @{u}` from the default release-analysis path.
- Require an explicit head ref and either an explicit base ref or a configured marker selector, then resolve all boundaries to exact SHAs once before analysis.
- Read commits and diffs directly from the resolved SHAs without checking out or rebasing either boundary.
- Run a non-mutating repository-status preflight and warn when the checked-out branch is dirty, detached, ahead, behind, diverged, or cannot be proven current from available remote-tracking data.
- Offer remote-ref refresh without checkout as an explicit option; report when freshness is unknown if no refresh is requested.
- Retain in-place fetch/rebase, if retained at all, only behind an explicit opt-in synchronization mode with clean-worktree and upstream preconditions.
- Keep temporary analysis files outside the analyzed source worktree and reject implicit writes into it.

## Capabilities

### New Capabilities
- `read-only-repository-analysis`: Defines source-worktree immutability, status/freshness diagnostics, optional remote-ref refresh, and guarded opt-in synchronization.

### Modified Capabilities
- `repository-release-range`: Select and freeze explicit base/head boundaries without mandatory checkout mutation, while preserving marker-based base selection as an explicit supported mode.

## Impact

This changes runtime configuration, Git command execution, range extraction, workflow preflight, CLI options and warnings, README guidance, and synchronization/range unit and Linux integration tests. Existing configurations that rely on implicit rebased `HEAD` must choose refs or explicitly opt into synchronization.
