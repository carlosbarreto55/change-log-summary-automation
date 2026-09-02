## MODIFIED Requirements

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
- **THEN** the system reports the unresolved boundary, returns a nonzero exit status, and performs no diff, AI, PDF, or Markdown work

#### Scenario: Marker does not exist
- **WHEN** no reachable commit subject between the frozen head and its ancestors contains the configured marker
- **THEN** the system reports the missing marker, returns a nonzero exit status, and performs no diff, AI, PDF, or Markdown work
