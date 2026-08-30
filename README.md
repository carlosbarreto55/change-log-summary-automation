# Change Log Summary

Change Log Summary analyzes a local Git worktree and saves a PDF report on the
user's disk. It supports an AI-generated release summary and a deterministic
commit list containing exact Git subjects and full object IDs. It is designed
for large brownfield repositories where many people contribute but only
explicitly approved author emails should count toward a release.

The workflow is configuration-driven: report mode, contributor emails, trusted
commit prefixes, output sections, release boundary, repository path, and final
PDF path come from JSON files. AI and temporary-diff settings apply only to the
`ai_summary` mode.

## What This Project Is

Change Log Summary is a local, configuration-driven CLI for producing a
traceable PDF from a bounded range of Git commits. It is useful when a large
repository needs release reporting based on a small, explicit set of contributor
emails and trusted commit-subject prefixes.

It can produce either of these report forms:

| Report mode | Module content | AI requirement | Temporary source artifacts |
| --- | --- | --- | --- |
| `commit_list` | Exact commit subjects and full object IDs | None | None |
| `ai_summary` | AI-generated module summaries | OpenAI-compatible API or Claude Code | Module diff files, deleted after success or failure |

Both modes preserve the same configured repository, release range, contributor
filtering, module order, section order, qualifying-change counts, UTC date
ranges, and ISO-week context.

## What This Project Is Not

- It is not a hosted service, GitHub application, or background daemon. It runs
  locally when the operator invokes the CLI.
- It is not a pull-request, issue, or release-page aggregator. Its source of
  truth is committed Git history in the configured local worktree.
- It is not a general author-identity resolver. Matching uses exact, raw Git
  author emails and does not apply `.mailmap`, aliases, co-author trailers, or
  pull-request attribution.
- It is not an automatic semantic-versioning or release-boundary tool. The
  operator supplies an explicit base ref or a release-marker selector.
- `commit_list` is not a source-code summary. It deliberately reports only the
  accepted commit subject and full object ID.
- `ai_summary` is not an offline workflow. Accepted source diffs are sent to the
  selected AI backend under that provider's policies.
- A non-LLM report is not automatically network-free. Explicit Git update modes
  can still contact the configured remote; the default `read_only` mode does not.
- The project does not manage API accounts or Claude Code authentication.

## Features

- Two explicit report modes, with `ai_summary` retained as the backward-
  compatible default when `report_mode` is omitted.
- Exact, case-sensitive contributor allowlisting using Git author email.
- Ordered, first-prefix commit classification from JSON module definitions.
- Explicit frozen release ranges using either `base_ref` or a release-marker
  JSON file, always paired with a required `head_ref`.
- Oldest-first commit extraction from immutable full object IDs.
- Read-only repository analysis by default, including dirty, detached, upstream,
  and remote-freshness diagnostics without consuming worktree changes.
- Optional scoped remote-ref refresh and guarded legacy fetch/rebase modes.
- Deterministic commit-list PDFs with exact subjects, full hashes, configured
  module order, and no author subgrouping.
- OpenAI-compatible and restricted Claude Code AI backends with bounded,
  ordered, module-isolated summarization and reduction requests.
- Mode-specific path handling: `commit_list` prepares only the PDF destination;
  `ai_summary` additionally uses an external temporary-diff directory.
- Unicode-capable ReportLab output with document, section, module, count, UTC
  date, and ISO-week context.
- Atomic PDF replacement that preserves an existing destination when rendering
  fails before replacement.
- Descriptive empty reports when no commit passes both filters.
- Layered domain, service, infrastructure, and presentation modules with unit,
  context, Linux-repository integration, and installed-wheel coverage.

## Quick Start

The examples below use `read_only`, so they perform no fetch, checkout, reset,
merge, pull, or rebase. The configured PDF and, for `ai_summary`, temporary diff
directory must be outside the repository being analyzed.

### 1. Install the CLI

```bash
git clone git@github.com:carlosbarreto55/change-log-summary-automation.git
cd change-log-summary-automation
python3 -m venv .venv
.venv/bin/python -m pip install -e .
mkdir -p quickstart
```

Python 3.9 or newer and Git are required.

### 2. Define approved contributors

Create `quickstart/users.json` using the exact author emails shown by Git:

```json
{
  "approved_author_emails": [
    "alice@example.com",
    "bob@example.com"
  ]
}
```

You can inspect candidate values before configuring them:

```bash
git -C /absolute/path/to/repository log --format='%ae' | sort -u
```

