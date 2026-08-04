## 1. Configuration Contract Tests

- [x] 1.1 Add runtime-configuration unit tests for a non-empty `head_ref` with an explicit `base_ref` and no marker selector.
- [x] 1.2 Add runtime-configuration unit tests for a non-empty `head_ref` with a valid `release_marker_config_path` and no explicit base ref.
- [x] 1.3 Add table-driven unit tests rejecting an absent or empty head ref and both, neither, absent, or empty lower-boundary selectors.
- [x] 1.4 Add unit tests rejecting missing, unreadable, malformed, non-object, absent-marker, and empty-marker files when marker mode is selected.
- [x] 1.5 Add unit tests proving omitted `repository_update_mode` selects `read_only` and each declared mode value is accepted.
- [x] 1.6 Add unit tests rejecting unknown update modes and mode-specific fields supplied to an incompatible mode.
- [x] 1.7 Add unit tests requiring an explicit remote and non-empty refspec list for `refresh_remote_refs`, rejecting empty values and destinations outside that remote's tracking namespace.
- [x] 1.8 Run the focused configuration tests and confirm the new contract tests fail before production code is changed.

## 2. Repository Status And Frozen Range Tests

- [x] 2.1 Add unit tests proving every inspection, resolution, marker lookup, commit-log, and commit-show command disables optional Git locks.
- [x] 2.2 Add repository-status unit tests for clean, staged, unstaged, untracked, and combined dirty checkout states.
- [x] 2.3 Add repository-status unit tests for attached and detached `HEAD`, including diagnostics that distinguish the checkout from a differently configured analysis head.
- [x] 2.4 Add repository-status unit tests classifying equal, ahead, behind, and diverged upstream relationships from left/right counts.
- [x] 2.5 Add repository-status unit tests warning without guessing when an upstream is absent, its tracking ref is missing, or comparison fails.
- [x] 2.6 Add unit tests proving read-only status reports remote freshness as unknown even when the checkout equals its local tracking ref.
- [x] 2.7 Add explicit-boundary unit tests proving head and base refs resolve to full commit SHAs exactly once after the selected update step.
- [x] 2.8 Add marker-boundary unit tests proving lookup is bounded by the frozen head SHA, accepts subject matches only, and selects the newest reachable matching subject.
- [x] 2.9 Add boundary-error unit tests for an unresolved head, unresolved base, and missing reachable marker, with no commit, diff, AI, or PDF work afterward.
- [x] 2.10 Add unit tests that move configured refs after resolution and prove commit extraction and diff generation still receive only the original `base_sha`, `head_sha`, and derived commit SHAs, never ambient `HEAD`.
- [x] 2.11 Add diff-command unit tests requiring `--no-ext-diff`, `--no-textconv`, the frozen commit SHA, and an option terminator.
- [x] 2.12 Run the focused repository-status, commit-range, and diff tests and confirm the new tests fail before production code is changed.

## 3. Read-Only Workflow Proof Tests

- [x] 3.1 Add a context-test Git-state proof snapshot that records every ref name/object ID, symbolic-or-detached `HEAD` plus its commit SHA, raw index bytes and metadata plus `write-tree`, porcelain status, and every non-Git worktree path's type, mode, symlink target, and content hash.
- [x] 3.2 Add a default-mode success context test with staged, unstaged, and untracked source changes, asserting exact equality of the before/after proof snapshots and that local changes are not used as analysis input.
- [x] 3.3 Add a default-mode success context test that analyzes an explicit head ref other than the checkout and asserts exact equality of refs, `HEAD`, index, and worktree snapshots.
- [x] 3.4 Add default-mode failure context tests at boundary resolution, commit extraction, diff generation, AI summarization, and PDF/output generation, asserting exact equality of every before/after Git-state proof snapshot.
- [x] 3.5 Add workflow context tests proving dirty, detached, ahead, behind, diverged, uncomparable, and unknown-freshness conditions emit warnings but do not block SHA-based read-only analysis.
- [x] 3.6 Add workflow context tests proving all runtime, referenced-JSON, and analysis-path validation completes before any repository update command or output creation.
- [x] 3.7 Run the focused read-only workflow context tests and confirm the new tests fail before production code is changed.

## 4. Explicit Update Mode Tests

