# Implementation Plan

This plan tracks the test-driven implementation of configuration-driven PDF release notes for large brownfield repositories.

## Working Rules

- [x] Runtime code receives a JSON configuration path.
- [x] Behavior changes are covered by unit tests before implementation.
- [x] Cross-module, filesystem, Git, and workflow behavior has context or integration coverage.
- [x] Unit, context, and integration suites remain separate.
- [x] External integration configuration is defined in JSON.
- [x] Integration tests use Linux and never mutate the separately managed fixture.

## 1. Baseline and Configuration

- [x] Incorporate the end-to-end CLI workflow from `feat/end-to-end-cli-workflow`.
- [x] Preserve exact author-email allowlisting.
- [x] Add ordered module definitions with required `section` values.
- [x] Add required positive `max_diff_characters_per_request` AI configuration.
- [x] Load the release marker from referenced JSON.
- [x] Require the runtime output path to end in `.pdf`.
- [x] Resolve relative, absolute, and home-relative runtime paths.
- [x] Validate all referenced JSON before repository synchronization.

## 2. Recoverable Repository Synchronization

- [x] Run `git fetch --prune` before `git rebase @{u}`.
- [x] Stop rebase when fetch fails.
- [x] Attempt `git rebase --abort` when rebase fails.
- [x] Preserve Git's original error and report abort outcome.
- [x] Stop extraction, diff, AI, and PDF work after synchronization failure.
- [x] Return concise expected-error CLI output and nonzero status without a traceback.
- [x] Limit marker lookup to Git fixed-string candidates for large histories.
- [x] Decode legacy Git output with replacement characters instead of crashing.

## 3. Dynamic Commit Classification and Composition

- [x] Keep exact case-sensitive email filtering.
- [x] Use case-sensitive first-match subject prefixes from JSON.
- [x] Discard unauthorized and unmapped commits before diff generation.
- [x] Preserve module order from JSON.
- [x] Derive section order from each section's first JSON appearance.
- [x] Keep modules sharing a section separate and ordered.
- [x] Omit empty modules and sections.
- [x] Compose a clear no-qualifying-changes document when nothing is accepted.

## 4. Bounded AI Summarization

- [x] Split each module diff within the configured character bound.
- [x] Prefer commit boundaries and then line boundaries.
- [x] Preserve diff content exactly.
- [x] Keep every request module-specific.
- [x] Summarize chunks sequentially.
- [x] Reduce partial summaries hierarchically through bounded requests.
- [x] Produce exactly one final summary per included module.

## 5. Atomic PDF Output

- [x] Add ReportLab as the single PDF runtime dependency.
- [x] Compose a renderer-independent structured release document.
- [x] Render title, sections, modules, bullets, paragraphs, and escaped text.
- [x] Embed the bundled Vera TrueType font family for supported UTF-8 text.
- [x] Create destination parent directories.
- [x] Render to a temporary sibling and atomically replace the destination.
- [x] Preserve an existing PDF and remove temporary output after render failure.
- [x] Replace final Markdown output with one local PDF.
- [x] Delete temporary diff files after successful generation.

## 6. Linux Brownfield Integration

- [x] Replace previous external fixture plans with `git@github.com:torvalds/linux.git`.
- [x] Clone and inspect the official Linux Git history.
- [x] Select marker `Linux 7.1`, yielding a 15,875-commit window when verified.
- [x] Configure five verified raw author emails.
- [x] Configure high-volume `wifi:`, `KVM:`, `ksmbd:`, `ASoC:`, and `net:` prefixes.
- [x] Verify 368 accepted commits in the researched fixture state.
- [x] Create temporary shared-object sparse worktrees for fetch/rebase coverage.
- [x] Exercise real extraction, filtering, grouping, and separated diff generation.
- [x] Exercise the full workflow with bounded recording-AI calls and dynamic sections.
- [x] Verify one PDF is generated and temporary diffs are cleaned.
- [x] Keep live AI integration opt-in and authorization data redacted.

## 7. Documentation and Verification

- [x] Update README configuration, recovery, chunking, PDF, security, and Linux setup guidance.
- [x] Update the normative project specification for the implemented behavior.
- [x] Replace the historical implementation plan with this current plan.
- [x] Run the complete unit suite.
- [x] Run the complete context suite.
- [x] Run the complete non-live Linux integration suite.
- [x] Run strict OpenSpec validation.
- [x] Confirm the worktree contains no stale references to previous integration fixtures.
