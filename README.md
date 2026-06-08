# Change Log Summary

Change Log Summary is an open-source release intelligence tool for development teams that need reliable, audit-friendly release notes from Git history.

The project helps Scrum teams turn implementation work into clear, categorized summaries that support sprint reviews, release planning, Product Owner reporting, and QA validation. Instead of asking engineers to manually reconstruct what changed, the tool filters commits, separates code diffs by configured product area, uses AI to summarize each focused payload, and composes the result into a Markdown release-notes document.

## Purpose

Modern product teams often need the same delivery information in different forms:

- Development teams need a consistent way to document what was implemented.
- Product Owners need concise summaries that connect technical changes to release scope.
- QA engineers need a practical view of what changed so they can plan validation and regression testing.
- Scrum teams need trustworthy release evidence for sprint reviews, release readiness, and stakeholder communication.

Change Log Summary is designed to reduce manual release-note work while keeping the process traceable, configurable, and safe for large repositories.

## What It Does

The tool processes a local Git repository and builds release-note content through a controlled pipeline:

1. Finds the latest configured release marker in Git history.
2. Extracts commits after that marker.
3. Filters commits by approved contributors.
4. Classifies commits by configurable product areas, services, modules, or release categories.
5. Discards unauthorized or unmapped commits before diff generation.
6. Groups accepted commits by category.
7. Generates focused Markdown diff files per category.
8. Sends each category-specific diff independently to an AI API.
9. Receives standalone AI summaries per category.
10. Composes final Markdown release notes from the AI-generated summaries.

This design avoids sending the full repository history to AI. Only locally filtered, category-specific diffs are sent.

## Who It Helps

### Development Teams

- Reduces repetitive release-note writing.
- Keeps release summaries tied to actual Git history.
- Encourages consistent commit classification and release documentation.

### Product Owners

- Provides clearer visibility into delivered scope.
- Helps translate technical changes into reviewable release summaries.
- Supports sprint review preparation and release communication.

### QA Engineers

- Highlights the areas of the product that changed.
- Helps identify validation focus and regression impact.
- Keeps QA planning aligned with the actual implementation diff.

### Scrum Teams

- Improves release transparency.
- Supports sprint review and release-readiness conversations.
- Creates a repeatable evidence trail from commit history to release notes.

## Key Features

- Git-based release range detection using a configurable release marker.
- Approved-contributor filtering before any AI request is made.
- Configurable commit classification by product area or release category.
- Separate diff generation for each accepted category.
- OpenAI-compatible AI summarization client.
- OpenCode Go live integration support through sanitized configuration.
- Environment-based API key loading with no secrets stored in JSON config.
- Optional live AI integration tests that preserve the latest generated assets for inspection.
- Final Markdown composition with grouped release-note sections.

## Current Status

The project now includes a CLI-driven end-to-end workflow for:

- JSON configuration loading.
- Git commit extraction and filtering.
- Commit grouping.
- Category-specific diff generation.
- AI summarization.
- Final Markdown composition.
- Temporary diff cleanup after successful output generation.

The workflow is executed from a single runtime JSON configuration file passed to the CLI.

## Requirements

- Python 3.9 or newer.
- Git CLI available on the host machine.
- A local clone of the target repository to analyze.
- An AI API key for live summarization.

## Installation

Create a virtual environment and install the project locally:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

The project exposes a console script:

```bash
change-log-summary --config path/to/workflow.json
```

## Configuration

Configuration is JSON-based so teams can adapt filtering and classification without changing Python code.

The project supports configuration for:

- Approved contributor identities.
- Release markers.
- Product areas, services, modules, or release categories.
- AI endpoint, model, prompt, and API key environment variable name.

AI configuration must not store secret values. Store only the environment variable name that contains the key.

The CLI requires one runtime workflow JSON file. Relative paths are resolved from the directory containing that runtime JSON file.

Example runtime workflow configuration:

```json
{
  "repository_path": "/absolute/path/to/target/repository",
  "user_config_path": "user.json",
  "module_config_path": "module.json",
  "release_marker_config_path": "releaseMarker.json",
  "ai_config_path": "ai.json",
  "temp_diff_dir": "../tmp/diffs",
  "output_path": "../output/release_notes.md",
  "env_file_path": "../.env.local"
}
```

Before reading release history, the workflow runs:

```bash
git -C <repository_path> fetch --prune
git -C <repository_path> rebase @{u}
```

If synchronization fails, processing stops before commit extraction, diff generation, AI requests, or output writing.

Example AI configuration shape:

```json
{
  "api_url": "https://provider.example/v1/chat/completions",
  "model": "summary-model",
  "api_key_env_var": "RELEASE_NOTES_AI_API_KEY",
  "prompt": "Summarize the provided category-specific Git diff for release notes."
}
```

Local secrets can be provided through the process environment or an ignored local env file.

## AI Integration

The AI client sends one request per generated category diff. Each request contains:

- A system prompt from configuration.
- A user message with the category name and the filtered diff content.
- The configured model identifier.

The client uses an OpenAI-compatible chat-completions request format and sends explicit JSON headers plus a stable user agent.

## Generated Assets

Optional live AI integration tests generate temporary inspection assets under the test assets directory.

Those assets can include:

- Generated category diff Markdown files.
- Sanitized AI request payloads.
- AI-generated Markdown summaries.

Generated assets are ignored by Git. Each live test run clears previous assets at the beginning and preserves the latest run afterward for manual inspection.

Request assets redact authorization headers so API keys are not written to disk.

## Testing

Run the unit test suite:

```bash
python3 -m unittest discover tests/unit
```

Run all non-live tests:

```bash
RUN_LIVE_AI_IT=0 python3 -m unittest discover tests
```

Run the optional live AI integration test:

```bash
RUN_LIVE_AI_IT=1 python3 -m unittest -v tests.integration.test_ai_summarization_live
```

Live AI tests require the configured AI API key environment variable to be available in the process environment or local env file.

## Security Notes

- Do not commit API keys.
- Do not store API keys in JSON configuration.
- Keep local env files outside version control.
- Generated test assets may contain source diffs and should be treated as local development artifacts.
- AI requests are intentionally split and filtered before leaving the local machine.

## Project Structure

```text
release_notes_generator/
  commits.py          Git history extraction, filtering, and grouping
  configuration.py    JSON configuration loading and validation
  diffs.py            Category-specific diff file generation
  summarization.py    AI summarization client and diff summarization flow
  composition.py      Final Markdown release-notes composition
  workflow.py         End-to-end workflow orchestration

tests/
  unit/               Class-level and module-level tests
  context/            Cross-module flow tests with mocked boundaries
  integration/        External repository and optional live AI tests
```

## Roadmap

Planned work includes:

- End-to-end workflow verification.
- Public release packaging and documented license terms.

## Contributing

Contributions should keep the project configurable, test-driven, and safe for repositories with sensitive code.

Before changing behavior:

- Add or update tests first.
- Keep unit tests separate from context and integration tests.
- Avoid committing secrets or generated assets.
- Prefer small, explicit changes over broad abstractions.

## License

This project is intended to be distributed as an open-source tool. Add the project license terms in a `LICENSE` file before public release.
