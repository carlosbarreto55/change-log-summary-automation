## 1. Baseline and Test Fixtures

- [x] 1.1 Run the existing non-live unit, context, integration, and packaging suites from the task branch and record any environment-based skips before changing runtime behavior
- [x] 1.2 Extend JSON workflow test helpers to emit either the default AI-summary shape or a `commit_list` shape with no AI, environment, or temporary-diff fields

## 2. Report-Mode Configuration and Paths

- [x] 2.1 Add unit tests for the `ReportMode` values, missing-field `ai_summary` default, explicit `commit_list`, invalid values, unchanged AI validation, and commit-list configurations that omit or contain unusable ignored AI/diff fields
- [x] 2.2 Implement report-mode loading and mode-specific immutable workflow values, ensuring commit-list loading does not resolve, read, validate, or retain AI, environment, or temporary-diff resources; run the configuration unit tests successfully
- [x] 2.3 Add path-safety unit tests proving AI-summary temporary paths retain their current containment rules while commit-list mode validates, prepares, and revalidates only the PDF destination
- [x] 2.4 Make analysis temporary paths mode-dependent without weakening output containment or identity checks; run the path-safety unit tests successfully

## 3. Commit-List Document and PDF

- [x] 3.1 Add domain and release-document service tests for immutable commit entries, configured section/module order, oldest-first within-module order, no author grouping, exact subjects, full object IDs, UTC context, omitted empty modules, and the empty commit-list document
- [x] 3.2 Implement explicit commit-entry and commit-list module document variants plus commit-list composition titled `Release Commit Report`; run the domain and service tests successfully
- [x] 3.3 Add ReportLab story tests for exact subject/em-dash/full-ID bullets, preserved module prefixes, HTML escaping, supported non-ASCII text, long SHA-256-style IDs, monospaced hash styling, natural wrapping, shared metadata, and existing AI-summary rendering
- [x] 3.4 Extend the PDF exporter to render both explicit module-content variants with bundled fonts while preserving atomic replacement; run the PDF unit tests successfully

## 4. Mode-Specific Workflow Orchestration

- [x] 4.1 Add release-workflow tests proving commit-list runs branch after selection, prepare only output, compose/export successfully, and never call diff grouping, diff generation, cleanup, AI factory creation, summarization, or reduction; retain failure/cleanup tests for AI-summary mode
- [x] 4.2 Implement the commit-list workflow branch, explicit AI-mode guards, and branch-neutral declared workflow steps; run workflow, architecture, and CLI unit/context tests successfully

## 5. End-to-End and External Repository Coverage

- [x] 5.1 Add a context test using a real temporary Git repository and runtime JSON with no AI file or diff path; verify exact title/hash content reaches document export, a valid PDF is written, and no temporary analysis directory is created
- [x] 5.2 Add a committed `commit_list` integration JSON for `git@github.com:torvalds/linux.git` and an integration test covering the frozen range, exact contributor/module filtering, configured module order and counts, oldest-first subject/full-ID entries, valid PDF output, no diff artifacts, and unchanged Linux repository state
- [x] 5.3 Extend wheel installation smoke coverage to run the installed CLI in `commit_list` mode without an AI configuration, API key, Claude executable, or temporary-diff path

## 6. Documentation and Verification

- [x] 6.1 Update README usage, runtime JSON reference, PDF description, security guidance, package description, and committed example configuration to distinguish `ai_summary` from the non-LLM `commit_list` workflow and explain that explicit Git update modes may still use the network
- [x] 6.2 Run the complete non-live unit, context, Linux integration, and packaging suites; confirm no new code remains untested and all generated temporary artifacts are cleaned
- [x] 6.3 Run strict OpenSpec validation, inspect the final task-branch diff for accidental source/diff/credential artifacts, and prepare a Conventional Commit message with a `Changes:` section only after every required test passes
