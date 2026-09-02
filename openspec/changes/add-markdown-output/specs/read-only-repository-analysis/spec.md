## MODIFIED Requirements

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
- **THEN** the system reports the refresh failure and performs no boundary resolution, commit extraction, diff generation, AI summarization, PDF generation, or Markdown generation

### Requirement: Analysis files remain outside the source worktree
The system SHALL create temporary analysis files only for workflows that require them and only under a canonical path outside the analyzed source worktree, SHALL reject an internal or aliased configured temporary path before writing analysis data, and SHALL create read-only-mode PDF or Markdown output only outside the source worktree.

#### Scenario: External analysis paths are configured
- **WHEN** `ai_summary` temporary and final output paths resolve outside the source worktree
- **THEN** the system may create the analysis files at those explicit external paths without writing generated files into the source worktree

#### Scenario: Temporary path is inside the source worktree
- **WHEN** the configured `ai_summary` temporary analysis path resolves to the source worktree or one of its descendants
- **THEN** the system exits with a configuration error before creating diff, AI, PDF, or Markdown artifacts

#### Scenario: Path aliases the source worktree
- **WHEN** a configured `ai_summary` temporary path or read-only-mode output path uses a symlink or relative traversal that resolves inside the source worktree
- **THEN** the system rejects the path before creating or replacing a file

#### Scenario: No implicit path fallback
- **WHEN** an external `ai_summary` temporary path cannot be created or used
- **THEN** the system reports the path error and does not fall back to the source worktree

#### Scenario: Commit-list mode has no temporary analysis path
- **WHEN** runtime configuration selects `commit_list`
- **THEN** the system validates and prepares only the configured PDF or Markdown destination and creates no temporary analysis directory