### 3. Define modules and PDF sections

Create `quickstart/modules.json`:

```json
{
  "modules": [
    {
      "name": "Network Core",
      "tags": ["net:"],
      "section": "Networking"
    },
    {
      "name": "Wi-Fi",
      "tags": ["wifi:"],
      "section": "Networking"
    },
    {
      "name": "KVM",
      "tags": ["KVM:"],
      "section": "Virtualization"
    }
  ]
}
```

Tags are trusted, case-sensitive subject prefixes. The first configured match
wins. Module order follows this file; section order follows the first appearance
of each section.

### 4. Choose exactly one release boundary

The quickest option is an explicit base ref. Use a tag, branch, or full commit
that exists in the local repository:

```json
"base_ref": "refs/tags/v2.0.0"
```

Alternatively, create `quickstart/release-marker.json`:

```json
{
  "marker": "[Release]"
}
```

Then use this selector in the runtime JSON instead of `base_ref`:

```json
"release_marker_config_path": "release-marker.json"
```

In both cases, configure a non-empty `head_ref`, such as
`refs/remotes/origin/main` or a full commit ID. The selected base and head
objects must already exist locally when using `read_only`.

### 5A. Run the deterministic commit-list form

Create `quickstart/workflow-commit-list.json`:

```json
{
  "report_mode": "commit_list",
  "repository_update_mode": "read_only",
  "repository_path": "/absolute/path/to/repository",
  "head_ref": "refs/remotes/origin/main",
  "base_ref": "refs/tags/v2.0.0",
  "user_config_path": "users.json",
  "module_config_path": "modules.json",
  "output_path": "/absolute/external/path/release-commits.pdf"
}
```

Run it:

```bash
.venv/bin/change-log-summary --config quickstart/workflow-commit-list.json
```

This form needs no AI JSON, API key, environment file, Claude executable, or
temporary diff directory. Each accepted commit is rendered under its configured
module as `<exact subject> — <full object ID>`.

### 5B. Run the AI-summary form with an OpenAI-compatible API

Create `quickstart/ai-openai.json`:

```json
{
  "backend": "openai_compatible",
  "api_url": "https://provider.example/v1/chat/completions",
  "model": "summary-model",
  "api_key_env_var": "RELEASE_NOTES_AI_API_KEY",
  "prompt": "Summarize the provided module-specific Git diff for release notes.",
  "max_diff_characters_per_request": 120000
}
```

Create `quickstart/workflow-ai-summary.json`:

```json
{
  "report_mode": "ai_summary",
  "repository_update_mode": "read_only",
  "repository_path": "/absolute/path/to/repository",
  "head_ref": "refs/remotes/origin/main",
  "base_ref": "refs/tags/v2.0.0",
  "user_config_path": "users.json",
  "module_config_path": "modules.json",
  "ai_config_path": "ai-openai.json",
  "temp_diff_dir": "/absolute/external/path/release-diffs",
  "output_path": "/absolute/external/path/release-notes.pdf"
}
```

Set the named environment variable and run the workflow:

```bash
export RELEASE_NOTES_AI_API_KEY='provider-secret-value'
.venv/bin/change-log-summary --config quickstart/workflow-ai-summary.json
```

Do not place the secret value in any JSON file. You may instead set
`env_file_path` in the runtime JSON to an ignored local environment file.

### 5C. Use Claude Code for the AI-summary form

Create `quickstart/ai-claude.json`:

```json
{
  "backend": "claude_code",
  "model": "sonnet",
  "prompt": "Summarize the provided module-specific Git diff for release notes.",
  "max_diff_characters_per_request": 120000
}
```

Change `ai_config_path` in `workflow-ai-summary.json` to `ai-claude.json`, verify
the operator-owned installation and login, and run the same CLI command:

```bash
claude --version
.venv/bin/change-log-summary --config quickstart/workflow-ai-summary.json
```

The application does not install, log in to, or inspect credentials for Claude
Code. Each request uses a fresh restricted `claude -p` process.

### 6. Find the result

On success, the command returns status `0` and leaves the final PDF at the exact
`output_path`. Expected configuration, Git, diff, AI, and PDF failures print a
concise message to standard error and return a nonzero status without an
expected-error traceback.

## How It Works

For one configured run, the tool:

1. Loads the runtime JSON and the common referenced JSON files, loading the
   release-marker JSON only when marker mode is selected and AI configuration
   only when `ai_summary` is selected.
