# Change Log Summary

Change Log Summary generates release notes from a local Git worktree and saves the result as a PDF on the user's disk. It is designed for large brownfield repositories where many people contribute but only explicitly approved author emails should count toward a release.

The workflow is configuration-driven: contributor emails, trusted commit prefixes, output sections, release boundary, AI request limit, repository path, temporary paths, and final PDF path all come from JSON files.

## How It Works

For one configured run, the tool:

1. Loads and validates every referenced JSON file.
2. Runs `git fetch --prune` and then `git rebase @{u}` in the target worktree.
3. Finds the newest commit whose subject contains the configured release marker.
4. Extracts commits from `<marker>..HEAD`, oldest first, including strict Git author timestamps.
5. Keeps only commits whose raw Git author email exactly matches the contributor allowlist.
6. Assigns each remaining commit to the first module whose case-sensitive prefix matches its subject.
7. Generates one temporary Git diff file per non-empty module.
8. Splits oversized module diffs into bounded, ordered AI requests.
9. Reduces chunk summaries within the same module until one module summary remains.
10. Composes configured sections and modules in JSON order with repository, change-count, and UTC date-range context.
11. Atomically writes one Unicode-capable PDF to the configured local path.
12. Deletes the temporary diff files after successful generation.

Unauthorized authors and unmapped prefixes are discarded before diff generation, so their source changes never reach the AI client.

## Requirements

- Python 3.9 or newer.
- Git available on the host machine.
- A local target worktree whose current branch tracks an upstream branch.
- An OpenAI-compatible API key when qualifying changes require summarization.

## Installation

Create a virtual environment and install the project, including ReportLab:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Run the CLI with a runtime JSON path:

```bash
.venv/bin/change-log-summary --config path/to/workflow.json
```

A successful run returns status `0`. Expected configuration, Git, diff, AI, and PDF failures print a concise message to standard error and return a nonzero status without an expected-error Python traceback.

## Configuration

The runtime manifest references four other JSON files. Relative paths are resolved from the directory containing the runtime manifest. Absolute paths and `~` home-relative paths are supported.

### Runtime manifest

```json
{
  "repository_path": "/absolute/path/to/target/repository",
  "user_config_path": "user.json",
  "module_config_path": "module.json",
  "release_marker_config_path": "releaseMarker.json",
  "ai_config_path": "ai.json",
  "temp_diff_dir": "../tmp/diffs",
  "output_path": "../output/release_notes.pdf",
  "env_file_path": "../.env.local"
}
```

`output_path` is required to end in `.pdf`. Its parent directories are created automatically. The PDF is rendered to a temporary sibling file and replaces the destination atomically only after rendering succeeds.

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

A tag is a trusted, case-sensitive subject prefix. The first matching module wins. Module order follows JSON order; section order follows the first appearance of each section. Empty modules and sections are omitted. If no commits qualify, the PDF contains `No qualifying changes.` and no AI key is required.

### Release boundary

```json
{
  "marker": "Linux 7.1"
}
```

The newest reachable commit whose subject contains this non-empty string is the exclusive lower boundary. The upper boundary is the successfully rebased `HEAD`.

### AI settings

```json
{
  "api_url": "https://provider.example/v1/chat/completions",
  "model": "summary-model",
  "api_key_env_var": "RELEASE_NOTES_AI_API_KEY",
  "prompt": "Summarize the provided module-specific Git diff for release notes.",
  "max_diff_characters_per_request": 120000
}
```

`max_diff_characters_per_request` must be a positive integer. Diff splitting preserves all content, prefers commit boundaries, and falls back to line boundaries for one oversized commit. Chunk and reduction requests remain ordered and module-specific; content from separate modules is never mixed.

The JSON stores only the name of the API-key environment variable. The secret itself can be provided through the process environment or the ignored local env file.

## Repository Synchronization and Recovery

All configuration is validated before the target worktree is changed. The mandatory synchronization sequence is:

```bash
git -C <repository_path> fetch --prune
git -C <repository_path> rebase @{u}
```

If fetch fails, rebase and all release processing stop. If rebase fails, the tool preserves Git's original error, attempts `git rebase --abort`, reports the abort outcome, and stops before marker lookup, diff generation, AI requests, or PDF output. If abort also fails, the message warns that manual repository recovery may be required.

## PDF Output

The final document contains:

- A release-notes title.
- The repository name derived from the final component of `repository_path`.
- The total qualifying-change count and its exact UTC calendar-date range.
- The corresponding ISO year-week value or range, including the ISO year to avoid ambiguity around New Year.
- Non-empty configured section headings.
- Non-empty configured module headings in configured order.
- Each module's qualifying-change count and exact UTC calendar-date range.
- AI summary paragraphs and bullet lines.

For example, a report can show `2026-01-03 – 2026-02-02` as its exact range and `2026-W01 – 2026-W06` as supporting week context. A single date or week is shown once rather than repeated as a range. Author timestamps are normalized to UTC before ranges are calculated.

Dates are attached to the report and module scope, not to individual AI-written bullets. One summary bullet can combine multiple commits, so assigning one source date to it would be misleading. When no commits qualify, the header still identifies the repository and shows a zero count, but omits unavailable date and week rows.

ReportLab Platypus renders the structured document with the bundled Vera TrueType font family. Summary lines beginning with `- ` or `* ` become bullets; other non-empty lines become paragraphs. No final Markdown release-notes file is written.

## Linux Integration Fixture

Integration tests use the public Linux kernel repository as a large brownfield fixture:

```bash
git clone git@github.com:torvalds/linux.git /Users/carloseduardo/Downloads/Project/linux
```

This is a separately managed, multi-gigabyte fixture. Tests skip clearly when it is absent and never mutate it. Fetch/rebase tests create a temporary shared-object clone with a sparse worktree, perform all synchronization there, and remove that temporary clone afterward.

The committed Linux integration JSON uses:

- Release marker `Linux 7.1` (15,875 commits to `HEAD` when verified).
- Five exact contributor emails.
- High-volume prefixes `wifi:`, `KVM:`, `ksmbd:`, `ASoC:`, and `net:`.
- 368 accepted commits when verified.

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

The live test requires the configured API key. It records sanitized request payloads under `tests/assets/`, redacts authorization headers, and preserves the most recent live-run assets for inspection. Normal non-live workflow tests use temporary directories and leave no generated repository assets behind.

## Security Notes

- Never store or commit API keys in JSON.
- Treat temporary diffs and live-test assets as sensitive source artifacts.
- Review contributor emails and prefixes before running against a proprietary repository.
- Use a conservative request character limit appropriate for the selected model.
- Remember that qualifying diff content is sent to the configured external AI endpoint.

## Project Structure

```text
config/                    Default and Linux integration JSON
release_notes_generator/
  commits.py               Synchronization, history extraction, filtering, grouping
  configuration.py         JSON loading and validation
  diffs.py                 Per-module temporary diff generation
  summarization.py         Bounded AI chunking and hierarchical reduction
  composition.py           Ordered structured release document
  pdf_export.py            Atomic ReportLab PDF rendering
  workflow.py              End-to-end orchestration
tests/
  unit/                    Class/module tests
  context/                 Cross-module workflow tests
  integration/             Linux fixture and optional live AI tests
```

## Contributing

Add or update tests before changing behavior. Keep unit tests separate from cross-module and external-repository coverage, keep configuration explicit, and avoid committing generated assets or secrets.

## License

The project is intended for open-source distribution. Add a `LICENSE` file before public release.
