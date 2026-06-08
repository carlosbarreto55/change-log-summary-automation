# Integration Test Protocol

This file records the integration-test decisions made for this project so future context windows can continue the same approach without re-discussing the fixture design.

## Main Goal

Integration tests should verify that the application can process a large real-world Git history and keep release-note inputs separated by configured groups.

The stress target is not just commit extraction. The end goal is to prove that large code diffs can be separated into independent payloads and, once later phases exist, summarized into separate AI-generated reports.

## Fixture Repository

Use the locally cloned Redis repository as the integration fixture:

`/Users/carloseduardo/Downloads/Project/redis`

The Redis clone is intentionally not created by integration tests. Cloning the repository is a separate manual setup operation. Integration tests should only use the local fixture after it exists.

If the Redis repository is missing, or if the path is not a Git repository, integration tests should skip with a clear message.

## Runtime Code Constraint

Changes required only to make integration testing easier should be made in test files or test configuration files only.

Runtime code should only be changed when the tests expose a clear production design problem.

## Release Marker Strategy

Production is expected to use an explicit release marker such as `[Release]` in a commit subject.

For the Redis integration fixture, do not rewrite Redis commits. This is a test-only compromise. Instead, the integration release marker config uses an existing Redis commit subject as the marker:

`Update to latest hiredis (#10297)`

This differs from production behavior and must remain documented as test-only behavior. The current implementation searches Git subjects through `git log %s`, so the marker must match the actual Git commit subject, not a GitHub Markdown title/body rendering.

Current expected marker commit in the local Redis fixture:

`e8c5b66ed2aaf40bec345ff5aca90721fb707d30`

## Integration Config Files

Integration tests use the `*IT.json` files under `config/`. Runtime code must continue referencing default JSON files unless a test explicitly passes an IT config path.

Current Redis IT marker config:

`config/releaseMarkerIT.json`

Current Redis IT users config:

`config/userIT.json`

Approved contributors:

- `debing.sun@redis.com`
- `vitahlin@gmail.com`
- `moticless@gmail.com`

Current Redis IT modules config:

`config/moduleIT.json`

Configured groups:

- `Add` with tags `Add`, `add`
- `Fix` with tags `Fix`, `fix`

Current AI IT config:

`config/aiIT.json`

The AI IT config must not contain an API key. It may contain endpoint, model, prompt, and the environment variable name used to locate the key. The current live AI integration target is OpenCode Go using the OpenAI-compatible `https://opencode.ai/zen/go/v1/chat/completions` endpoint and the `kimi-k2.6` model.

Local AI secrets must live outside version control, currently in `.env.local` or process environment.

Current full workflow IT config:

`config/workflowRedisIT.json`

The full workflow IT config must reference the Redis fixture and the Redis `*IT.json` files. Generated full-workflow artifacts must remain under `tests/assets/`.

## Current Integration Test Shape

Keep one integration test for each independently testable workflow part and one integration test for the combined flow.

Current parts:

- Load Redis IT configuration.
- Locate the configured Redis marker commit.
- Extract a large commit range after the marker.
- Filter commits by approved users and configured groups.
- Run the combined extraction, filtering, grouping, and diff-size separation flow.
- Run the full workflow through `ReleaseNotesWorkflow.run()` using `config/workflowRedisIT.json`, with AI summarization mocked and repository synchronization mocked to avoid mutating the externally managed Redis fixture.
- Optionally run live AI summarization against separated Redis diff payloads.

Assertions should prefer stable thresholds and invariants over exact counts because the local Redis fixture can move forward over time.

## Optional Live AI Integration

Live AI integration tests must be skipped by default.

To run live AI integration tests, set `RUN_LIVE_AI_IT=1` and `OPENCODE_GO_API_KEY` in process environment or the ignored `.env.local` file.

When enabled, live AI integration tests must make real API requests through the configured AI API client. These tests must use Redis-derived diff payloads and write generated diff files, sanitized AI request payload assets, and AI reports only under `tests/assets/`.

Before each live AI integration run, generated content under `tests/assets/` must be deleted so the run starts clean. The test must not delete `tests/assets/` at the end of a successful run; the directory should retain only the most recent run's generated diffs, request payload assets, and summaries for manual inspection.

The API key must be read from the environment variable named by the AI config file. It must never be committed in JSON config, test files, source files, fixtures, or documentation.

## Future Full Workflow Assets

When the full workflow integration test is created after all features are implemented, generated code diffs and AI reports must be stored temporarily under:

`tests/assets/`

Before each full workflow integration test run, every generated file and directory inside `tests/assets/` must be deleted so the test starts from a clean asset directory.

The integration test may recreate `tests/assets/` if it does not exist. The directory is for temporary test artifacts only and should not be used as a source of expected golden files unless that is explicitly decided later.

Full workflow integration tests must not leave temporary diff files behind after a successful run. They may leave the final generated release-notes Markdown file long enough to assert its contents, then clean it up before the test exits.
