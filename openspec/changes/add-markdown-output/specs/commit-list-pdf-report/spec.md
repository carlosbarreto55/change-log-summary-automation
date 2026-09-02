## MODIFIED Requirements

### Requirement: Commit-list generation never performs diff or AI work
The system SHALL compose `commit_list` content from accepted commit metadata and export it in the selected final-output format without grouping hashes for diffs, invoking `git show`, creating or reading diff artifacts, resolving AI credentials, constructing an AI client, or performing summarization or reduction.

#### Scenario: Qualifying commits exist
- **WHEN** one or more commits pass contributor and module filtering in `commit_list` mode with PDF or Markdown selected
- **THEN** the system generates the selected report without any diff or AI operation

#### Scenario: No commits qualify
- **WHEN** no commit passes contributor and module filtering in `commit_list` mode with PDF or Markdown selected
- **THEN** the system generates the descriptive empty report without any diff or AI operation

### Requirement: Commit-list content is organized only by configured module
The system SHALL render non-empty sections and modules in configured order and SHALL render each module's qualifying commits in oldest-first extraction order without author subgroups in every supported final-output format.

#### Scenario: Multiple modules and authors qualify
- **WHEN** qualifying commits from multiple approved authors map to multiple configured modules
- **THEN** the selected report groups entries by section and module only, preserves module JSON order and within-module commit order, and does not render author headings or author emails

#### Scenario: Configured module has no qualifying commit
- **WHEN** a configured module has no accepted commit
- **THEN** the module and any otherwise empty section are omitted

### Requirement: Each commit entry preserves exact traceability data
The system SHALL render each qualifying commit as its exact Git subject followed by an em dash and its complete Git object ID, SHALL retain the matched module prefix in the subject, SHALL NOT include the commit body or diff, and SHALL escape representation-sensitive syntax for the selected output format.

#### Scenario: Commit subject contains its module prefix
- **WHEN** the accepted subject is `Pix: committed feature` and its full object ID is available
- **THEN** the module contains one entry formatted as `Pix: committed feature — <full object ID>`

#### Scenario: Subject and object ID require safe layout
- **WHEN** a subject contains output-format-sensitive or non-ASCII text or the repository uses an object ID longer than a SHA-1 ID
- **THEN** the subject is escaped for the selected format, non-ASCII text renders without an encoding failure, and the complete object ID is rendered without truncation

### Requirement: Commit-list PDF retains release context and safe output
The system SHALL title the document `Release Commit Report` and SHALL retain repository identification, total qualifying-change count, UTC date range, ISO-week context, module counts, module date ranges, descriptive empty-report behavior, output-path containment, and atomic destination replacement in PDF and Markdown.

#### Scenario: Commit-list report contains qualifying commits
- **WHEN** accepted commits are composed in `commit_list` mode and either supported output format is selected
- **THEN** the final report contains the existing report and module context followed by the commit entries

#### Scenario: Commit-list report is empty
- **WHEN** no commits qualify in `commit_list` mode and either supported output format is selected
- **THEN** the final report identifies the repository, shows a zero count, omits unavailable date and week rows, and displays `No qualifying changes.`
