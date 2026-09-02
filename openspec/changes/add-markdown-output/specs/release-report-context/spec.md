## MODIFIED Requirements

### Requirement: Report header identifies its repository and scope
The system SHALL render a document header that identifies the repository by the configured repository path's final component and reports the total number of qualifying commits represented by the document in every supported output format.

#### Scenario: Report contains qualifying changes
- **WHEN** one or more commits qualify for the release document
- **THEN** the header shows the repository name and the exact total qualifying-change count

#### Scenario: Configured repository path has parent directories
- **WHEN** the configured repository path is `/work/fixtures/linux`
- **THEN** the header repository name is `linux`

### Requirement: Empty reports remain descriptive
The system SHALL identify the repository and show a zero qualifying-change count when no commits qualify, while omitting date and ISO-week values that cannot be derived, in every supported output format.

#### Scenario: No post-marker commits qualify
- **WHEN** filtering produces no qualifying commits
- **THEN** the final report header shows the repository and zero count, omits change-date and ISO-week rows, and displays `No qualifying changes.`

### Requirement: Existing PDF guarantees are preserved
The system SHALL render report context through the selected UTF-8-capable PDF or Markdown exporter and SHALL preserve output-path containment and atomic destination replacement behavior for every report mode and output format.

#### Scenario: Metadata contains non-ASCII repository text
- **WHEN** the derived repository name contains non-ASCII characters supported by the selected format
- **THEN** the repository name renders without an encoding failure

#### Scenario: Context-rich PDF renders successfully
- **WHEN** PDF is selected and report metadata, sections, module summaries or commit entries, and output writing succeed
- **THEN** the configured destination is atomically replaced by a valid PDF containing the context metadata

#### Scenario: Context-rich Markdown renders successfully
- **WHEN** Markdown is selected and report metadata, sections, module summaries or commit entries, and output writing succeed
- **THEN** the configured destination is atomically replaced by a UTF-8 Markdown document containing the same context metadata
