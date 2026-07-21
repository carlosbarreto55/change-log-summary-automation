# release-report-context Specification

## Purpose
Define deterministic repository, qualifying-change count, UTC date, ISO week, and per-module context for generated release-notes PDFs.

## Requirements

### Requirement: Qualifying commits retain deterministic dates
The system SHALL extract each post-marker commit's strict ISO 8601 Git author timestamp, preserve it when the commit qualifies by author and module, and normalize it to UTC before deriving report dates.

#### Scenario: Qualifying commit has an offset timestamp
- **WHEN** Git returns a qualifying commit with a valid author timestamp containing a UTC offset
- **THEN** the classified commit retains the instant and report composition derives its calendar date in UTC

#### Scenario: Commit timestamp is malformed
- **WHEN** Git returns a post-marker commit whose strict author timestamp cannot be parsed
- **THEN** release history extraction fails with a Git-history error instead of generating incomplete temporal metadata

### Requirement: Report header identifies its repository and scope
The system SHALL render a first-page header that identifies the repository by the configured repository path's final component and reports the total number of qualifying commits represented by the document.

#### Scenario: Report contains qualifying changes
- **WHEN** one or more commits qualify for the release document
- **THEN** the header shows the repository name and the exact total qualifying-change count

#### Scenario: Configured repository path has parent directories
- **WHEN** the configured repository path is `/work/fixtures/linux`
- **THEN** the header repository name is `linux`

### Requirement: Report header describes the qualifying date range
The system SHALL show the minimum and maximum UTC calendar dates among all qualifying commits and the corresponding ISO year-week value or range as secondary context.

#### Scenario: Qualifying changes span multiple dates and weeks
- **WHEN** the earliest qualifying commit is dated 2026-01-03 UTC and the latest is dated 2026-02-02 UTC
- **THEN** the header shows `2026-01-03 – 2026-02-02` as the change-date range and `2026-W01 – 2026-W06` as the ISO week range

#### Scenario: Qualifying changes share one date and week
- **WHEN** all qualifying commits have the same UTC calendar date
- **THEN** the header shows one date and one ISO year-week value without duplicating either as a range

#### Scenario: Author offsets cross a UTC date boundary
- **WHEN** qualifying commits contain author timestamps with different offsets
- **THEN** range ordering and displayed calendar dates are derived after UTC normalization

### Requirement: Each module identifies its temporal scope
The system SHALL render each included module's qualifying-change count and minimum-to-maximum UTC calendar-date range immediately before its AI-generated summary.

#### Scenario: Module contains several qualifying commits
- **WHEN** an included module contains three qualifying commits spanning two UTC calendar dates
- **THEN** the module metadata shows a count of three and the exact two-date range

#### Scenario: Module contains one qualifying commit
- **WHEN** an included module contains exactly one qualifying commit
- **THEN** the module metadata uses singular change wording and shows one date without a duplicated range endpoint

#### Scenario: Summary combines multiple commits
- **WHEN** an AI-generated summary bullet represents changes from more than one qualifying commit
- **THEN** the system presents dates in module metadata and does not assign an unsupported individual date to that bullet

### Requirement: Empty reports remain descriptive
The system SHALL identify the repository and show a zero qualifying-change count when no commits qualify, while omitting date and ISO-week values that cannot be derived.

#### Scenario: No post-marker commits qualify
- **WHEN** filtering produces no qualifying commits
- **THEN** the PDF header shows the repository and zero count, omits change-date and ISO-week rows, and displays `No qualifying changes.`

### Requirement: Existing PDF guarantees are preserved
The system SHALL render report context using the existing Unicode-capable PDF path and SHALL preserve atomic destination replacement behavior.

#### Scenario: Metadata contains supported non-ASCII repository text
- **WHEN** the derived repository name contains characters supported by the embedded font
- **THEN** the repository name renders without an encoding failure

#### Scenario: Context-rich PDF renders successfully
- **WHEN** report metadata, sections, module summaries, and output writing succeed
- **THEN** the configured destination is atomically replaced by a valid PDF containing the context metadata
