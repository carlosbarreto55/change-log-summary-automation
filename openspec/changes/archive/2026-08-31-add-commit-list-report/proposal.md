## Why

The generator currently turns qualifying commits into PDF content only through diff generation and an LLM summarization backend. Some release environments need a deterministic, traceable PDF that requires no LLM, credentials, source-bearing diff artifacts, or natural-language generation while preserving the existing Git range, contributor, module, and report-context behavior.

## What Changes

- Add an explicit `commit_list` report mode that produces a PDF from filtered commit subjects and full Git object IDs without invoking diff generation or an LLM.
- Keep existing runtime JSON backward compatible by treating a missing report mode as `ai_summary`.
- Allow AI- and diff-specific runtime fields to remain present in `commit_list` configurations while ignoring their values and referenced resources completely.
- Preserve configured section and module ordering, repository metadata, qualifying-change counts, UTC date ranges, and ISO-week context in the non-LLM report.
- Render each qualifying commit under its module as its exact Git subject followed by its full object ID, without author subgroups.
- Make temporary diff path requirements conditional on the AI summary workflow and retain existing output-path containment and atomic PDF replacement guarantees.

## Capabilities

### New Capabilities

- `commit-list-pdf-report`: Defines report-mode selection, strict non-LLM execution, commit-list content and ordering, mode-specific configuration, and empty-report behavior.

### Modified Capabilities

- `bounded-ai-summarization`: Scope AI configuration, diff generation, and summarization requirements to `ai_summary` runs so `commit_list` runs never initialize an AI backend.
- `configurable-release-sections`: Generalize post-filter behavior and ordered module output from AI summaries to the selected report content while preserving exact-email and prefix filtering.
- `pdf-release-notes`: Allow the PDF renderer to emit either AI summaries or deterministic commit entries beneath configured modules.
- `read-only-repository-analysis`: Require and validate a temporary analysis path only for workflows that generate temporary diff artifacts.
- `release-report-context`: Place module count and date context before the selected module content rather than specifically before an AI-generated summary.

## Impact

This affects runtime configuration types and validation, path validation, release workflow orchestration, release-document domain content, ReportLab rendering, declared workflow diagnostics, JSON examples, package documentation, and unit/context/Linux integration/packaging tests. It adds no dependency and does not change Git selection, AI backend behavior, the CLI `--config` interface, or existing AI-summary JSON behavior.
