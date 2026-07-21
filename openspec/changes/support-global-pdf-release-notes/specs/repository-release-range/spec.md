## ADDED Requirements

### Requirement: Release boundary is loaded from JSON
The system SHALL load a non-empty release marker from the release-marker JSON file referenced by the runtime configuration before mutating or analyzing the target repository.

#### Scenario: Valid configured marker
- **WHEN** the runtime configuration references a readable JSON file containing a non-empty `marker` string
- **THEN** the system uses that string as the release-boundary marker

#### Scenario: Invalid marker configuration
- **WHEN** the release-marker file is missing, invalid JSON, or does not contain a non-empty `marker` string
- **THEN** the system exits with a configuration error before fetching or rebasing the repository

### Requirement: Repository is fetched and rebased before analysis
The system SHALL run `git fetch --prune` followed by `git rebase @{u}` against the configured local repository before searching for the release marker.

#### Scenario: Successful synchronization
- **WHEN** fetch and rebase both succeed
- **THEN** the system searches for the release boundary against the successfully rebased `HEAD`

#### Scenario: Fetch fails
- **WHEN** `git fetch --prune` returns a nonzero status
- **THEN** the system does not run rebase, commit extraction, diff generation, AI summarization, or PDF generation

### Requirement: Failed rebase is recovered and reported
The system SHALL preserve the original Git error, attempt to abort a failed rebase, stop downstream processing, and return a nonzero exit status without an expected-error Python traceback.

#### Scenario: Rebase fails and abort succeeds
- **WHEN** `git rebase @{u}` fails and `git rebase --abort` succeeds
- **THEN** the CLI displays the original rebase error, states that the rebase was aborted, and generates no release-note artifacts

#### Scenario: Rebase and abort both fail
- **WHEN** `git rebase @{u}` fails and the abort attempt also fails
- **THEN** the CLI displays the original rebase error and abort error, warns that manual recovery may be required, and generates no release-note artifacts

### Requirement: Commits are selected from marker to rebased HEAD
The system SHALL find the newest commit reachable from rebased `HEAD` whose subject contains the configured marker and SHALL select later commits in oldest-first order from `<marker-hash>..HEAD`.

#### Scenario: Marker exists
- **WHEN** multiple reachable commit subjects contain the configured marker
- **THEN** the newest matching commit is excluded as the lower boundary and only later commits are selected

#### Scenario: Marker does not exist
- **WHEN** no reachable commit subject contains the configured marker
- **THEN** the CLI reports the missing marker, returns a nonzero exit status, and performs no diff, AI, or PDF work
