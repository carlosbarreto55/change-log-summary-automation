## MODIFIED Requirements

### Requirement: AI diff size limit is configured in JSON
The system SHALL load a positive integer `max_diff_characters_per_request` from the configured AI JSON file for the selected backend and SHALL use that value to bound every initial summarization and reduction payload independently of whether `openai_compatible` or `claude_code` performs the request.

#### Scenario: Valid request limit
- **WHEN** AI configuration for the selected backend contains a positive integer request limit
- **THEN** the system uses it to bound diff content and partial-summary content sent in each request

#### Scenario: Invalid request limit
- **WHEN** the request limit is missing, non-integer, or not positive
- **THEN** the system exits with a configuration error before fetching or rebasing the repository

#### Scenario: Claude Code backend is selected
- **WHEN** valid AI configuration selects `claude_code`
- **THEN** initial and reduction standard-input payloads obey the same configured character limit and module boundaries as the OpenAI-compatible backend
