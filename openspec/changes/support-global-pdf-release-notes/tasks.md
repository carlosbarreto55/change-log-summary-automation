## 1. Establish the Implementation Baseline

- [x] 1.1 Incorporate the end-to-end workflow from `feat/end-to-end-cli-workflow` into this task branch and confirm the existing non-live test suite passes before feature work.
- [x] 1.2 Replace Redis-specific integration fixture names and protocol documentation with a Linux-kernel fixture plan that uses JSON configuration and never mutates the externally managed fixture directly.

## 2. Extend and Validate JSON Configuration

- [x] 2.1 Add unit tests for required module `section` values, preserved module order, and rejection of missing, empty, or unusable section data.
- [x] 2.2 Add unit tests for required positive `max_diff_characters_per_request` AI configuration and rejection of missing, boolean, non-integer, or non-positive values.
- [x] 2.3 Add unit tests that runtime output paths must end in `.pdf` and that relative, absolute, and home-relative paths resolve correctly.
- [x] 2.4 Implement the ordered module definitions, section loading, AI request limit, and PDF output-path validation needed to pass the configuration tests.
- [x] 2.5 Update default and integration JSON files with module sections, AI request limits, and PDF output paths.
- [x] 2.6 Add a context test proving all referenced JSON structures are validated before repository fetch or rebase, then reorder workflow configuration loading to satisfy it.

## 3. Make Git Synchronization Recoverable

- [x] 3.1 Add unit tests that fetch runs before rebase, fetch failure prevents rebase, and the original fetch error is preserved.
- [x] 3.2 Add unit tests that rebase failure triggers `git rebase --abort` and reports the original rebase error plus the abort outcome.
- [x] 3.3 Implement stage-aware Git synchronization errors and failed-rebase abort handling without hiding Git standard error.
- [x] 3.4 Add CLI unit tests for concise standard-error output, nonzero status, and absence of an expected-error traceback.
- [x] 3.5 Implement CLI handling for expected configuration, Git, diff, AI, and PDF workflow errors.
- [x] 3.6 Add context tests proving fetch, rebase, marker lookup, extraction, and downstream work remain ordered and that no diff, AI, or PDF work runs after synchronization failure.

## 4. Generalize Filtering and Release Sections

- [x] 4.1 Add unit tests that exact approved emails and case-sensitive first-match prefixes remain the only commit-selection rules after the module configuration change.
- [x] 4.2 Add unit tests for section order by first JSON appearance, module order within sections, omission of empty modules and sections, and the no-qualifying-changes document.
- [x] 4.3 Implement the minimal ordered release-document model and config-driven composition without hard-coded product names.
- [x] 4.4 Add context tests that configured modules sharing a section retain separate summaries in configured order and that unauthorized or unmapped commits never appear in the document input.

## 5. Bound AI Summarization

- [x] 5.1 Add unit tests for one in-limit diff request, commit-boundary chunking, line-boundary splitting of one oversized commit, exact content preservation, and strict request-size bounds.
- [x] 5.2 Implement ordered module-specific diff chunking using `max_diff_characters_per_request`.
- [x] 5.3 Add unit tests for ordered hierarchical reduction, bounded reduction requests, and prevention of cross-module content mixing.
- [x] 5.4 Implement sequential chunk summarization and bounded hierarchical reduction to one summary per included module.
- [x] 5.5 Add context tests covering multiple chunks per module through final structured-document composition with a recording AI client.

## 6. Generate PDF Release Notes

- [x] 6.1 Add ReportLab as the single runtime PDF dependency using a project-compatible version range and install the updated project environment.
- [x] 6.2 Add unit tests for mapping titles, sections, module headings, bullet lines, paragraphs, escaped renderer characters, and supported non-ASCII text into PDF flowables.
- [x] 6.3 Add unit tests for parent-directory creation, successful atomic replacement, temporary-file cleanup, preservation of an existing destination after render failure, and PDF signature output.
- [x] 6.4 Implement the ReportLab Platypus renderer with the bundled Vera TrueType font family and direct support for the defined release-document structure.
- [x] 6.5 Implement temporary sibling-file rendering and atomic replacement of the configured PDF destination.
- [x] 6.6 Replace Markdown export in the workflow with structured composition and PDF export, while retaining temporary diff cleanup after successful generation.

## 7. Verify the Full Workflow with Linux

- [x] 7.1 Create JSON-only Linux integration configurations for approved emails, reliable high-volume prefixes and sections, release marker, bounded AI settings, temporary paths, and PDF output.
- [x] 7.2 Add integration tests using a temporary local clone derived from the separately managed public Linux fixture to exercise fetch, rebase, configured marker selection, exact-email filtering, prefix classification, and separated diff generation.
- [x] 7.3 Add an integration test with a recording AI client that runs the full configured workflow, verifies bounded category calls and dynamic sections, generates one PDF, and cleans temporary diffs.
- [x] 7.4 Remove obsolete Redis integration tests and fixture JSON after equivalent Linux coverage passes.
- [x] 7.5 Keep live AI integration opt-in and update it to use bounded Linux category input without recording authorization secrets.

## 8. Documentation and Final Verification

- [x] 8.1 Update README configuration, synchronization, graceful-error, chunking, PDF output, security, installation, and Linux testing documentation.
- [x] 8.2 Update project specification and implementation plan to describe the new JSON fields, mandatory rebase behavior, dynamic sections, bounded AI flow, and PDF-only final output.
- [x] 8.3 Run the complete unit suite, then context suite, then non-live integration suite, and resolve every failure before marking implementation complete.
- [x] 8.4 Run `openspec validate support-global-pdf-release-notes --type change --strict` and confirm the implemented behavior satisfies every capability scenario.
