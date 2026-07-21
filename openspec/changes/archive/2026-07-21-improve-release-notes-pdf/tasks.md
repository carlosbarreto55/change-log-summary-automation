## 1. Preserve Commit Dates

- [x] 1.1 Add commit unit tests for strict ISO author-timestamp extraction, offset-aware parsing, malformed timestamp errors, and date preservation through filtering.
- [x] 1.2 Extend `GitCommit`, `ClassifiedCommit`, Git log parsing, and filtering to retain timezone-aware author timestamps and satisfy the new unit tests.

## 2. Compose Report Context

- [x] 2.1 Add composition unit tests for repository identity, total and per-module qualifying-change counts, UTC-normalized single and multi-date ranges, ISO year-week ranges, and the zero-change document.
- [x] 2.2 Extend the release document and module summary models and composition function to derive the tested metadata from the configured repository name and accepted commits.

## 3. Integrate Context Into the Workflow

- [x] 3.1 Add context-level coverage proving filtered dated commits flow into the correct configured sections and module metadata without assigning dates to AI summary bullets.
- [x] 3.2 Update workflow orchestration to pass the configured repository path's final component and accepted commits into document composition.

## 4. Render Descriptive PDF Metadata

- [x] 4.1 Add PDF story tests for the repository and count rows, exact UTC date and ISO week rows, per-module singular and plural metadata, escaped text, and empty-report omission of unavailable ranges.
- [x] 4.2 Add compact ReportLab metadata styles and render the tested first-page and per-module context while preserving summary, Unicode, and atomic export behavior.

## 5. Verify Cross-Boundary Behavior

- [x] 5.1 Update the JSON-driven public Linux repository integration test to assert the derived repository name, qualifying count, global date range, ISO week range, and per-module ranges in the generated document.
- [x] 5.2 Update user-facing documentation to describe the repository, qualifying-change, UTC date-range, and ISO-week fields shown in generated PDFs.
- [x] 5.3 Run the complete unit and context test suites and resolve every failure.
- [x] 5.4 Run the non-live Linux integration suite against `git@github.com:torvalds/linux.git` and verify PDF generation and temporary-diff cleanup still pass.
