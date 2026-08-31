## Purpose

Define how authorized commits are mapped into configured modules and ordered output sections for release documentation.
## Requirements
### Requirement: Approved contributors are configured by exact email
The system SHALL include a commit only when its Git author email exactly equals an entry in `approved_author_emails` from the configured users JSON file.

#### Scenario: Approved author
- **WHEN** a selected commit's author email exactly matches a configured approved email
- **THEN** the commit remains eligible for module classification

#### Scenario: Unapproved author
- **WHEN** a selected commit's author email does not exactly match a configured approved email
- **THEN** the commit is discarded before diff generation, AI processing, or commit-list composition

### Requirement: Modules and output sections are configured in JSON
The system SHALL load each module's non-empty `name`, non-empty list of `tags`, and non-empty `section` from the configured module JSON file.

#### Scenario: Valid module entries
- **WHEN** every module entry provides a name, at least one string tag, and a section
- **THEN** the system uses those entries for classification and output composition

#### Scenario: Missing module section
- **WHEN** any module entry omits `section` or provides an empty section
- **THEN** the system exits with a configuration error before fetching or rebasing the repository

### Requirement: Commit subjects are classified by configured prefix
The system SHALL assign an approved commit to the first configured module whose non-empty tag is a case-sensitive prefix of the commit subject.

#### Scenario: Subject matches a configured prefix
- **WHEN** an approved commit subject starts with a configured module tag
- **THEN** the commit is assigned to that module

#### Scenario: Subject matches no configured prefix
- **WHEN** an approved commit subject starts with none of the configured module tags
- **THEN** the commit is discarded before diff generation, AI processing, or commit-list composition

### Requirement: Release document ordering follows module configuration
The system SHALL order modules according to their JSON order and SHALL order sections by the first appearance of each distinct section in that module order, independently of whether modules contain AI summaries or commit-list entries.

#### Scenario: Multiple modules share a section
- **WHEN** two included modules reference the same section
- **THEN** the release document contains one section heading with both module contents in configured module order

#### Scenario: Configured module has no accepted commits
- **WHEN** a module has no commits that pass both email and prefix filtering
- **THEN** the module and any otherwise empty section are omitted from the release document

#### Scenario: No commits qualify
- **WHEN** no selected commit passes both filters
- **THEN** the release document contains its mode-specific title and a clear `No qualifying changes.` message