2. Canonicalizes the Git worktree and validates the mode-specific output paths.
3. Inspects the checkout and reports dirty, detached, upstream-relationship, and remote-freshness diagnostics.
4. Applies the selected repository update mode; the default `read_only` mode performs no network or repository update.
5. Resolves the configured head and exactly one lower boundary to immutable full commit SHAs.
6. Extracts commits from `<base_sha>..<head_sha>`, oldest first, including strict Git author timestamps.
7. Keeps only commits whose raw Git author email exactly matches the contributor allowlist.
8. Assigns each remaining commit to the first module whose case-sensitive prefix matches its subject.
9. Produces the selected content:
   - `ai_summary` groups hashes, creates temporary module diffs, makes bounded AI
     requests, and reduces each module to one summary.
   - `commit_list` composes directly from the accepted subjects and complete
     object IDs without grouping hashes, running `git show`, creating diffs, or
     constructing an AI client.
10. Composes configured sections and modules in JSON order with repository,
    change-count, and UTC date-range context.
11. Atomically writes one Unicode-capable PDF to the configured local path.
12. Deletes temporary diff files after either success or downstream failure in
    `ai_summary` mode.

Unauthorized authors and unmapped prefixes are discarded before either report
is composed. In `ai_summary`, their source changes never reach the AI client.

## Requirements

- Python 3.9 or newer.
- Git available on the host machine.
- A local Git worktree containing the configured boundary commits.
- For `ai_summary` with the `openai_compatible` backend, an API key in the
  configured environment variable when qualifying changes require summarization.
- For `ai_summary` with the `claude_code` backend, Claude Code 2.1.251 or newer available as the
  fixed `claude` executable on `PATH` and authenticated by the operator. Claude
  is not required when no qualifying changes exist or another backend is used.

`commit_list` requires neither an AI configuration nor an API key or Claude
executable.

An attached branch with a resolvable upstream is required only for the explicitly
selected `legacy_in_place_sync` mode.

## CLI Invocation

After installation, invoke either equivalent entry point with an explicit
runtime configuration path:

```bash
.venv/bin/change-log-summary --config path/to/workflow.json
.venv/bin/python -m release_notes_generator --config path/to/workflow.json
```

The command is the same for both report modes; `report_mode` in the runtime JSON
selects the content. The CLI requires `--config`; it has no hard-coded project or
test configuration fallback.

A successful run returns status `0`. Expected configuration, Git, diff, AI, and
PDF failures print a concise message to standard error and return a nonzero
status without an expected-error Python traceback.

## Configuration

The runtime manifest references common contributor and module JSON files plus
one release-boundary selector. An `ai_summary` manifest also references AI
configuration and a temporary diff destination. Relative paths are resolved
from the directory containing the runtime manifest. Absolute paths and `~`
home-relative paths are supported.

### Runtime manifest

```json
{
  "report_mode": "ai_summary",
  "repository_path": "/absolute/path/to/target/repository",
  "head_ref": "refs/remotes/origin/main",
  "base_ref": "refs/tags/v2.0.0",
  "user_config_path": "user.json",
  "module_config_path": "module.json",
  "ai_config_path": "ai.json",
  "temp_diff_dir": "/external/analysis/diffs",
  "output_path": "/external/output/release_notes.pdf",
  "env_file_path": "../.env.local"
}
```

A deterministic commit-list manifest needs no AI, environment, or temporary
diff fields:

```json
{
  "report_mode": "commit_list",
  "repository_path": "/absolute/path/to/target/repository",
  "head_ref": "refs/remotes/origin/main",
  "base_ref": "refs/tags/v2.0.0",
  "user_config_path": "user.json",
  "module_config_path": "module.json",
  "output_path": "/external/output/commit_report.pdf"
}
```

`report_mode` accepts `ai_summary` and `commit_list`. Omitting it preserves
backward compatibility by selecting `ai_summary`. Unknown, blank, and non-string
values fail before path validation or Git activity. In `commit_list`, any
present `ai_config_path`, `env_file_path`, or `temp_diff_dir` values are ignored
without resolving, validating, reading, or retaining them.

`head_ref` is required and must be non-empty. Configure exactly one lower
boundary:

- `base_ref` for an explicit ref or commit, as above; or
- `release_marker_config_path` for the marker JSON described below.

