## ADDED Requirements

### Requirement: AI diff size limit is configured in JSON
The system SHALL load a positive integer `max_diff_characters_per_request` from the configured AI JSON file.

#### Scenario: Valid request limit
- **WHEN** AI configuration contains a positive integer request limit
- **THEN** the system uses it to bound diff content sent in each summarization request

#### Scenario: Invalid request limit
- **WHEN** the request limit is missing, non-integer, or not positive
- **THEN** the system exits with a configuration error before fetching or rebasing the repository

### Requirement: Oversized module diffs are split without category mixing
The system SHALL divide a module diff into ordered chunks whose diff content does not exceed the configured character limit and SHALL NOT place content from different modules in the same chunk.

#### Scenario: Module diff is within the limit
- **WHEN** a module diff does not exceed the configured limit
- **THEN** the system sends it as one module-specific summarization request

#### Scenario: Module diff exceeds the limit
- **WHEN** a module diff exceeds the configured limit
- **THEN** the system splits it in commit order, preferring commit boundaries and using line boundaries when one commit is itself oversized

#### Scenario: One commit exceeds the limit
- **WHEN** one accepted commit's diff exceeds the configured limit
- **THEN** the system creates multiple ordered chunks without dropping that commit's diff content

### Requirement: Chunk summaries are reduced to one module summary
The system SHALL combine multiple chunk summaries through bounded module-specific reduction requests until exactly one final summary remains for the module.

#### Scenario: Multiple chunk summaries
- **WHEN** a module produces more than one initial chunk summary
- **THEN** the system reduces those summaries in order without including another module's content

#### Scenario: Reduction input exceeds the limit
- **WHEN** the combined partial summaries exceed the configured request limit
- **THEN** the system performs additional bounded reduction levels until one module summary remains

### Requirement: Unauthorized and unmapped content never reaches AI
The system SHALL generate AI chunks only from commits that passed both exact-email approval and configured-prefix classification.

#### Scenario: Filtered commits are present in the release range
- **WHEN** the release range contains unapproved-author or unmapped-prefix commits
- **THEN** none of their diff content appears in an initial or reduction AI request
