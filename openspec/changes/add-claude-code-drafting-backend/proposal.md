## Why

The generator currently requires an OpenAI-compatible endpoint and API-key environment variable whenever qualifying changes need summarization. The target environment has an authenticated Claude Code installation and Claude subscription but cannot provide an LLM API key, so release generation needs a supported backend that delegates inference to the local `claude` executable without reading or managing its credentials.

## What Changes

- Add `claude_code` as a JSON-selectable summarization backend while retaining the existing OpenAI-compatible backend for current users.
- Make AI configuration backend-specific: Claude Code requires a requested model, prompt, and positive request-size limit but does not require an API URL or API-key environment-variable name.
- Invoke `claude -p` without a shell, send source-bearing request content only through standard input, request schema-validated structured output, and translate expected process failures into concise summarization errors.
- Disable built-in tools, MCP tools, project customizations, slash commands, and session persistence for every Claude Code inference process.
- Use one fresh Claude Code process for every initial summarization and reduction request so module and request context cannot carry across calls.
- Record the selected backend, detected Claude Code version, and requested model as secret-free execution provenance available to the release workflow and future draft artifacts.
- Preserve the existing behavior that no backend is initialized and no credential is needed when no commit qualifies.
- Add unit, context, and JSON-driven Linux integration coverage, with live Claude execution remaining explicit and opt-in.

## Capabilities

### New Capabilities

- `claude-code-drafting-backend`: Defines backend-specific configuration, restricted Claude Code process execution, structured result handling, isolation, error behavior, and secret-free execution provenance.

### Modified Capabilities

- `bounded-ai-summarization`: Allow bounded initial and reduction requests to use a selected summarization backend without weakening size, ordering, authorization, or module-isolation guarantees.

## Impact

This affects AI configuration validation and templates, summarization clients, workflow client construction, CLI error handling, provider provenance, documentation, and unit/context/Linux integration tests. Claude Code becomes an external runtime prerequisite only when `backend` is `claude_code`; the Python package gains no Claude SDK dependency and never reads Claude credential storage. Existing OpenAI-compatible configurations remain supported, and missing `backend` retains their current behavior.
