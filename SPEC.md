# Configuration-Driven PDF Release Notes Generator

## Objective

Build a Python CLI that generates categorized release notes from a local brownfield Git worktree. The tool must count only commits from explicitly approved author emails, classify those commits by trusted subject prefixes, bound all AI input, and atomically save one final PDF on the user's disk.

## Core Assumptions

- The target repository does not squash commits used for release attribution.
- Every counted contributor is identified by one exact Git author email.
- Commit subject prefixes are reliable and can be trusted for category classification.
- The current local branch tracks an upstream branch and can be rebased.
- Runtime behavior is controlled by JSON configuration paths rather than project-specific Python constants.

## Configuration

The CLI must receive a runtime JSON path. That manifest must provide paths for:

- The target repository.
- Contributor configuration.
- Module and section configuration.
- Release-marker configuration.
- AI configuration.
- Temporary diff output.
- Final PDF output.
- An optional local environment file.

Relative paths must resolve from the runtime JSON directory. Absolute and home-relative paths must be supported. The final output path must end in `.pdf`.

### Contributors JSON

The contributors file must contain `approved_author_emails` as a list of strings. A commit is approved only when its raw Git `%ae` value exactly and case-sensitively equals a configured value.

### Modules JSON

The modules file must contain an ordered `modules` list. Every entry must define:

- A non-empty `name`.
- A non-empty list of non-empty `tags`.
- A non-empty output `section`.

The first configured module whose tag is a case-sensitive prefix of the commit subject wins. Module order follows JSON order. Section order follows the first appearance of each distinct section in that order.

### Release Marker JSON

The release-marker file must contain one non-empty `marker` string. The newest reachable commit whose subject contains the marker is the exclusive lower release boundary. The successfully rebased `HEAD` is the upper boundary.

### AI JSON

The AI file must contain non-empty endpoint, model, API-key environment-variable name, and prompt strings, plus a positive integer `max_diff_characters_per_request`. It must not contain an API-key value.

All referenced JSON structures must be loaded and validated before repository synchronization begins.

## Repository Synchronization

Before marker lookup or extraction, the tool must run against the configured worktree:

1. `git fetch --prune`
2. `git rebase @{u}`

A fetch failure must prevent rebase and all later work. A rebase failure must preserve Git's original error, attempt `git rebase --abort`, report the recovery outcome, and prevent marker lookup, diff generation, AI requests, and PDF generation.

Expected configuration, Git, diff, AI, and PDF failures must produce concise standard-error output, a nonzero CLI status, and no expected-error Python traceback.

## Commit Extraction and Selection

The tool must find the newest configured marker against the rebased `HEAD`, exclude that marker commit, and extract later commits oldest first. Each extracted record must contain commit hash, raw author email, and subject.

Only commits that pass both rules may continue:

1. Exact author-email allowlist match.
2. First configured case-sensitive subject-prefix match.

Unauthorized and unmapped commits must be discarded before diff generation and AI processing.

Git history and diff decoding must tolerate legacy non-UTF-8 bytes by replacing undecodable characters rather than crashing the workflow.

## Diff Generation

Accepted hashes must be grouped by module. For each non-empty group, the tool must run `git show <hash>` in commit order and write one temporary UTF-8 Markdown diff file. Files must never mix hashes from different modules.

## Bounded AI Summarization

Each module diff must be split into ordered chunks no larger than `max_diff_characters_per_request` characters. Splitting must:

- Preserve all diff text exactly.
- Prefer commit boundaries.
- Prefer line boundaries when one commit is oversized.
- Never include content from another module.

Chunks must be summarized sequentially. Multiple partial summaries must be reduced through bounded, ordered, module-specific requests until exactly one summary remains per included module. Unauthorized, unmapped, and cross-module content must never enter either initial or reduction requests.

If no module has an accepted commit, the tool must skip AI-key resolution and generate a document containing `No qualifying changes.`

## Structured Composition

Before rendering, the tool must compose an ordered release document containing:

- Title `Release Notes`.
- Non-empty configured sections.
- Non-empty module headings in configured module order.
- One final summary per included module.

Modules without accepted commits and sections without included modules must be omitted. Summary lines starting with `- ` or `* ` are bullets; other non-empty lines are paragraphs.

## PDF Output

ReportLab Platypus must render the structured document directly with the bundled Vera TrueType font family. Renderer-sensitive text must be escaped.

The renderer must:

1. Create the destination parent directory.
2. Render to a temporary sibling file.
3. Atomically replace the configured destination only after successful rendering.
4. Remove the temporary file on success or failure when possible.
5. Preserve an existing destination when rendering fails before replacement.

Successful output must be a non-empty PDF beginning with `%PDF-`. No final Markdown release-notes document may be written.

After successful PDF generation, temporary module diff files must be deleted.

## Integration Fixture

Integration tests must use the public Linux kernel repository at `git@github.com:torvalds/linux.git`, available as a separately managed local fixture. They must use JSON configuration and must never synchronize or otherwise mutate that external fixture directly.

Synchronization tests must create an isolated temporary worktree derived from the fixture. The suite must cover a large configured marker-to-`HEAD` range, a small exact-email allowlist, high-volume reliable prefixes, separated real diffs, bounded recording-AI calls, dynamic sections, PDF creation, and cleanup.

The networked AI integration test must remain opt-in and must never record authorization secrets.

## Acceptance Criteria

- Every runtime decision described above is loaded from a configuration file path.
- Invalid configuration fails before fetch or rebase.
- Fetch runs before rebase; synchronization failures stop downstream work.
- Rebase failures attempt abort and expose the original Git error.
- Only exact approved emails and configured first-match prefixes are included.
- The release range begins after the configured marker and ends at rebased `HEAD`.
- All AI diff and reduction payloads are bounded and module-specific.
- Section and module ordering is configuration-driven.
- Exactly one final PDF is atomically saved to the configured local path.
- Temporary diffs are removed after a successful run.
- Unit, context, and non-live Linux integration suites pass.

## Out of Scope

- Multiple-email aliases, `.mailmap`, co-author parsing, squash attribution, or pull-request APIs.
- Date, tag, or multi-strategy release boundaries.
- Path-based or regular-expression classification.
- Concurrent AI requests.
- Exact provider-token counting.
- Output formats other than PDF.
- Arbitrary Markdown rendering.
