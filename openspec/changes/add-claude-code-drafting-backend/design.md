## Context

The current workflow loads one `AIConfig`, creates `OpenAIChatClient` when qualifying diff files exist, sends bounded module-specific chunks through the `SummaryClient` protocol, reduces partial summaries, composes a document, and writes a PDF. `AIConfig` always requires `api_url`, `model`, `api_key_env_var`, and `prompt`, and the default client resolves the named key from the environment or configured env file. This prevents use in the target environment even though that environment has Claude Code authenticated through a Claude subscription.

Claude Code documents non-interactive print mode, JSON and JSON-Schema output, tool restriction, safe mode, and non-persistent sessions at https://code.claude.com/docs/en/cli-usage. Its authentication documentation at https://code.claude.com/docs/en/authentication states that Claude subscription OAuth credentials can be used by the CLI. Authentication remains owned by Claude Code: this project will neither read its credential store nor mint, refresh, validate, log, or persist API keys or OAuth tokens.

This change is branched from `main` and preserves the current one-command workflow. Two unmerged efforts need later reconciliation without being copied into this branch: configuration onboarding must eventually emit and validate the backend-specific template, and release governance must persist the execution provenance in its draft bundle. This design exposes provenance through the summarization result so those consumers do not need to inspect the Claude process or credentials.

## Goals / Non-Goals

**Goals:**

- Allow qualifying releases to be summarized through an authenticated local Claude Code CLI without an LLM API key in project configuration.
- Preserve current OpenAI-compatible configurations and the existing `SummaryClient`-based bounded orchestration.
- Keep every source-bearing request module-specific, character-bounded, sequential, tool-less, non-persistent, and isolated in a fresh process.
- Fail closed when the executable, required CLI behavior, authentication, process result, or structured response is unavailable or invalid.
- Provide secret-free backend, requested-model, and Claude Code version provenance to workflow and draft consumers.
- Cover behavior without requiring Claude installation or live inference in the mandatory test suites.

**Non-Goals:**

- Automating Claude Desktop, Claude in a browser, a project skill, MCP, or the Claude Agent SDK.
- Reading, configuring, selecting, or reporting Claude's active authentication method.
- Guaranteeing model availability, subscription capacity, response determinism, exact token counts, or exact cost.
- Reusing Claude sessions, conversations, caches, or process state across requests.
- Making the Claude executable path or an arbitrary command configurable.
- Adding a new draft file, provider sidecar, or PDF section to the current one-shot workflow; the planned governance lifecycle is the persistence boundary for draft provenance.
- Removing the existing OpenAI-compatible backend.

## Decisions

### 1. AI configuration is a discriminated backend configuration

The loader will accept `backend: "claude_code"` or `backend: "openai_compatible"`. A missing `backend` selects `openai_compatible` so existing committed JSON and external installations retain their current behavior.

Both variants require a non-empty `model`, non-empty `prompt`, and positive `max_diff_characters_per_request`. The OpenAI-compatible variant additionally requires `api_url` and `api_key_env_var`. The Claude Code variant does not require or resolve either field. Existing inline-secret prohibitions remain common to both variants.

Runtime representation will use separate immutable configuration dataclasses behind a small union or common protocol rather than one object containing meaningful and meaningless optional fields. This keeps invalid combinations out of workflow code and lets client construction dispatch exhaustively on the backend.

Alternative considered: infer Claude Code from a missing endpoint or key-variable field. Rejected because malformed OpenAI configuration would silently select a different execution path.

Alternative considered: make `backend` immediately mandatory. Rejected because adding a backend should not invalidate every existing configuration and test fixture when the current behavior has an unambiguous compatibility default.

### 2. Claude Code is an external executable adapter, not a Python dependency

A `ClaudeCodeClient` will implement the existing `SummaryClient` operations and use a small injected process-runner boundary. Production uses `subprocess` with an argument sequence and `shell=False`; unit tests use a recording runner. The executable name is fixed as `claude` and resolved through the child process environment. The Python package will not add the Claude Agent SDK or an HTTP client for Anthropic.

The client probes `claude --version` once before its first source-bearing request and requires a successful non-empty version. It does not call an authentication-status command because that could expose account details, would duplicate Claude's credential policy, and would still race the actual request. Authentication and capacity errors are handled from the inference process result.

Alternative considered: use the Claude Agent SDK. Rejected because the installed CLI is the capability available in the target environment, while an SDK adds dependency, version, and authentication surface not needed for two request operations.

Alternative considered: accept a configurable executable or shell command. Rejected because it creates a command-injection and support surface without a current requirement.

