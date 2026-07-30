## MODIFIED Requirements

### Requirement: Release boundary is loaded from JSON
The system SHALL load a non-empty explicit head ref and exactly one lower-boundary selector from JSON: either a non-empty explicit base ref or a release-marker JSON file containing a non-empty `marker` string. It SHALL validate selector exclusivity before updating or analyzing the target repository.

#### Scenario: Valid explicit base configuration
- **WHEN** runtime JSON defines a non-empty head ref and base ref and does not define a marker selector
- **THEN** the system uses the head and base refs as the release-range selectors

#### Scenario: Valid configured marker
- **WHEN** runtime JSON defines a non-empty head ref, references a readable release-marker JSON file containing a non-empty `marker` string, and does not define a base ref
- **THEN** the system uses the head ref and marker string as the release-range selectors

#### Scenario: Missing or conflicting selectors
- **WHEN** the head ref is empty or absent, or the runtime configuration defines both lower-boundary selectors or neither lower-boundary selector
- **THEN** the system exits with a configuration error before running a Git command or creating an output artifact

#### Scenario: Invalid marker configuration
- **WHEN** marker mode is selected and the release-marker file is missing, invalid JSON, or does not contain a non-empty `marker` string
- **THEN** the system exits with a configuration error before fetching, rebasing, resolving boundaries, or analyzing the repository

### Requirement: Commits are selected from marker to rebased HEAD
The system SHALL resolve the configured head ref and selected lower boundary to full commit SHAs exactly once after any explicitly requested repository update, SHALL find a marker boundary only within history reachable from the frozen head SHA, and SHALL select commits in oldest-first order from `<base-sha>..<head-sha>` using only the frozen SHAs.

#### Scenario: Explicit base ref is selected
- **WHEN** the configured head ref and base ref each resolve to a commit
- **THEN** the system freezes both full commit SHAs once and selects the commits in `<base-sha>..<head-sha>` without checking out either ref

#### Scenario: Marker exists within frozen head history
- **WHEN** multiple commit subjects reachable from the frozen head SHA contain the configured marker
- **THEN** the system freezes the newest matching reachable commit as the base SHA, excludes it as the lower boundary, and selects only later commits reachable from the frozen head SHA

#### Scenario: Marker exists only outside frozen head history
- **WHEN** a commit subject contains the configured marker but that commit is not reachable from the frozen head SHA
- **THEN** the system does not use that commit as the release boundary

#### Scenario: Configured refs move after resolution
- **WHEN** a configured ref changes after the range SHAs have been frozen
- **THEN** all commit extraction and diff generation for that run continue to use the original base and head SHAs

#### Scenario: A configured ref cannot resolve to a commit
- **WHEN** the explicit head ref or explicit base ref does not resolve to a commit
- **THEN** the system reports the unresolved boundary, returns a nonzero exit status, and performs no diff, AI, or PDF work

#### Scenario: Marker does not exist
- **WHEN** no reachable commit subject between the frozen head and its ancestors contains the configured marker
- **THEN** the system reports the missing marker, returns a nonzero exit status, and performs no diff, AI, or PDF work

## REMOVED Requirements

### Requirement: Repository is fetched and rebased before analysis
**Reason**: Mandatory in-place synchronization can rewrite local history and modify a developer's source worktree, and it prevents safe analysis of explicit refs.

**Migration**: Configure an explicit head ref and one base ref or marker selector. Use the read-only default, explicitly request named remote-ref refresh when current remote data is required, or explicitly select guarded legacy in-place synchronization when rebasing the checkout is required.

### Requirement: Failed rebase is recovered and reported
**Reason**: Rebase is no longer part of the default release-range behavior, so unconditional rebase recovery does not belong to this capability.

**Migration**: Default and remote-refresh runs require no rebase recovery. The explicitly selected legacy in-place synchronization mode retains abort and error-reporting behavior under the `read-only-repository-analysis` capability.
