## MODIFIED Requirements

### Requirement: Runtime output is a configured PDF path
The system SHALL require `output_path` in runtime JSON to resolve to a local path with a `.pdf` or `.md` extension compared case-insensitively, SHALL select the matching final-output format from that extension, and SHALL reject every other extension before path validation or Git activity.

#### Scenario: Relative output path
- **WHEN** `output_path` is relative and has a supported extension
- **THEN** the system resolves it relative to the runtime JSON file's directory

#### Scenario: Home-relative output path
- **WHEN** `output_path` begins with `~` and has a supported extension
- **THEN** the system expands it to the current user's home directory

#### Scenario: PDF output path
- **WHEN** `output_path` ends in `.pdf` using any letter case
- **THEN** the system selects the existing PDF exporter

#### Scenario: Markdown output path
- **WHEN** `output_path` ends in `.md` using any letter case
- **THEN** the system selects the Markdown exporter

#### Scenario: Unsupported output path
- **WHEN** `output_path` has neither a `.pdf` nor `.md` extension
- **THEN** the system exits with a configuration error before validating analysis paths or running Git
