## Why

The current workflow is tied to three hard-coded product areas, emits only Markdown, and can send category diffs that are too large for an AI request. It needs to become a configuration-driven release-notes tool that can run against a large brownfield repository, count only explicitly approved contributor emails, rebase the local worktree with understandable failure handling, and save a final PDF on the user's disk.

## What Changes

- Keep exact author-email allowlisting and reliable commit-subject prefix matching as the only contributor and module selection mechanisms.
- Require repository synchronization through `git fetch --prune` followed by `git rebase @{u}` before release analysis.
- Handle Git synchronization failures without a Python traceback, preserve the original Git error for the user, attempt to abort a failed rebase, return a nonzero exit code, and stop all downstream processing.
- Keep the release marker in a dedicated JSON file and use it to select commits between the latest matching marker and the successfully rebased `HEAD`.
- Add a configured output section to each module so release-note headings, grouping, and order are no longer hard-coded in Python.
- Split oversized module diffs into bounded AI requests and combine the partial results into one module summary.
- **BREAKING**: Require module entries to define their output section.
- **BREAKING**: Replace the final Markdown output contract with a PDF output path and PDF document saved to local disk.
- Replace the existing Redis integration fixture with a separately managed clone of the public Linux kernel repository (`git@github.com:torvalds/linux.git`), use a bounded configured release window, and define all integration-test configuration in JSON.

## Capabilities

### New Capabilities

- `repository-release-range`: Synchronize and rebase the configured local repository, report Git failures gracefully, and select the configured release-marker-to-`HEAD` range.
- `configurable-release-sections`: Group trusted commit-prefix categories into dynamically configured release-note sections while retaining exact approved-email filtering.
- `bounded-ai-summarization`: Split oversized category diffs into bounded requests and combine their summaries without mixing categories.
- `pdf-release-notes`: Compose and atomically save a Unicode-capable PDF release-notes document at the configured local output path.

### Modified Capabilities

None. The repository has no existing OpenSpec capability specifications.

## Impact

- Affects runtime configuration validation, Git synchronization and extraction, module configuration, workflow orchestration, AI summarization, final composition, CLI error handling, packaging dependencies, documentation, and generated output.
- The PDF output path remains user-controlled and is resolved relative to the runtime JSON file unless absolute or home-relative.
- Expected workflow errors will be written to standard error and return a nonzero process exit code; successful execution continues to return zero.
- Integration coverage must use the public Linux kernel repository and JSON fixture configuration derived from verified contributor emails, high-volume commit prefixes, and a stable release boundary.
- The end-to-end workflow from `feat/end-to-end-cli-workflow` has been incorporated into the implementation branch and its non-live baseline suite passes.