Omitting `repository_update_mode` intentionally selects `read_only`.
In `ai_summary`, `ai_config_path` and `temp_diff_dir` are required, and the
temporary directory must resolve outside the analyzed worktree. `commit_list`
does not validate or create a temporary analysis directory.
`output_path` must end in `.pdf` and must also resolve outside the worktree in
`read_only` and `refresh_remote_refs` modes. Existing symlink aliases and
nonexistent suffixes beneath symlinked ancestors are canonicalized before these
checks. Destination directories are created only after configuration, path,
preflight, update, and range resolution succeed, then their containment is
revalidated. In `commit_list`, only the PDF destination is prepared and
revalidated.

The PDF is rendered to a temporary sibling file and replaces the destination
atomically only after rendering succeeds.

### Contributors

Contributor identity is intentionally exact and simple:

```json
{
  "approved_author_emails": [
    "alice@example.com",
    "bob@example.com"
  ]
}
```

The tool compares these strings with Git's raw `%ae` author email. Matching is case-sensitive. Multiple aliases, `.mailmap`, co-author lines, and pull-request attribution are not used.

### Modules and sections

```json
{
  "modules": [
    {
      "name": "Network Core",
      "tags": ["net:"],
      "section": "Networking"
    },
    {
      "name": "Wi-Fi",
      "tags": ["wifi:"],
      "section": "Networking"
    },
    {
      "name": "KVM",
      "tags": ["KVM:"],
      "section": "Virtualization"
    }
  ]
}
```

A tag is a trusted, case-sensitive subject prefix. The first matching module
wins. Module order follows JSON order; section order follows the first
appearance of each section. Empty modules and sections are omitted. If no
commits qualify, either report contains `No qualifying changes.`; `ai_summary`
does not initialize its configured backend in that case.

### Release boundary

Marker mode uses a runtime selector:

```json
{
  "head_ref": "refs/remotes/origin/main",
  "release_marker_config_path": "releaseMarker.json"
}
```

The referenced marker file contains:

```json
{
  "marker": "Linux 7.1"
}
```

The configured head is resolved first. The newest commit reachable from that
frozen head whose subject contains the non-empty marker is the exclusive lower
boundary. Marker matches in commit bodies are ignored. In explicit-base mode,
both configured refs are resolved once. All later logs and shows use only the
frozen SHAs and derived commit SHAs, never ambient `HEAD`.

### AI settings

AI settings are loaded and used only for `ai_summary`. They are neither needed
nor inspected by `commit_list`.

OpenAI-compatible configuration remains the default when `backend` is omitted.
New configuration should identify it explicitly:

```json
{
  "backend": "openai_compatible",
  "api_url": "https://provider.example/v1/chat/completions",
  "model": "summary-model",
  "api_key_env_var": "RELEASE_NOTES_AI_API_KEY",
  "prompt": "Summarize the provided module-specific Git diff for release notes.",
  "max_diff_characters_per_request": 120000
}
```

Claude Code configuration is keyless and contains no endpoint or credential
location:

```json
{
  "backend": "claude_code",
  "model": "sonnet",
  "prompt": "Summarize the provided module-specific Git diff for release notes.",
  "max_diff_characters_per_request": 120000
}
```

`max_diff_characters_per_request` must be a positive integer. Diff splitting preserves all content, prefers commit boundaries, and falls back to line boundaries for one oversized commit. Chunk and reduction requests remain ordered and module-specific; content from separate modules is never mixed.

For `openai_compatible`, the JSON stores only the name of the API-key
environment variable. The secret itself can be provided through the process
environment or the ignored local env file. Claude Code configuration rejects
`api_url` and `api_key_env_var`; the child process inherits the operator's
environment so Claude Code can apply its supported authentication rules without
this project reading credential data.

Each Claude request runs as a fresh, non-persistent `claude -p` process in an
empty temporary directory. Source-bearing module diffs and reduction inputs are
written only to standard input. The invocation uses JSON-Schema output, safe
mode, disabled slash commands, an empty built-in-tool set, strict empty MCP
configuration, and disabled session persistence. The recorded compatibility
floor is Claude Code 2.1.251; older or unrecognized versions fail before source
is sent.

Missing executables, expired login, usage or capacity limits, timeouts,
nonzero exits, and malformed structured results are expected workflow failures.
They produce a concise sanitized error, delete temporary diff files, and do not
replace an existing PDF. The workflow does not retry with another backend or
bypass a usage limit. Resolve the installation, login, or capacity issue with
Claude Code itself and rerun the same workflow command.

## Repository State and Update Modes

The default repository update mode is read-only:

```json
{
  "repository_update_mode": "read_only"
}
```

