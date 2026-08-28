## ADDED Requirements

### Requirement: Claude Code backend is selected through JSON
The system SHALL support `claude_code` as an AI configuration `backend`, SHALL require a non-empty requested `model`, non-empty `prompt`, and positive integer `max_diff_characters_per_request` for that backend, and SHALL NOT require an API URL or API-key environment-variable name. A configuration without `backend` SHALL retain the existing OpenAI-compatible behavior.

#### Scenario: Claude Code configuration is valid without API settings
- **WHEN** AI configuration selects `claude_code` and contains a valid model, prompt, and request limit but no `api_url` or `api_key_env_var`
- **THEN** configuration validation succeeds without reading an environment variable or Claude credential storage

#### Scenario: Existing configuration omits backend
- **WHEN** AI configuration contains the existing valid OpenAI-compatible fields and omits `backend`
- **THEN** the system treats it as `openai_compatible` and preserves its current behavior

#### Scenario: Claude Code configuration is incomplete
- **WHEN** AI configuration selects `claude_code` but its model, prompt, or positive request limit is missing or invalid
- **THEN** the system reports a configuration error before repository synchronization or summarization

#### Scenario: Backend is unsupported
- **WHEN** AI configuration names a backend other than `claude_code` or `openai_compatible`
- **THEN** the system reports a configuration error before repository synchronization or summarization

### Requirement: Claude Code availability is required only for active drafting
The system SHALL resolve the fixed `claude` executable from the process environment and obtain its non-empty version before the first Claude Code summarization request, but SHALL NOT inspect or initialize Claude Code when no approved and mapped diff requires summarization or when another backend is selected.

#### Scenario: Claude Code backend has qualifying diffs
- **WHEN** `claude_code` is selected and at least one approved and mapped diff requires summarization
- **THEN** the system verifies that `claude` is executable and obtains its version before sending source content to it

#### Scenario: Claude executable is unavailable
- **WHEN** `claude_code` is selected for qualifying diffs but the executable cannot be found, started, or versioned
- **THEN** the system returns a concise summarization error without attempting an OpenAI-compatible request or generating a final PDF

#### Scenario: No commit qualifies
- **WHEN** `claude_code` is configured but no selected commit passes both author approval and module mapping
- **THEN** the system does not execute `claude`, require a Claude login, or read any credential and still produces the existing no-qualifying-changes document

### Requirement: Claude Code requests use a restricted subprocess
For every initial or reduction request, the system SHALL start `claude -p` directly from an argument vector without a command shell, SHALL transmit all source-bearing user content through standard input, and SHALL select flags that disable built-in tools, MCP tools, project customizations, slash commands, and session persistence.

#### Scenario: Initial diff is summarized
- **WHEN** the backend sends one bounded module diff chunk to Claude Code
- **THEN** the diff is absent from process arguments, is written only to that process's standard input, and the process has no enabled built-in or MCP tool

#### Scenario: Partial summaries are reduced
- **WHEN** the backend sends one bounded module-specific reduction payload to Claude Code
- **THEN** the reduction content is absent from process arguments, is written only to that process's standard input, and uses the same restricted execution flags

#### Scenario: Source content contains shell syntax
- **WHEN** a diff or partial summary contains shell metacharacters, substitutions, flags, or newlines
- **THEN** the content remains inert standard-input data because no shell parses it and it cannot alter the Claude Code argument vector

### Requirement: Every request has isolated Claude Code context
The system SHALL use a new non-persistent Claude Code process for each initial summarization and each reduction request, SHALL NOT resume or continue any Claude session, and SHALL preserve the existing sequential request order.

#### Scenario: Module requires several chunks
- **WHEN** one module produces multiple initial chunks and one or more reduction requests
- **THEN** every request uses a distinct fresh process and receives only its own module-specific payload

#### Scenario: Several modules qualify
- **WHEN** two or more modules require summarization
- **THEN** no process for one module receives a prompt, response, session identifier, or conversation history from another module

### Requirement: Claude Code output is schema validated
The system SHALL request JSON-Schema-constrained output containing exactly one non-empty summary string, SHALL parse only the final structured result from a successful process, and SHALL reject nonzero exit status, timeout, malformed JSON, schema mismatch, or empty summary as a summarization failure.

#### Scenario: Structured output is valid
- **WHEN** Claude Code exits successfully with a schema-valid non-empty summary
- **THEN** the backend returns the normalized summary to the existing bounded summarization flow

#### Scenario: Structured output is unusable
- **WHEN** Claude Code exits successfully but its final output is malformed, violates the requested schema, or contains an empty summary
- **THEN** the system reports a concise summarization error and does not treat diagnostic or intermediate output as release content

#### Scenario: Claude Code process fails
- **WHEN** Claude Code cannot authenticate, reaches a usage limit, times out, or exits nonzero
- **THEN** the system reports a concise backend failure without exposing source payloads, credentials, raw environment values, or an expected-error Python traceback

### Requirement: Claude Code execution provenance is secret free
Successful Claude Code summarization SHALL produce provenance containing the backend identifier `claude_code`, the detected Claude Code version, and the requested model. The release workflow SHALL carry this provenance with the completed summaries, and every persisted draft artifact that contains those summaries SHALL record it without credential data.

#### Scenario: Claude Code summarization completes
- **WHEN** every required initial and reduction request succeeds
- **THEN** the completed summarization result identifies `claude_code`, the detected executable version, and the requested model used for the run

#### Scenario: Provenance is persisted in a draft
- **WHEN** a workflow persists a draft artifact containing Claude Code-generated summaries
- **THEN** the draft records the exact backend identifier, detected version, and requested model and contains no API key, OAuth token, authorization value, environment value, or Claude credential-store content

#### Scenario: Existing OpenAI-compatible backend is used
- **WHEN** the selected backend is `openai_compatible`
- **THEN** no Claude Code version is required or attributed to the generated summaries
