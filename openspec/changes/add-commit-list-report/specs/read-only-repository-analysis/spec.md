## MODIFIED Requirements

### Requirement: Analysis files remain outside the source worktree
The system SHALL create temporary analysis files only for workflows that require them and only under a canonical path outside the analyzed source worktree, SHALL reject an internal or aliased configured temporary path before writing analysis data, and SHALL create read-only-mode final output only outside the source worktree.

#### Scenario: AI-summary external analysis paths are configured
- **WHEN** `ai_summary` temporary and final output paths resolve outside the source worktree
- **THEN** the system may create the analysis files at those explicit external paths without writing generated files into the source worktree

#### Scenario: AI-summary temporary path is inside the source worktree
- **WHEN** the configured `ai_summary` temporary analysis path resolves to the source worktree or one of its descendants
- **THEN** the system exits with a configuration error before creating diff, AI, or PDF artifacts

#### Scenario: Path aliases the source worktree
- **WHEN** a configured `ai_summary` temporary path or read-only-mode output path uses a symlink or relative traversal that resolves inside the source worktree
- **THEN** the system rejects the path before creating or replacing a file

#### Scenario: No implicit path fallback
- **WHEN** an external `ai_summary` temporary path cannot be created or used
- **THEN** the system reports the path error and does not fall back to the source worktree

#### Scenario: Commit-list mode has no temporary analysis path
- **WHEN** runtime configuration selects `commit_list`
- **THEN** the system validates and prepares only the configured PDF destination and creates no temporary analysis directory