This performs no fetch, checkout, switch, reset, merge, pull, or rebase. Dirty
and detached checkouts are allowed because analysis reads committed objects by
SHA. Staged, unstaged, and untracked content is diagnosed but never included in
diffs. Equality between a local branch and its local remote-tracking ref does
not prove the remote server is current, so remote freshness remains explicitly
unknown.

Repository update mode is independent of report mode. A `commit_list` run is
non-LLM but is not necessarily offline: explicitly selecting
`refresh_remote_refs` or `legacy_in_place_sync` still permits the documented Git
network operations before the release range is frozen.

To update only named remote-tracking refs before freezing boundaries:

```json
{
  "repository_update_mode": "refresh_remote_refs",
  "refresh_remote": "origin",
  "refresh_refspecs": [
    "+refs/heads/main:refs/remotes/origin/main"
  ]
}
```

The fetch uses exactly the configured remote and refspecs, disables tag
following, and does not write `FETCH_HEAD`. RefSpec destinations must be inside
`refs/remotes/<refresh_remote>/`. Only named destinations are reported fresh as
of that successful fetch; freshness of all other refs remains unknown. A fetch
failure stops before either boundary is resolved.

The compatibility mode is explicit:

```json
{
  "repository_update_mode": "legacy_in_place_sync"
}
```

Before any mutation, this mode requires a clean attached checkout with a
resolvable upstream. It then runs `git fetch --prune` followed by
`git rebase @{upstream}`. A fetch failure skips the rebase. A rebase failure
preserves Git's original error, attempts `git rebase --abort`, reports an abort
failure separately, and stops all downstream work.

### Migrating existing runtime JSON

Configurations that previously relied on implicit `HEAD` and a marker path must
add an explicit `head_ref`. Keep `release_marker_config_path` to retain marker
selection, or replace it with a non-empty `base_ref`; do not configure both.
Existing workflows that depended on automatic fetch/rebase must intentionally
select `legacy_in_place_sync`, or preferably select `refresh_remote_refs` with
an explicit remote and remote-tracking refspec. Move temporary diffs and, for
read-only or refresh mode, PDF output outside the analyzed worktree.

## PDF Output

Every final document contains:

- A mode-specific title: `Release Notes` for `ai_summary` or
  `Release Commit Report` for `commit_list`.
- The repository name derived from the final component of `repository_path`.
- The total qualifying-change count and its exact UTC calendar-date range.
- The corresponding ISO year-week value or range, including the ISO year to avoid ambiguity around New Year.
- Non-empty configured section headings.
- Non-empty configured module headings in configured order.
- Each module's qualifying-change count and exact UTC calendar-date range.
- Mode-specific module content:
  - `ai_summary` renders AI summary paragraphs and bullet lines.
  - `commit_list` renders one bullet per qualifying commit as its exact subject,
    including the matched prefix, followed by an em dash and the complete Git
    object ID. Entries remain oldest first within each module and are not
    grouped by author.

For example, a report can show `2026-01-03 – 2026-02-02` as its exact range and `2026-W01 – 2026-W06` as supporting week context. A single date or week is shown once rather than repeated as a range. Author timestamps are normalized to UTC before ranges are calculated.

Dates are attached to the report and module scope, not to individual summaries
or commit entries. One AI summary bullet can combine multiple commits, so
assigning one source date to it would be misleading; commit-list entries also
avoid adding unrequested per-entry dates. When no commits qualify, the header
still identifies the repository and shows a zero count, but omits unavailable
date and week rows.

ReportLab Platypus renders the structured document with the bundled Vera
TrueType font family. Summary lines beginning with `- ` or `* ` become bullets;
other non-empty lines become paragraphs. Commit subjects are escaped, and full
object IDs use a monospaced face with natural wrapping and no truncation. No
final Markdown release-notes file is written.

## Linux Integration Fixture

Integration tests use the public Linux kernel repository as a large brownfield fixture:

```bash
git clone git@github.com:torvalds/linux.git /Users/carloseduardo/Downloads/Project/linux
```

This is a separately managed, multi-gigabyte fixture. Tests skip clearly when
it is absent and never mutate it. Direct fixture tests use default read-only
analysis with exact before/after snapshots. Refresh and fetch/rebase tests
create temporary shared-object clones with sparse worktrees and remove those
clones afterward.

The committed Linux integration JSON files use:

