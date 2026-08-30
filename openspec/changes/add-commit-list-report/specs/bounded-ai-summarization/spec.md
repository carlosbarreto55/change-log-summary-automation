## MODIFIED Requirements

### Requirement: AI diff size limit is configured in JSON
The system SHALL load a positive integer `max_diff_characters_per_request` from the configured AI JSON file only when the selected report mode is `ai_summary`, and SHALL NOT load an AI JSON file when the selected report mode is `commit_list`.

#### Scenario: Valid request limit
- **WHEN** `ai_summary` configuration contains a positive integer request limit
- **THEN** the system uses it to bound diff content sent in each summarization request

#### Scenario: Invalid request limit
- **WHEN** `ai_summary` configuration has a request limit that is missing, non-integer, or not positive
- **THEN** the system exits with a configuration error before fetching or rebasing the repository

#### Scenario: Commit-list report is selected
- **WHEN** runtime configuration selects `commit_list`
- **THEN** the system does not require or read an AI configuration or request-size limit
