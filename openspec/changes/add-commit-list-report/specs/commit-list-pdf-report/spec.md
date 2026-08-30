## ADDED Requirements

### Requirement: Runtime configuration selects the report mode explicitly
The system SHALL accept `report_mode` values `ai_summary` and `commit_list` in runtime JSON, SHALL select `ai_summary` when the field is absent, and SHALL reject any other value before path validation or Git activity.

#### Scenario: Existing runtime JSON omits report mode
- **WHEN** a valid existing runtime configuration does not define `report_mode`
- **THEN** the system runs the existing AI summary workflow

#### Scenario: Commit-list mode is selected
- **WHEN** runtime JSON defines `report_mode` as `commit_list`
- **THEN** the system selects deterministic commit-list document generation

#### Scenario: Report mode is invalid
- **WHEN** runtime JSON defines an unknown, empty, blank, or non-string `report_mode`
- **THEN** the system exits with a configuration error before validating analysis paths or running Git

### Requirement: Commit-list mode has no AI or diff configuration requirement
The system SHALL NOT require, resolve, validate, read, or retain `ai_config_path`, `env_file_path`, or `temp_diff_dir` in `commit_list` mode, even when those fields are present in runtime JSON.

#### Scenario: Mode-specific fields are absent
- **WHEN** a valid `commit_list` runtime configuration omits AI, environment, and temporary-diff fields
- **THEN** the system validates the common configuration and can generate the report

#### Scenario: Ignored fields reference unusable resources
- **WHEN** a `commit_list` runtime configuration contains AI, environment, or temporary-diff values that are malformed or reference missing or unusable resources
- **THEN** the system ignores those fields and does not access their referenced resources

### Requirement: Commit-list generation never performs diff or AI work
The system SHALL compose `commit_list` content from accepted commit metadata without grouping hashes for diffs, invoking `git show`, creating or reading diff artifacts, resolving AI credentials, constructing an AI client, or performing summarization or reduction.

#### Scenario: Qualifying commits exist
- **WHEN** one or more commits pass contributor and module filtering in `commit_list` mode
- **THEN** the system generates the PDF without any diff or AI operation

#### Scenario: No commits qualify
- **WHEN** no commit passes contributor and module filtering in `commit_list` mode
- **THEN** the system generates the descriptive empty PDF without any diff or AI operation

### Requirement: Commit-list content is organized only by configured module
The system SHALL render non-empty sections and modules in configured order and SHALL render each module's qualifying commits in oldest-first extraction order without author subgroups.

#### Scenario: Multiple modules and authors qualify
- **WHEN** qualifying commits from multiple approved authors map to multiple configured modules
- **THEN** the PDF groups entries by section and module only, preserves module JSON order and within-module commit order, and does not render author headings or author emails

#### Scenario: Configured module has no qualifying commit
- **WHEN** a configured module has no accepted commit
- **THEN** the module and any otherwise empty section are omitted

### Requirement: Each commit entry preserves exact traceability data
The system SHALL render each qualifying commit as its exact Git subject followed by an em dash and its complete Git object ID, SHALL retain the matched module prefix in the subject, and SHALL NOT include the commit body or diff.

#### Scenario: Commit subject contains its module prefix
- **WHEN** the accepted subject is `Pix: committed feature` and its full object ID is available
- **THEN** the module contains one entry formatted as `Pix: committed feature — <full object ID>`

#### Scenario: Subject and object ID require safe layout
- **WHEN** a subject contains PDF-markup-sensitive or supported non-ASCII text or the repository uses an object ID longer than a SHA-1 ID
- **THEN** the subject is escaped, supported text renders through embedded fonts, and the complete object ID is rendered without truncation

### Requirement: Commit-list PDF retains release context and safe output
The system SHALL title the document `Release Commit Report` and SHALL retain repository identification, total qualifying-change count, UTC date range, ISO-week context, module counts, module date ranges, descriptive empty-report behavior, output-path containment, and atomic PDF replacement.

#### Scenario: Commit-list report contains qualifying commits
- **WHEN** accepted commits are composed in `commit_list` mode
- **THEN** the PDF contains the existing report and module context followed by the commit entries

#### Scenario: Commit-list report is empty
- **WHEN** no commits qualify in `commit_list` mode
- **THEN** the PDF identifies the repository, shows a zero count, omits unavailable date and week rows, and displays `No qualifying changes.`
