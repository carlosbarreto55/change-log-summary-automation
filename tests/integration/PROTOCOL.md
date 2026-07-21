# Integration Test Protocol

This file records the integration-test fixture and safety rules for the project.

## Purpose

Integration tests verify that the application can process a large brownfield Git history while keeping release-note inputs restricted to configured author emails and subject prefixes.

## External Fixture

Use the public Linux kernel repository:

`git@github.com:torvalds/linux.git`

Keep a separately managed clone at:

`/Users/carloseduardo/Downloads/Project/linux`

The integration suite never creates, fetches, rebases, resets, or otherwise mutates this external fixture. If the fixture is missing or is not a Git repository, Linux integration tests skip with a clear setup message.

The fixture is intentionally large. GitHub's Linux history contains more than 1.4 million commits, and a nominally shallow clone can still retain the full graph because of its dense merge ancestry. Setup is a separate manual operation:

```sh
git clone git@github.com:torvalds/linux.git /Users/carloseduardo/Downloads/Project/linux
```

On case-insensitive filesystems, checkout can report Linux paths that differ only by case. Tests avoid relying on the fixture worktree and read its Git object database instead.

## Temporary Worktree Safety

Tests that exercise fetch and rebase create a temporary clone derived from the external fixture with `git clone --shared --no-checkout`. They enable a sparse checkout of `Documentation`, populate it with `git read-tree -mu HEAD`, and perform synchronization only in that temporary clone.

The temporary clone has its own branch, index, worktree, and local origin. Shared immutable objects keep setup fast without modifying the fixture. The temporary directory is removed by the test framework after each test.

## Verified Release Window

The integration release marker is:

`Linux 7.1`

Its commit is `8cd9520d35a6c38db6567e97dd93b1f11f185dc6`. At verification time, the marker-to-`HEAD` range contained 15,875 commits. Assertions use stable lower bounds because the public fixture can move forward.

## Verified Contributors and Prefixes

Contributor configuration uses the exact raw author emails emitted by `git log --format=%ae`:

- `kuba@kernel.org`
- `johannes.berg@intel.com`
- `seanjc@google.com`
- `broonie@kernel.org`
- `linkinjeon@kernel.org`

These are major Linux contributors and active subsystem authors. The configured case-sensitive prefixes are deliberately high-volume within the release window:

- `wifi:` — 112 accepted commits
- `KVM:` — 86 accepted commits
- `ksmbd:` — 72 accepted commits
- `ASoC:` — 65 accepted commits
- `net:` — 33 accepted commits

Together they provide 368 accepted commits from only five approved emails across a 15,875-commit range.

## JSON Configuration

All integration settings live under `config/`:

- `userIT.json` — approved Linux author emails
- `moduleIT.json` — Linux prefixes and dynamic PDF sections
- `releaseMarkerIT.json` — `Linux 7.1`
- `aiIT.json` — sanitized endpoint/model settings and request character limit
- `workflowLinuxIT.json` — fixture, temporary diff, and PDF output paths

Runtime code always receives a configuration file path. Full-workflow tests copy the committed workflow JSON into their temporary directory and replace only repository/output paths with test-local absolute paths.

## Test Shape

The non-live integration suite covers:

- JSON loading for verified Linux emails, prefixes, sections, marker, and request limit.
- Marker lookup and a large marker-to-`HEAD` extraction.
- Exact-email filtering and case-sensitive first-prefix classification.
- Real fetch/rebase in a temporary derived worktree.
- Separated diff generation for every configured category.
- Bounded recording-AI calls, dynamic document sections, atomic PDF generation, and diff cleanup.

Assertions prefer stable lower thresholds and invariants over exact current counts.

## Optional Live AI Integration

Live AI integration is skipped unless `RUN_LIVE_AI_IT=1` and the configured API-key environment variable is available in process environment or ignored `.env.local`.

The live test uses one accepted Linux commit per configured module, preserves module separation, applies the configured request bound, redacts authorization headers from inspection assets, and writes generated artifacts only under `tests/assets/`.

Before a live run, generated content under `tests/assets/` is cleared. A successful live run retains its latest sanitized request payloads, diffs, and summaries for manual inspection.

## Generated Assets

Normal full-workflow tests write only inside their framework-managed temporary directory and leave no repository assets behind. Successful workflows delete temporary `diff_*.md` files and retain exactly one final PDF long enough for assertions.
