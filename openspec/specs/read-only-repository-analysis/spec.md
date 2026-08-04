## Purpose

Define safe repository analysis behavior, explicit update modes, checkout diagnostics, and source-worktree artifact containment.

## Requirements

### Requirement: Default repository analysis is read-only
The system SHALL default to repository analysis that does not fetch, rebase, checkout, switch, reset, merge, pull, or modify repository refs, `HEAD`, the index, tracked worktree files, or untracked worktree files.

#### Scenario: Default analysis succeeds
- **WHEN** the user runs analysis without explicitly selecting a repository update mode
- **THEN** the system analyzes the configured frozen range without changing repository refs, `HEAD`, the index, or worktree contents

#### Scenario: Default analysis fails after preflight
- **WHEN** any range, diff, AI, or output operation fails during default analysis
- **THEN** repository refs, `HEAD`, the index, and worktree contents remain unchanged

#### Scenario: Dirty checkout is analyzed read-only
- **WHEN** the checkout contains staged, unstaged, or untracked changes and the default mode is used
- **THEN** the system warns about the dirty checkout and performs SHA-based analysis without changing or consuming those changes

### Requirement: Checkout status and freshness are diagnosed without mutation
The system SHALL inspect the checked-out worktree without mutation and SHALL warn when it is dirty, detached, ahead of its upstream, behind its upstream, diverged from its upstream, cannot be compared with an upstream from available tracking data, or has remote freshness that cannot be established.

#### Scenario: Detached checkout
- **WHEN** the configured repository has a detached `HEAD`
- **THEN** the system warns that the checkout is detached while continuing read-only analysis of the explicitly configured head ref

#### Scenario: Checked-out branch is ahead
- **WHEN** the checked-out branch has commits not present in its available upstream tracking ref and the upstream has no commits absent from the branch
- **THEN** the system warns that the checkout is ahead

#### Scenario: Checked-out branch is behind
- **WHEN** the available upstream tracking ref has commits not present in the checked-out branch and the branch has no commits absent from the upstream
- **THEN** the system warns that the checkout is behind

#### Scenario: Checked-out branch has diverged
- **WHEN** both the checked-out branch and its available upstream tracking ref have commits absent from the other
- **THEN** the system warns that the checkout has diverged

#### Scenario: Upstream comparison is unavailable
- **WHEN** the checkout has no resolvable upstream or the available remote-tracking data cannot support a comparison
- **THEN** the system warns that the checkout relationship cannot be determined and does not infer that it is current

#### Scenario: Remote freshness is unknown without refresh
- **WHEN** no explicit remote-ref refresh was completed for a relevant remote-tracking ref
- **THEN** the system warns that the ref's remote freshness is unknown even if local ahead and behind counts are both zero

### Requirement: Remote refs are refreshed only by explicit request
The system SHALL fetch remote refs only when the user explicitly selects remote-ref refresh and names the remote refs, SHALL complete that refresh before resolving range boundaries, and SHALL leave `HEAD`, the index, local branch refs, and worktree contents unchanged.

#### Scenario: No refresh is requested
- **WHEN** the default read-only update mode is used
- **THEN** the system performs no fetch and reports remote freshness as unknown

#### Scenario: Named remote refs are refreshed
- **WHEN** the user explicitly requests refresh of valid named remote refs
- **THEN** the system fetches only those refs into their remote-tracking destinations without checkout or rebase and resolves boundaries after the fetch succeeds

#### Scenario: Ref freshness after refresh
- **WHEN** an explicit refresh of a named remote ref succeeds
- **THEN** the system reports that ref as refreshed as of that fetch and does not claim freshness for relevant refs that were not refreshed

#### Scenario: Requested refresh fails
- **WHEN** an explicitly requested remote-ref fetch returns a nonzero status
- **THEN** the system reports the refresh failure and performs no boundary resolution, commit extraction, diff generation, AI summarization, or PDF generation

### Requirement: Legacy in-place synchronization is explicitly opted into and guarded
The system SHALL run legacy in-place fetch and rebase only when the user explicitly selects that mode and the checked-out branch is attached, has no staged, unstaged, or untracked changes, and has a resolvable upstream.

#### Scenario: Legacy mode is not selected
- **WHEN** the user does not explicitly select legacy in-place synchronization
- **THEN** the system does not rebase the checked-out branch

#### Scenario: Legacy mode has a dirty checkout
- **WHEN** legacy in-place synchronization is selected and the checkout has staged, unstaged, or untracked changes
- **THEN** the system reports the failed clean-worktree guard and performs no fetch, rebase, or downstream analysis

#### Scenario: Legacy mode has no usable upstream
- **WHEN** legacy in-place synchronization is selected and the checkout is detached or its branch has no resolvable upstream
- **THEN** the system reports the failed upstream guard and performs no fetch, rebase, or downstream analysis

#### Scenario: Legacy synchronization succeeds
- **WHEN** legacy in-place synchronization is selected, all guards pass, and fetch and upstream rebase succeed
- **THEN** the system resolves the configured range boundaries only after the synchronized checkout is available

#### Scenario: Legacy fetch fails
- **WHEN** legacy in-place synchronization passes its guards but fetch fails
- **THEN** the system reports the fetch error and performs no rebase or downstream analysis

#### Scenario: Legacy rebase fails
- **WHEN** legacy in-place synchronization passes its guards and fetch succeeds but rebase fails
- **THEN** the system preserves the original rebase error, attempts to abort the rebase, reports any abort error separately, and performs no downstream analysis

### Requirement: Analysis files remain outside the source worktree
The system SHALL create temporary analysis files only under a canonical path outside the analyzed source worktree, SHALL reject an internal or aliased temporary path before writing analysis data, and SHALL create read-only-mode final output only outside the source worktree.

#### Scenario: External analysis paths are configured
- **WHEN** temporary and final output paths resolve outside the source worktree
- **THEN** the system may create the analysis files at those explicit external paths without writing generated files into the source worktree

#### Scenario: Temporary path is inside the source worktree
- **WHEN** the configured temporary analysis path resolves to the source worktree or one of its descendants
- **THEN** the system exits with a configuration error before creating diff, AI, or PDF artifacts

#### Scenario: Path aliases the source worktree
- **WHEN** a configured temporary or read-only-mode output path uses a symlink or relative traversal that resolves inside the source worktree
- **THEN** the system rejects the path before creating or replacing a file

#### Scenario: No implicit path fallback
- **WHEN** an external temporary path cannot be created or used
- **THEN** the system reports the path error and does not fall back to the source worktree