- [x] 4.1 Add tests proving default `read_only` mode invokes no fetch, rebase, checkout, switch, reset, merge, or pull and reports unknown remote freshness.
- [x] 4.2 Add explicit-refresh tests proving only the configured remote/refspecs are fetched with no tags and no `FETCH_HEAD` write, before either boundary is resolved.
- [x] 4.3 Add refresh diagnostics tests proving only successfully named destinations are reported fresh as of that fetch and all other relevant refs remain unknown.
- [x] 4.4 Add refresh context tests whose proof snapshots allow changes only to configured remote-tracking refs and Git objects while requiring `HEAD`, index, local branch refs, and every worktree path to remain unchanged.
- [x] 4.5 Add refresh-failure tests proving a nonzero fetch stops boundary resolution, commit extraction, diff generation, AI summarization, and PDF generation without falling back to stale refs.
- [x] 4.6 Add legacy-guard tests for staged, unstaged, and untracked changes, detached `HEAD`, absent upstream, and unresolvable upstream, proving no fetch, rebase, or downstream work occurs.
- [x] 4.7 Assert exact before/after Git-state proof snapshots for every rejected legacy guard case.
- [x] 4.8 Add legacy-success tests proving clean attached upstream validation precedes `fetch --prune`, upstream rebase, and then one-time boundary resolution.
- [x] 4.9 Add legacy-fetch-failure tests proving rebase and all downstream work are skipped.
- [x] 4.10 Add legacy-rebase-failure tests proving the original error is preserved, abort is attempted, abort failure is reported separately, and downstream work is skipped.
- [x] 4.11 Run the focused update-mode unit and context tests and confirm the new tests fail before production code is changed.

## 5. Path Containment Tests

- [x] 5.1 Add path-validation tests accepting canonical temporary and final-output paths outside the source worktree.
- [x] 5.2 Add tests rejecting a temporary path equal to or lexically below the source root in every update mode before diff, AI, or PDF work.
- [x] 5.3 Add tests rejecting read-only and refresh output paths equal to or lexically below the source root before creating or replacing output.
- [x] 5.4 Add tests rejecting relative traversal and existing symlink aliases that resolve a temporary or protected output path inside the source worktree.
- [x] 5.5 Add tests for nonexistent path suffixes beneath symlinked existing ancestors and for containment revalidation after an external temporary directory is created.
- [x] 5.6 Add tests proving an unusable external temporary path reports an error and never falls back to the source worktree.
- [x] 5.7 Run the focused path-containment tests and confirm the new tests fail before production code is changed.

## 6. Configuration Implementation

- [x] 6.1 Add immutable runtime selector and repository-update mode values for explicit head, exactly one lower boundary, and the three declared modes.
- [x] 6.2 Parse and validate selector exclusivity, non-empty values, update-mode compatibility, and refresh remote/refspec shape in `load_runtime_config`.
- [x] 6.3 Load and validate the release-marker JSON only when marker mode is selected, while preserving configuration-path injection at the runtime entry point.
- [x] 6.4 Ensure selector, mode, referenced-JSON, and path-shape errors are raised before any Git command or output write.
- [x] 6.5 Run the configuration unit tests and make the complete configuration contract pass.

## 7. Repository Inspection And Range Implementation

- [x] 7.1 Introduce one read-only Git command path that sets `GIT_OPTIONAL_LOCKS=0` for status, ref inspection, resolution, logs, and shows without affecting mutating mode commands.
- [x] 7.2 Implement one reusable porcelain-v2 preflight result for dirty state, attached/detached checkout, upstream availability, and left/right relationship counts.
- [x] 7.3 Implement explicit warnings for dirty, detached, ahead, behind, diverged, uncomparable, and unknown-freshness states without blocking read-only analysis.
- [x] 7.4 Add an immutable release-range value containing only `base_sha` and `head_sha`.
- [x] 7.5 Resolve explicit head and base refs once to full commit SHAs with safe option termination and clear unresolved-boundary errors.
- [x] 7.6 Resolve marker mode from only the frozen head history, verify marker text against subjects, and freeze the newest reachable match.
- [x] 7.7 Extract commits oldest-first from `<base_sha>..<head_sha>` and remove every downstream use of ambient `HEAD` or configured refs.
- [x] 7.8 Generate commit diffs from frozen commit SHAs with external diff and text conversion disabled.
- [x] 7.9 Run the repository-status, frozen-range, commit, and diff unit tests and make them pass.

## 8. Repository Update Mode Implementation

