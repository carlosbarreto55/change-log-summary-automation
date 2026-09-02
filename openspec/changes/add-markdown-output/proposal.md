## Why

Release reports are currently available only as PDFs, which makes their content difficult to review in source-control tools, reuse in release pages, or process with text-based automation. Supporting Markdown gives operators a portable, diff-friendly output while preserving the same release information and existing PDF behavior.

## What Changes

- Accept a final `output_path` ending in `.md` as well as the existing `.pdf` extension, using the extension to select exactly one output format per run.
- Add a UTF-8 Markdown exporter for the existing renderer-independent release document.
- Render the same report metadata, configured sections, modules, mode-specific content, empty state, and task-reference information in Markdown as in PDF.
- Escape dynamic text so Markdown syntax in repository names, headings, summaries, commit subjects, and task references does not alter the intended report structure.
- Save Markdown through the same temporary-sibling and atomic-replacement guarantees as PDF output.
- Generalize PDF-specific workflow boundaries, exporter contracts, CLI wording, documentation, and tests without changing `report_mode` behavior or existing `.pdf` configurations.

## Capabilities

### New Capabilities

- `markdown-release-notes`: Defines Markdown format selection, content parity, safe UTF-8 serialization, escaping, and atomic output behavior.

### Modified Capabilities

- `pdf-release-notes`: Allows `.md` as a supported alternative final-output extension while preserving all existing `.pdf` rendering and atomic-write guarantees.
- `commit-list-pdf-report`: Makes deterministic commit-list reporting available in both PDF and Markdown without introducing diff or AI work.
- `release-report-context`: Requires repository, count, UTC date, ISO-week, module, and empty-report context in every supported output format.
- `read-only-repository-analysis`: Applies destination containment and failure behavior to either supported final report format rather than PDF alone.
- `repository-release-range`: Prevents every supported report output, not only PDF output, when range resolution fails.

## Impact

- Runtime configuration validation will recognize `.pdf` and `.md`; existing JSON remains compatible and no separate `output_format` field is introduced.
- The application exporter port and dependency composition will become format-neutral, with a new Markdown infrastructure adapter alongside ReportLab.
- CLI and expected-error handling will describe final report generation rather than PDF-only generation.
- Unit, context, packaging, and Linux integration coverage will be extended for Markdown; Linux integration configuration remains JSON-based and continues to use `git@github.com:torvalds/linux.git`.
- README, project specification, and affected OpenSpec capabilities will describe both formats.
- No new runtime dependency is required.