### 3. Every inference process is restricted and receives source only on standard input

Each `summarize` or `reduce` call starts a new `claude -p` process with a fixed argument vector including:

- non-interactive print mode;
- JSON output and the exact summary JSON Schema;
- the requested model;
- safe mode to suppress project and user customizations that could change behavior;
- disabled slash commands;
- an empty built-in-tool set;
- an explicit MCP-tool denial;
- disabled session persistence.

No resume, continue, session ID, plugin, MCP configuration, permission bypass, browser, or remote-session flag is permitted. The configured system instruction may be passed as a fixed argument or dedicated prompt input, but module names, diffs, and partial summaries are assembled into the user message and written through standard input only. The process runs from a temporary empty working directory so repository discovery and path-specific configuration are outside its context even if a future CLI regression weakens safe mode. The temporary directory is removed after success or failure.

The child inherits the operator's environment so Claude Code can use its supported authentication mechanisms. Project code passes no key or token, does not open Claude credential files, and does not inspect or redact the environment by value. Documentation will warn that Claude Code itself chooses credentials according to its precedence rules and that operators can verify their intended login with Claude Code before running this project.

Alternative considered: pass the diff as a positional prompt. Rejected because source would appear in the process argument list and could exceed platform argument limits.

Alternative considered: use `--bare`. Rejected because bare mode retains built-in tools and changes support for some authentication sources; safe mode plus explicit tool and MCP removal is the narrower contract.

### 4. Fresh processes enforce the existing request boundary

The current bounded orchestration remains responsible for chunk order, maximum characters, and same-module reduction. `ClaudeCodeClient.summarize` and `.reduce` are stateless request operations: each starts and waits for a distinct process. The client retains only immutable configuration and the version string; it retains no session identifier, prompt history, response history, or module state.

This costs one CLI startup per request but makes the existing rule that modules never share AI context enforceable at the process boundary. Requests remain sequential, so there is no new concurrency or rate-limit behavior.

Alternative considered: one persistent CLI conversation per run or module. Rejected because conversation history would make later payloads depend on earlier requests and could expose content across reductions or modules.

### 5. Only schema-valid final output becomes release content

The requested JSON Schema allows one object with one required non-empty `summary` string and no additional properties. Claude Code's JSON envelope is parsed according to the documented structured-output field, and the project validates the extracted object again rather than trusting exit status alone. Diagnostic, intermediate, tool, and Markdown output are never accepted as the summary.

The adapter maps executable-not-found, version failure, timeout, nonzero exit, malformed JSON, missing structured output, schema mismatch, and empty summary to stable `AISummarizationError` categories. Expected CLI handling continues to print a concise message without a Python traceback. Error messages may name the failure category and executable version but do not echo standard input, raw environment values, full stdout, or full stderr. Temporary working directories are cleaned in all cases.

Alternative considered: use plain text output. Rejected because CLI notices or diagnostic text could be mistaken for release content and output-shape changes would be difficult to detect.

### 6. Summarization returns explicit execution provenance

The summarization layer will return an immutable outcome containing the module-summary mapping and secret-free execution provenance. Common provenance contains `backend` and requested `model`; Claude Code provenance also contains the detected CLI version. It contains no endpoint authorization, API-key variable value, OAuth token, environment value, credential path, user identity, or subscription information.

The current one-shot workflow carries this outcome through composition but does not create a new sidecar solely to persist it. When the release-governance lifecycle is merged, its draft bundle must persist this provenance beside generated summaries and bind it into the draft digest. Recording the requested model rather than claiming a resolved model keeps the project from inferring behavior not guaranteed by the CLI response.

Alternative considered: let each downstream consumer introspect its client. Rejected because consumers should depend on an immutable completed result, not provider-specific client internals or a process that may no longer exist.

### 7. Mandatory tests use recording and fake process boundaries

Unit tests will keep class-level concerns separate: backend configuration validation, command-vector construction, stdin isolation, version probing, structured parsing, provenance, and error mapping use an injected recording runner. Context tests will exercise workflow selection, bounded summarize/reduce calls, no-qualifying behavior, cleanup, and PDF gating with a fake executable or process adapter.

The required integration configuration remains JSON and targets the separately managed public Linux repository fixture. A deterministic fake `claude` executable placed first on the test `PATH` will record sanitized invocation metadata and return schema-valid output, proving the real subprocess and workflow boundary without network inference. A separate live Claude Code integration may run only behind an explicit opt-in flag when an operator has installed and authenticated Claude Code; its artifacts must exclude prompts, diffs, credentials, and raw process output.