- [x] 8.1 Implement `read_only` as the no-network, no-update default and report remote freshness as unknown.
- [x] 8.2 Implement `refresh_remote_refs` with the exact configured remote/refspecs, remote-tracking-only destinations, no tags, and suppressed `FETCH_HEAD` updates.
- [x] 8.3 Report successful refresh scope and stop immediately on refresh failure before resolving either range boundary.
- [x] 8.4 Guard `legacy_in_place_sync` with the shared preflight's attached, clean, and resolvable-upstream conditions before any mutation.
- [x] 8.5 Preserve guarded legacy fetch/rebase ordering, fetch short-circuiting, rebase abort, and separate original/abort error reporting.
- [x] 8.6 Resolve range boundaries only after a requested refresh or legacy synchronization succeeds.
- [x] 8.7 Run the explicit update-mode unit and context tests and make them pass.

## 9. Workflow And Path Safety Implementation

- [x] 9.1 Resolve the repository's canonical worktree root without optional locks and implement symlink-aware containment checks from canonical existing ancestors.
- [x] 9.2 Reject internal temporary paths in every mode and internal final-output paths in read-only and refresh modes before creating analysis artifacts.
- [x] 9.3 Revalidate containment after creating external directories and propagate path errors without any source-worktree fallback.
- [x] 9.4 Reorder the workflow to validate configuration and paths, run one preflight, execute the selected update mode, and then freeze the release range.
- [x] 9.5 Pass the immutable range and its derived commit SHAs through extraction, filtering, diff generation, report context, and range diagnostics without re-resolving refs.
- [x] 9.6 Keep temporary diffs and atomic output siblings at their validated external destinations and preserve downstream short-circuit behavior on every failure.
- [x] 9.7 Update declared workflow steps and user-facing warnings to describe preflight, selected update mode, frozen boundaries, and SHA-based extraction accurately.
- [x] 9.8 Run all path-safety and workflow context tests and make every proof-snapshot assertion pass.

## 10. JSON-Driven Linux Integration

- [x] 10.1 Add Linux-fixture integration setup/teardown proof snapshots that fail a test if the external fixture's refs, `HEAD`, index, status, or worktree inventory differs afterward.
- [x] 10.2 Update marker and large-range integration tests to obtain repository path, head selector, and marker selector from JSON and resolve the configured frozen range rather than ambient `HEAD`.
- [x] 10.3 Update the full default workflow integration test to analyze the external Linux fixture directly while placing copied runtime JSON, diffs, and PDF output under the test temporary directory.
- [x] 10.4 Add a forced downstream-failure Linux workflow test proving the direct external fixture's complete before/after snapshot is unchanged and no artifact is written into it.
- [x] 10.5 Add Linux-derived temporary-clone integration coverage for explicit remote refresh, asserting only the named tracking destination may change and the external fixture remains unchanged.
- [x] 10.6 Retain guarded legacy fetch/rebase integration coverage only in a temporary shared-object sparse clone, never in the external fixture.
- [x] 10.7 Keep every integration invocation JSON-driven by writing a runtime JSON path and passing that path through the public workflow entry point.

## 11. Documentation And Configuration Migration

- [x] 11.1 Migrate `config/workflowLinuxIT.json` to an explicit reproducible Linux head ref, marker lower-boundary selector, external analysis paths, and the omitted read-only default.
- [x] 11.2 Update any remaining committed runtime JSON to declare `head_ref`, exactly one lower-boundary selector, safe external paths, and an intentional update mode.
- [x] 11.3 Update `README.md` configuration examples and workflow documentation for frozen SHAs, read-only default behavior, diagnostics, explicit refresh, guarded legacy synchronization, and path restrictions.
- [x] 11.4 Add direct migration guidance for existing implicit-`HEAD` marker configurations and explain that local tracking equality does not prove remote freshness.
- [x] 11.5 Update the Linux integration protocol to document direct read-only fixture analysis, exact state snapshots, temporary-clone-only mutation tests, and JSON-defined boundaries.
- [x] 11.6 Run the JSON configuration and Linux integration tests after migration and make them pass without changing the external fixture snapshot.

## 12. Full Verification

- [x] 12.1 Run the complete unit suite and resolve every regression.
- [x] 12.2 Run the complete context suite and verify all success/failure Git-state proof snapshots remain exact.
- [x] 12.3 Run the complete non-live integration suite against `git@github.com:torvalds/linux.git` and verify the managed fixture is unchanged.
- [x] 12.4 Verify tests and runtime leave no generated diffs, PDFs, lock files, `FETCH_HEAD` updates, or other artifacts in any analyzed source worktree.
- [x] 12.5 Run strict OpenSpec validation for `make-git-analysis-read-only` and resolve every validation error.
