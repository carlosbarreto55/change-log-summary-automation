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

## Current Integration Test Shape

Keep one integration test for each independently testable workflow part and one integration test for the combined flow.

Current parts:

- Load Redis IT configuration.
- Locate the configured Redis marker commit.
- Extract a large commit range after the marker.
- Filter commits by approved users and configured groups.
- Run the combined extraction, filtering, grouping, and diff-size separation flow.

Assertions should prefer stable thresholds and invariants over exact counts because the local Redis fixture can move forward over time.

## Future Full Workflow Assets

When the full workflow integration test is created after all features are implemented, generated code diffs and AI reports must be stored temporarily under:

`tests/assets/`

Before each full workflow integration test run, every generated file and directory inside `tests/assets/` must be deleted so the test starts from a clean asset directory.

The integration test may recreate `tests/assets/` if it does not exist. The directory is for temporary test artifacts only and should not be used as a source of expected golden files unless that is explicitly decided later.
