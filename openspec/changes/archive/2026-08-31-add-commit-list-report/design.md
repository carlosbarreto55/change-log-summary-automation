## Context

The current layered workflow loads AI and temporary-diff configuration for every run, extracts full commit metadata from a frozen Git range, filters by exact author email and subject prefix, groups accepted hashes by module, generates module diffs, summarizes them, composes a structured release document, and atomically renders it with ReportLab. `ClassifiedCommit` already retains the exact subject, full object ID, module, author timestamp, and author email needed for a deterministic report before `git show` or any AI operation occurs.

The new mode must retain the existing range, filtering, module ordering, repository safety, report context, and PDF guarantees while proving that qualifying commits do not cause an AI client, credential lookup, diff file, or `git show` call. Existing runtime JSON must remain valid and continue selecting the AI workflow.

## Goals / Non-Goals

**Goals:**

- Generate a module-organized PDF containing exact commit subjects and full object IDs with no LLM dependency.
- Keep report selection explicit and backward compatible.
- Preserve repository, count, UTC date, ISO-week, section, and module context.
- Keep mode-specific configuration and side effects out of the path that does not need them.
- Represent summary content and commit-list content explicitly in the release-document domain.

**Non-Goals:**

- Grouping commits by author or displaying author emails.
- Stripping module prefixes, abbreviating object IDs, adding repository hyperlinks, or including commit bodies or diffs.
- Replacing or changing either existing AI backend.
- Making `commit_list` fully offline when an explicit Git remote-ref refresh or legacy synchronization mode is selected.
- Adding pagination controls, truncation limits, or a configurable report title.

## Decisions

### 1. Report mode is an explicit runtime discriminator with an AI-compatible default

Add `ReportMode` values `ai_summary` and `commit_list` to the validated workflow configuration. The runtime loader reads `report_mode` before any mode-specific path. A missing field maps to `ai_summary`; an unknown or unusable value fails configuration before path validation or Git activity.

For `ai_summary`, the current `ai_config_path`, `temp_diff_dir`, and optional `env_file_path` loading and validation remain unchanged. For `commit_list`, those raw fields may be absent or present, but the loader does not resolve, validate, read, or retain them. The validated configuration carries no AI settings or temporary-diff destination for that mode. AI and temporary-path fields become optional in the shared immutable configuration and analysis-path types, with mode-specific loader invariants and explicit workflow branching guarding their use.

This is preferred over inferring the mode from a missing AI path because malformed AI configuration must not silently change report behavior. Allowing ignored fields is preferred over rejecting them because an operator can safely switch an existing JSON workflow by changing one discriminator.

### 2. The workflow branches immediately after common commit selection

Repository inspection/update, range freezing, commit extraction, exact-email filtering, and prefix classification remain common. After selection:

- `ai_summary` keeps the existing grouping, destination preparation, diff generation, summarization, summary composition, export, and `finally` cleanup path.
- `commit_list` prepares only the PDF parent, composes directly from accepted classified commits, revalidates the output destination, and exports it.

The commit-list branch never calls the diff grouping collaborator because that representation drops subjects, never calls `git show`, and never enters the diff cleanup block. Production dependency composition may still construct stateless service objects, but no AI factory `create` operation, client process, endpoint request, environment-key resolution, or diff artifact operation is reachable.

This branch is preferred over implementing a fake summarizer that returns hash bullets because deterministic Git data must not masquerade as AI prose or pass through AI-oriented limits and artifacts.

### 3. Release documents use explicit module-content variants

Keep the common `ReleaseDocument` and `ReleaseSection` metadata. Add immutable `ReleaseCommitEntry(subject, commit_hash)` and `ReleaseModuleCommitList` values alongside the existing `ReleaseModuleSummary`; a section's modules may contain either explicit variant. The commit-list composer walks configured modules in JSON order, selects their accepted commits without regrouping by author, preserves the oldest-first extraction order, computes existing UTC module dates, and omits empty modules and sections.

This is preferred over stuffing formatted hashes into `ReleaseModuleSummary.summary` because it preserves type meaning and gives the renderer an exhaustive content decision without introducing a general extension framework.

### 4. Commit-list presentation reuses the existing PDF frame

The document title is `Release Commit Report`. Repository name, total qualifying-change count, UTC date range, ISO weeks, section headings, module headings, module count, module date range, empty-message behavior, embedded fonts, and atomic replacement remain unchanged.

Each accepted commit is one bullet rendered as `<exact subject> — <full object ID>`. The subject retains the trusted classification prefix and is HTML-escaped. The complete object ID is never assumed to be 40 characters and uses an embedded monospaced Vera face. ReportLab may wrap a long entry across lines and paginate naturally; entries are not truncated. No author heading or author text appears.

### 5. Tests enforce absence as well as output

Unit tests cover the discriminated loader, document variants, exact ordering, and ReportLab story. Workflow tests inject fail-fast diff and summarization collaborators to prove they are unreachable. Context coverage runs a real temporary Git workflow with no AI file or diff path. Required Linux integration uses committed JSON and the public fixture to exercise large-history extraction, filtering, commit-list composition, PDF export, and repository immutability. Packaging coverage proves the installed CLI can run the mode without an AI backend.

## Risks / Trade-offs

- [Ignored AI fields can become stale without diagnostics] → Document that they are out of scope in `commit_list` and test that even malformed referenced resources are not consumed.
- [Optional mode-specific values permit invalid manually constructed domain objects] → Centralize production construction in the validated loader and fail explicitly if an AI branch receives absent AI settings or a diff path.
- [Full object IDs and long subjects wrap] → Use individual Platypus paragraph flowables, an embedded monospaced hash font, escaping, and natural pagination.
- [Broad filters can produce a large PDF] → Preserve every qualifying commit as requested and accept output size proportional to the filtered set; do not add an unrequested truncation policy.
- [Static workflow descriptions can incorrectly imply AI work] → Replace AI-specific declared steps with branch-neutral configured-content language while retaining execution-order tests for each mode.

## Migration Plan

1. Add the report discriminator with `ai_summary` as the missing-field default and run the existing suite as the compatibility baseline.
2. Add mode-specific configuration/path handling and the explicit commit-list document content.
3. Add the workflow branch and PDF rendering behind `report_mode: "commit_list"`.
4. Add JSON examples, documentation, Linux integration configuration, and installed-package coverage.
5. Roll back operationally by removing `report_mode` or selecting `ai_summary`; no repository or PDF data migration is required.

## Open Questions

None. Report hierarchy, entry content, hash length, subject preservation, title, metadata, mode selection, and ignored-field behavior are resolved.
