## MODIFIED Requirements

### Requirement: Each module identifies its temporal scope
The system SHALL render each included module's qualifying-change count and minimum-to-maximum UTC calendar-date range immediately before its selected AI-summary or commit-list content.

#### Scenario: Module contains several qualifying commits
- **WHEN** an included module contains three qualifying commits spanning two UTC calendar dates
- **THEN** the module metadata shows a count of three and the exact two-date range

#### Scenario: Module contains one qualifying commit
- **WHEN** an included module contains exactly one qualifying commit
- **THEN** the module metadata uses singular change wording and shows one date without a duplicated range endpoint

#### Scenario: Summary combines multiple commits
- **WHEN** an AI-generated summary bullet represents changes from more than one qualifying commit
- **THEN** the system presents dates in module metadata and does not assign an unsupported individual date to that bullet

#### Scenario: Commit list contains individual entries
- **WHEN** a commit-list module renders exact subject and object-ID entries
- **THEN** the system retains dates in common module metadata and does not add unrequested per-entry dates

### Requirement: Existing PDF guarantees are preserved
The system SHALL render report context using the existing Unicode-capable PDF path and SHALL preserve atomic destination replacement behavior for every report mode.

#### Scenario: Metadata contains supported non-ASCII repository text
- **WHEN** the derived repository name contains characters supported by the embedded font
- **THEN** the repository name renders without an encoding failure

#### Scenario: Context-rich PDF renders successfully
- **WHEN** report metadata, sections, module summaries, and output writing succeed
- **THEN** the configured destination is atomically replaced by a valid PDF containing the context metadata

#### Scenario: Context-rich commit-list PDF renders successfully
- **WHEN** report metadata, sections, module commit entries, and output writing succeed
- **THEN** the configured destination is atomically replaced by a valid PDF containing the context metadata
