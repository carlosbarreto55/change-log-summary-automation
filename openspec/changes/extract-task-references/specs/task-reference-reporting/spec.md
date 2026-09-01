## ADDED Requirements

### Requirement: Accepted commit subjects provide task references
The system SHALL extract case-sensitive task references from the subjects of commits that passed both contributor approval and module classification in `ai_summary` and `commit_list` modes. When no custom patterns are configured, it SHALL recognize `WLT-` followed by digits, `WLTM-` followed by digits, and `P` followed by six digits, a hyphen, and more digits. Task-reference extraction SHALL NOT invoke an AI backend.

#### Scenario: Accepted subjects contain default task references
- **WHEN** accepted commits contain `WLT-123`, `WLTM-456`, or `P260820-05441` in their subjects
- **THEN** the release document contains those identifiers associated with each source commit's configured module

#### Scenario: Filtered commit contains a task-like identifier
- **WHEN** a commit subject contains a recognized identifier but the commit does not pass contributor approval or module classification
- **THEN** that identifier is absent from the release document

#### Scenario: Commit-list mode extracts task references
- **WHEN** `commit_list` mode has accepted subjects containing recognized identifiers
- **THEN** the system extracts the identifiers without constructing or invoking an AI backend

### Requirement: Task-reference patterns are optionally configured in module JSON
The system SHALL accept an optional `task_patterns` object beside `modules`, with non-empty valid regular expressions under the supported keys `wlt`, `wltm`, and `plm`. Configured patterns SHALL replace the defaults, and invalid configured expressions SHALL fail configuration validation before Git analysis.

#### Scenario: Module configuration omits task patterns
- **WHEN** a valid module JSON file has no `task_patterns` object
- **THEN** the system uses all default task-reference patterns

#### Scenario: Custom task patterns are valid
- **WHEN** module JSON provides valid expressions with the capture groups required for their supported keys
- **THEN** the system uses those configured expressions instead of the defaults

#### Scenario: Custom task pattern is invalid
- **WHEN** a configured task pattern is empty, not a string, or not a valid regular expression
- **THEN** configuration validation fails before path preparation or Git analysis

### Requirement: Task-reference occurrences are aggregated by module
The system SHALL count every recognized occurrence by the pair of canonical reference identifier and classified module name, and SHALL order the resulting references deterministically by module name and reference identifier.

#### Scenario: One identifier occurs repeatedly in one module
- **WHEN** the same recognized identifier occurs more than once among accepted subjects classified into one module
- **THEN** the task reference for that identifier and module reports the total occurrence count

#### Scenario: One identifier occurs in multiple modules
- **WHEN** the same recognized identifier occurs in accepted subjects classified into different modules
- **THEN** each module has a separate task reference and occurrence count for that identifier

### Requirement: PDF renders a final task-reference section only when needed
The system SHALL render non-empty task references in a final `Task References` section after all configured module sections, grouped by module with the occurrence count for each identifier. It SHALL omit the task-reference section when no accepted subject contains a recognized identifier.

#### Scenario: Recognized references exist
- **WHEN** the composed release document contains one or more task references
- **THEN** the PDF renders `Task References` after the configured module sections and shows each reference under its module with its count

#### Scenario: No recognized references exist
- **WHEN** no accepted subject contains a recognized task reference
- **THEN** the PDF contains no `Task References` section