## Compatibility Contract (resolved by the 2026-08-28 spike)

A source-free spike ran on an authenticated Claude Code installation and fixed the following contract:

**Minimum supported Claude Code version:** `2.1.251`. The version probe `claude --version` exits `0` and prints `2.1.251 (Claude Code)`; the leading dotted-numeric token is the comparable version. Versions below `2.1.251` are unsupported because the flag set below was validated only from that version.

**Restricted invocation validated by the spike:** `claude -p --output-format json --json-schema <schema> --model <model> --safe-mode --disable-slash-commands --tools "" --strict-mcp-config --no-session-persistence --system-prompt <prompt>`, executed with `shell=False` from an empty temporary working directory, with the entire source-bearing user message written to standard input. `--tools ""` empties the built-in tool set, `--strict-mcp-config` without any `--mcp-config` denies every MCP server, `--safe-mode` disables project and user customizations, and `--no-session-persistence` prevents session storage in print mode.

**Schema-valid success envelope:** a successful run exits `0` and prints one JSON object on standard output with, among other diagnostic fields, `"type": "result"`, `"subtype": "success"`, `"is_error": false`, and a `"structured_output"` field holding the schema-validated object (`{"summary": "..."}`). The `"result"` field duplicates that object as a JSON-encoded string. The parser MUST read `structured_output` only, MUST require `type == "result"`, `subtype == "success"`, and `is_error == false`, and MUST re-validate the extracted object against the summary schema. All other envelope fields (session, usage, cost, timing, model-usage diagnostics) are ignored and never persisted.

A sanitized success-envelope fixture (placeholder identifiers, no account, credential, prompt, diff, cost, or raw diagnostic content) is committed at `tests/fixtures/claude_code/envelope_success.json`.

## Risks / Trade-offs

- [Claude Code flags or JSON envelopes change between versions] -> Record the version, test the complete argument and parsing contract with a fake executable, document a supported version floor after a live spike, and fail closed on unknown output.
- [Subscription login expires or usage limits are reached] -> Treat the request as an expected summarization failure, preserve the prior PDF, and direct operators to validate Claude Code independently without exposing account data.
- [A fresh process per request adds startup latency] -> Accept the cost to preserve request isolation; keep execution sequential and avoid speculative pooling or session reuse.
- [Diff content can prompt-inject the model] -> Remove all tools and external context, constrain the response schema, and continue human review; generated prose remains non-authoritative.
- [No API key does not mean local inference] -> Document that approved diff content is still sent by Claude Code to Anthropic or the operator's configured provider under its account and policy.
- [An inherited environment can cause Claude Code to select a credential other than subscription OAuth] -> Keep credential selection outside project scope, document Claude's precedence, and never claim or persist an authentication method.
- [The onboarding and governance changes evolve before merge] -> Rebase after those prerequisites land, update their backend-specific template and draft-provenance contracts, and rerun strict OpenSpec validation rather than duplicating their artifacts here.
- [The current development environment has no `claude` executable] -> Make a version/flag/output spike the first implementation gate before production code and keep all mandatory tests independent of a live installation.

## Migration Plan

1. Confirm the supported Claude Code version and exact non-interactive structured-output envelope with a local authenticated installation before writing production adapter code.
2. Add backend-discriminated configuration with missing `backend` mapped to `openai_compatible`; run existing tests unchanged as the compatibility baseline.
3. Add the process adapter, explicit summarization outcome/provenance, backend factory, and workflow selection behind `backend: "claude_code"`.
4. Add one example Claude Code AI JSON file and update README/security guidance; do not place a key, OAuth token, or credential path in configuration.
5. After configuration onboarding merges, update its template, validation diagnostics, inspection output, and tests to understand both backend shapes.
6. After release governance merges, store backend, requested model, and Claude Code version in draft provenance and bind it into draft integrity validation.
7. Roll back operationally by selecting `openai_compatible` with the prior fields or installing the previous package version; no repository or PDF data migration is required.

## Open Questions

- ~~What minimum Claude Code version simultaneously supports the chosen safe-mode, tool-removal, no-session-persistence, JSON-Schema, and structured-output flags?~~ Resolved by the spike: `2.1.251` supports the complete flag set; see the Compatibility Contract section.
- ~~What exact documented JSON field contains schema-constrained output in that supported version?~~ Resolved by the spike: the top-level `structured_output` field of the single `type: "result"` JSON envelope; see the Compatibility Contract section.