- Explicit head `b95f03f04d475aa6719d15a636ddf32222d55657`.
- Release marker `Linux 7.1` (15,875 commits in the configured frozen range).
- Five exact contributor emails.
- High-volume prefixes `wifi:`, `KVM:`, `ksmbd:`, `ASoC:`, and `net:`.
- 368 accepted commits when verified.

`config/workflowLinuxIT.json` explicitly selects `ai_summary`, while
`config/workflowLinuxCommitListIT.json` demonstrates the same frozen selection
as `commit_list` with no AI, environment, or temporary-diff configuration.

See `tests/integration/PROTOCOL.md` for the exact verified emails, counts, safety rules, and fixture behavior.

## Testing

Run suites in increasing scope:

```bash
.venv/bin/python -m unittest discover -v tests/unit
.venv/bin/python -m unittest discover -v tests/context
RUN_LIVE_AI_IT=0 .venv/bin/python -m unittest discover -v tests/integration
```

Run the optional networked AI integration test:

```bash
RUN_LIVE_AI_IT=1 .venv/bin/python -m unittest -v tests.integration.test_ai_summarization_live
```

Run the optional live Claude Code Linux integration only after verifying the
operator login:

```bash
RUN_LIVE_CLAUDE_CODE_IT=1 \
CLAUDE_CODE_OPERATOR_LOGGED_IN=1 \
.venv/bin/python -m unittest -v tests.integration.test_claude_code_live
```

The OpenAI-compatible live test requires the configured API key. It records
sanitized request payloads under `tests/assets/`, redacts authorization headers,
and preserves the most recent live-run assets for inspection. Normal non-live
workflow tests use temporary directories and leave no generated repository
assets behind.

The live Claude Code test has separate opt-in and login-attestation gates. It
uses one accepted Linux commit per configured module and stores no prompts,
diffs, summaries, credentials, account identity, or raw Claude process output.

## Security Notes

- Never store or commit API keys in JSON.
- Treat `ai_summary` temporary diffs and live-test assets as sensitive source
  artifacts.
- Review contributor emails and prefixes before running against a proprietary repository.
- Use a conservative request character limit appropriate for the selected model
  in `ai_summary`.
- `commit_list` does not send content to an AI provider or create source-bearing
  diff artifacts, but its PDF intentionally discloses accepted commit subjects
  and complete object IDs. Protect the destination accordingly.
- Non-LLM does not mean network-disabled: `refresh_remote_refs` and
  `legacy_in_place_sync` perform explicit Git network operations in either
  report mode. Use the default `read_only` mode when the run must avoid them.
- A keyless Claude Code configuration does not mean local inference. Qualifying,
  approved source content is still transmitted by Claude Code to Anthropic or
  the operator's configured remote provider under that account and provider's
  policies.
- Never infer the active Claude authentication method from inherited
  environment values; verify the intended login directly with Claude Code.
- Remember that qualifying diff content is sent to the selected backend's
  configured external provider.

## Project Structure

```text
config/                    Default, AI-summary, and commit-list integration JSON
release_notes_generator/
  domain/                   Immutable values, enums, and pure value behavior
  services/                 Use case, workflow services, and narrow Protocol ports
  infrastructure/           JSON, Git, filesystem, AI, env-file, and PDF adapters
  presentation/             CLI parsing, error handling, and manual composition
  __main__.py               `python -m release_notes_generator` entry point
tests/
  unit/
    domain/                 Dependency-free value behavior
    services/               Workflow and transformation behavior with injected fakes
    infrastructure/         Adapter behavior and external-error mapping
    presentation/           CLI and AST-enforced architecture boundaries
  context/                 Cross-module workflow tests
  integration/             Linux fixture, packaging, and optional live AI tests
```

The dependency direction is intentionally one-way. `domain` imports only the
Python standard library. `services` imports domain values and its own minimal
ports, never concrete adapters. `infrastructure` implements those ports and
returns domain values. `presentation` is the composition root: it manually
wires infrastructure into services and owns CLI exit codes and error text.
Package initializers perform no imports or runtime setup.

`ReleaseNotesService.generate(config_path)` is the application use-case entry
point. It accepts the runtime configuration path explicitly, validates every
referenced JSON file before Git or filesystem side effects, and returns the
generated PDF path. Provider clients remain lazy when no commits qualify.
In `commit_list`, provider construction and all diff operations are unreachable.

## Contributing

Add or update tests before changing behavior. Keep unit tests separate from cross-module and external-repository coverage, keep configuration explicit, and avoid committing generated assets or secrets.

## License

The project is intended for open-source distribution. Add a `LICENSE` file before public release.
