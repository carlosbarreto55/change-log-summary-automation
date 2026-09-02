## 1. Configuration and Format Selection

- [ ] 1.1 Add unit tests proving relative, absolute, home-relative, lowercase, and uppercase `.md` output paths load successfully while unsupported suffixes fail before path validation or Git activity
- [ ] 1.2 Update runtime configuration validation to accept only `.pdf` and `.md` suffixes case-insensitively without adding a redundant format field; run the configuration unit tests
- [ ] 1.3 Add unit tests for suffix-based exporter routing, including defensive rejection of an unsupported suffix and unchanged `.pdf` selection

## 2. Markdown Serialization and Atomic Export

- [ ] 2.1 Add Markdown serializer unit tests for complete AI-summary content, report and module metadata, configured ordering, paragraph and bullet handling, UTF-8 text, normalized newlines, and one trailing newline
- [ ] 2.2 Add Markdown serializer unit tests for deterministic commit-list entries with exact escaped subjects, em dashes, complete SHA-1 and longer object IDs in inline code, and no author/body/diff content
- [ ] 2.3 Add Markdown serializer unit tests for present and absent Task References, deterministic module/reference grouping, occurrence counts, and the descriptive empty report
- [ ] 2.4 Add focused escaping tests covering headings, list markers, emphasis, links, images, code spans, backslashes, and raw HTML delimiters in every dynamic field type
- [ ] 2.5 Implement the dependency-free UTF-8 Markdown serializer and exporter over `ReleaseDocument`; run its serializer tests
- [ ] 2.6 Add exporter tests proving parent creation, temporary-sibling cleanup, non-empty validation, atomic replacement, existing-destination preservation on pre-replacement failure, and Markdown-specific error reporting
- [ ] 2.7 Implement and verify atomic Markdown export without changing ReportLab PDF rendering behavior

## 3. Format-Neutral Application Wiring

- [ ] 3.1 Add service and presentation tests for a format-neutral document-exporter port, suffix-selecting exporter composition, and identical workflow ordering for `.pdf` and `.md`
- [ ] 3.2 Generalize the exporter protocol, `ReleaseNotesService` collaborator naming, workflow step text, and presentation composition, then wire the PDF and Markdown exporters through one selector
- [ ] 3.3 Add a report-generation base error and Markdown-specific error while preserving `PDFGenerationError`; update CLI tests for concise Markdown failures without tracebacks
- [ ] 3.4 Update CLI descriptions, package metadata, architecture assertions, and affected existing unit tests to use output-format-neutral terminology; run the complete unit suite

## 4. Context and Filesystem Workflow Coverage

- [ ] 4.1 Add an `ai_summary` context test using JSON configuration and an `.md` destination; verify all PDF-equivalent information, Task References, external-path containment, atomic output, and temporary-diff cleanup
- [ ] 4.2 Add a `commit_list` context test using JSON configuration and an `.md` destination; verify exact ordered commits and full IDs with no diff or AI work
- [ ] 4.3 Add context failure coverage proving Markdown export errors preserve an existing destination, clean temporary artifacts, return the expected error, and do not mutate the analyzed repository
- [ ] 4.4 Run the complete context suite and resolve every regression before continuing

## 5. Linux and Packaging Integration

- [ ] 5.1 Add a committed JSON runtime configuration for Markdown integration against `git@github.com:torvalds/linux.git`, keeping output external to the fixture and avoiding AI requirements by using deterministic `commit_list` mode
- [ ] 5.2 Add a non-live Linux integration test that generates Markdown from the frozen fixture range and verifies repository context, counts, UTC/ISO-week context, ordered modules, exact commit traceability, Task References when present, and unchanged fixture state
- [ ] 5.3 Extend installed-wheel integration coverage to invoke the packaged CLI with an `.md` JSON configuration and verify the Markdown adapter is included and selected
- [ ] 5.4 Run the complete non-live Linux integration suite with live AI tests disabled and resolve every regression

## 6. Documentation and Specification Alignment

- [ ] 6.1 Update README examples, feature tables, configuration rules, output guarantees, error behavior, testing guidance, and security notes for selectable PDF or Markdown output
- [ ] 6.2 Update `SPEC.md` and `PLAN.md` to remove PDF-only and no-Markdown constraints while retaining all release-selection, bounded-AI, path-safety, and atomic-output requirements
- [ ] 6.3 Inspect active task-reference documentation and ensure Markdown parity is described without weakening its extraction, aggregation, ordering, or PDF behavior

## 7. Final Verification

- [ ] 7.1 Run the complete unit suite and record a successful result
- [ ] 7.2 Run the complete context suite and record a successful result
- [ ] 7.3 Run the complete non-live integration suite with live AI and Claude Code tests disabled and record a successful result
- [ ] 7.4 Run `openspec validate add-markdown-output --type change --strict` and resolve every validation error
- [ ] 7.5 Review the final diff for unintended source artifacts, generated reports, temporary files, credentials, and unrelated changes before any commit
- [ ] 7.6 Commit only after all required tests pass, using a Conventional Commit message with a `Changes:` section as required by `AGENTS.md`
