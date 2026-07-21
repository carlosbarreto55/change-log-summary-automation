## Context

The workflow extracts commits after the latest configured release marker, filters them by exact author email and configured subject prefix, summarizes per-module diffs, composes an output-independent `ReleaseDocument`, and renders it with ReportLab. The extracted and classified commit models currently discard timestamps, `ReleaseDocument` only carries a generic title and summary sections, and the PDF begins immediately with those fields.

The new context must remain deterministic and testable. AI summaries are module-level reductions and do not preserve a one-to-one mapping between output bullets and commits, so assigning a commit date to an AI-written bullet would imply precision that the workflow cannot guarantee. Runtime behavior must continue to accept a JSON configuration path and integration tests must continue to use the public Linux repository fixture.

## Goals / Non-Goals

**Goals:**

- Identify the source repository and qualifying-change scope at the beginning of every PDF.
- Show exact UTC calendar dates as the primary coverage representation and unambiguous ISO year-week labels as secondary context.
- Show an exact qualifying-change count and date range for every rendered module.
- Derive all report metadata from the configured repository path and filtered Git history without another configuration field or AI request.
- Preserve the existing PDF output, ordering, Unicode, and atomic replacement behavior.
- Test date extraction and preservation separately from composition, rendering, and end-to-end workflow behavior.

**Non-Goals:**

- Assigning dates to AI-generated bullets or changing the summarization prompt and response shape.
- Listing every commit, hash, subject, author, or timestamp in the PDF.
- Adding date-based release selection, custom date formats, locale configuration, time-zone configuration, or a report-template system.
- Resolving a canonical repository identity from hosting-provider APIs or Git remote URLs.
- Adding a repeating page header, table of contents, charts, or another output format.

## Decisions

### Carry strict Git author timestamps through filtering

`git log` will add `%aI` to the existing field-separated output. Both `GitCommit` and `ClassifiedCommit` will carry the parsed, timezone-aware author timestamp so filtering cannot accidentally detach metadata from a commit. Git's strict ISO 8601 representation is machine-readable and preserves the source offset.

Composition will normalize accepted timestamps to UTC before deriving calendar dates, range boundaries, and ISO weeks. UTC produces one deterministic result regardless of the machine running the workflow. Malformed timestamps remain Git-history errors instead of being silently omitted.

Alternatives considered:

- Committer dates were rejected because rebases can change them and they describe repository integration rather than when an author made the change.
- Formatting timestamp strings directly was rejected because offsets could make global ranges and week labels inconsistent.
- Looking up dates after filtering was rejected because it would add redundant Git subprocesses and could allow the commit data and date data to diverge.

### Model report context in the output-independent document

The composition layer will receive the configured repository display name and accepted commits in addition to summaries and module configuration. `ReleaseDocument` will carry repository name, total qualifying-change count, and optional start/end dates. Each `ReleaseModuleSummary` will carry its own qualifying-change count and start/end dates. The composition layer will calculate ranges by taking minimum and maximum normalized dates rather than relying on traversal order.

The repository display name will be `runtime_config.repository_path.name`. This is deterministic, sufficient for the current JSON configuration, and avoids introducing either a new required field or remote-URL parsing. The workflow will pass the accepted commits already used to generate diffs, ensuring metadata describes only content eligible for the report.

Alternatives considered:

- Adding a configured display name was rejected as unnecessary configuration for the current request.
- Parsing `remote.origin.url` was rejected because remotes are optional, names differ across hosting protocols, and repository synchronization already operates on a local configured path.
- Computing a marker-to-HEAD period was rejected because it could imply that filtered-out commits are represented. The header will explicitly describe the range as qualifying changes.

### Use exact dates first and ISO weeks second

The first-page report header will render a compact metadata block beneath `Release Notes`:

```text
Repository: linux
Qualifying changes: 42
Change dates (UTC): 2026-01-03 – 2026-02-02
ISO weeks: 2026-W01 – 2026-W06
```

A single-day or single-week range will render only one value. The ISO week includes its ISO year because week numbers alone become ambiguous around New Year. When no commits qualify, the count remains `0`, the date and week rows are omitted, and the existing `No qualifying changes.` message remains.

Module headings will be followed by a compact line such as `3 qualifying changes · 2026-01-08 – 2026-01-19 (UTC)` before the AI-generated summary. ISO weeks are omitted at module level to keep repeated metadata concise.

Alternatives considered:

- Week labels alone were rejected because they are less precise and ambiguous without a year.
- Per-bullet dates were rejected because a summary bullet can combine multiple commits.
- A generated-at timestamp was rejected because it does not describe the changes and makes otherwise identical PDFs vary between runs.

### Extend the existing ReportLab story and styles

The renderer will map document context to escaped `Paragraph` flowables using dedicated metadata and module-context styles, separated from the title and summaries with modest spacing. This keeps presentation inside `pdf_export.py`, preserves the current structured-document boundary, and requires no new dependency or general layout abstraction.

### Verify behavior at unit, context, and integration levels

Commit unit tests will assert `%aI` extraction, timestamp parsing, and preservation through filtering. Composition unit and context tests will assert global and per-module counts/ranges, including cross-offset timestamps and empty reports. PDF tests will inspect story text for the header and module metadata. The Linux integration workflow will assert repository identity, nonzero counts, and known date boundaries derived from its JSON-configured release window while continuing to verify the actual PDF and diff cleanup.

## Risks / Trade-offs

- [A local clone can have an arbitrary directory name] → Label the field `Repository` and document that it is derived from the configured path; add an explicit configured display name only if a real use case requires it.
- [Author timestamps can contain different offsets] → Parse timezone-aware timestamps and normalize to UTC before calculating dates or weeks.
- [Large date ranges can make unrelated changes look continuous] → Pair every range with the exact qualifying-change count and use the label `Change dates` rather than claiming uninterrupted activity.
- [More header content reduces first-page space] → Use a compact metadata style and avoid commit tables or per-change details.
- [Existing callers construct commit and document dataclasses positionally] → Update repository call sites and tests in one change; this project does not publish a compatibility contract for those internal models.

## Migration Plan

1. Extend commit extraction and filtering models with parsed author timestamps.
2. Extend composition inputs and output models with deterministic report and module context.
3. Render the new first-page and per-module metadata with focused styles.
4. Update unit and context tests, then run the non-live suite.
5. Update the JSON-driven Linux integration assertions and run them when the external fixture is available.

Rollback consists of reverting this change. No user configuration, stored data, or output-path migration is required.

## Open Questions

None. Exact UTC dates are primary, ISO year-week labels are secondary, module summaries use ranges rather than per-bullet dates, and repository identity comes from the configured path.
