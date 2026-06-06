# Implementation Plan

This plan breaks the Release Notes Generator scope into TDD implementation phases and small trackable tasks.

Each checkbox indicates whether the phase or task has been completed.

## TDD Workflow Rules

- [ ] Write the class-level/unit tests for a behavior before implementing that behavior
- [ ] Keep class-level/unit tests separate from context/integration tests
- [ ] Keep tests pending or skipped until their target class, module, or code path exists
- [ ] After each implementation task, enable and run only the matching class-level tests first
- [ ] Run context/integration tests only after the involved classes and workflow code exist

## Phase 1: Project Foundation

- [x] Phase complete
- [x] Write pending class-level tests for the expected project structure
- [x] Write pending class-level tests for the main script entry point
- [x] Write pending context tests for the expected runtime flow
- [x] Create the base Python project structure
- [x] Define the main script entry point
- [x] Define the expected runtime flow in the code structure
- [x] Add a location for JSON configuration files
- [x] Add a location for temporary generated diff files
- [x] Add a location for the final Release Notes output
- [x] Enable and run the matching project foundation class-level tests
- [x] Run the project foundation context tests after the runtime flow code exists

## Phase 2: JSON Configuration

- [ ] Phase complete
- [ ] Write class-level tests that approved users are loaded from the users JSON file
- [ ] Write class-level tests that supported modules are loaded from the modules JSON file
- [ ] Write class-level tests for missing or unreadable configuration files
- [ ] Write pending context tests that changing JSON configuration changes filtering behavior without code changes
- [ ] Create the users JSON configuration file
- [ ] Define approved author emails or email-matching rules in the users JSON file
- [ ] Create the modules JSON configuration file
- [ ] Define supported module tags in the modules JSON file
- [ ] Load the users JSON file from Python
- [ ] Load the modules JSON file from Python
- [ ] Validate that required configuration files exist before processing commits
- [ ] Validate that users configuration is readable and usable for author filtering
- [ ] Validate that modules configuration is readable and usable for commit classification
- [ ] Enable and run the matching JSON configuration class-level tests

## Phase 3: Git Commit Extraction

- [ ] Phase complete
- [ ] Write class-level tests for detecting the latest `[Release]` marker in Git history
- [ ] Write class-level tests for extracting commit hash, author email, and message subject
- [ ] Write class-level tests for ignoring commits outside the selected release range
- [ ] Write class-level tests for handling no commits after the release marker
- [ ] Detect the latest `[Release]` marker in the Git history
- [ ] Capture commits created after the latest `[Release]` marker
- [ ] Extract each commit hash
- [ ] Extract each commit author email
- [ ] Extract each commit message subject
- [ ] Ensure commits outside the selected release range are ignored
- [ ] Handle the case where no commits are found after the release marker
- [ ] Enable and run the matching Git commit extraction class-level tests

## Phase 4: Commit Filtering

- [ ] Phase complete
- [ ] Write class-level tests that unauthorized authors are ignored
- [ ] Write class-level tests that unmapped modules are ignored
- [ ] Write class-level tests for matching commit message prefixes against configured module tags
- [ ] Write context tests for configuration-driven filtering behavior
- [ ] Filter commits using the approved users configuration
- [ ] Discard commits from unauthorized authors
- [ ] Parse the beginning of each commit message for module classification
- [ ] Match commit message prefixes against configured module tags
- [ ] Discard commits that do not match a configured module tag
- [ ] Ensure unauthorized commits are never passed to diff generation
- [ ] Ensure unmapped module commits are never passed to diff generation
- [ ] Enable and run the matching commit filtering class-level tests
- [ ] Run the configuration-driven filtering context tests

## Phase 5: Commit Grouping

- [ ] Phase complete
- [ ] Write class-level tests for grouping accepted commit hashes by module category
- [ ] Write class-level tests for skipping empty groups
- [ ] Write context tests that category separation is preserved before AI summarization
- [ ] Group accepted commit hashes by module category
- [ ] Create a Pix commit group
- [ ] Create a GlobalLoyalty commit group
- [ ] Create a TransitOpenLoop commit group
- [ ] Skip empty groups when generating temporary diff files
- [ ] Preserve category separation before AI summarization
- [ ] Enable and run the matching commit grouping class-level tests
- [ ] Run the category separation context tests after grouping code exists

## Phase 6: Diff Generation

- [ ] Phase complete
- [ ] Write class-level tests that category diff files only include commits for their category
- [ ] Write class-level tests that unrelated module diffs are not mixed into the same temporary file
- [ ] Write context tests that accepted commits are rendered into the expected temporary Markdown files
- [ ] Run `git show <hash>` for each accepted commit hash
- [ ] Write Pix diffs to a temporary Markdown file
- [ ] Write GlobalLoyalty diffs to a temporary Markdown file
- [ ] Write TransitOpenLoop diffs to a temporary Markdown file
- [ ] Ensure temporary files contain only filtered commits for their category
- [ ] Ensure unrelated module diffs are not mixed into the same temporary file
- [ ] Enable and run the matching diff generation class-level tests
- [ ] Run the diff generation context tests after file writing code exists

## Phase 7: AI API Summarization

- [ ] Phase complete
- [ ] Write class-level tests that AI summarization receives separate category payloads
- [ ] Write class-level tests that no AI request contains unauthorized or unmapped commit diffs
- [ ] Write context tests for independent Pix, GlobalLoyalty, and TransitOpenLoop summarization calls
- [ ] Read each generated temporary diff Markdown file
- [ ] Send each category diff file independently to the AI API
- [ ] Keep AI requests separated by category
- [ ] Receive a standalone summary for the Pix diff file
- [ ] Receive a standalone summary for the GlobalLoyalty diff file
- [ ] Receive a standalone summary for the TransitOpenLoop diff file
- [ ] Ensure no AI request contains unauthorized or unmapped commit diffs
- [ ] Enable and run the matching AI summarization class-level tests
- [ ] Run the AI summarization context tests with the API client mocked

## Phase 8: Final Release Notes Composition

- [ ] Phase complete
- [ ] Write class-level tests that the final Markdown file contains `## Global Features`
- [ ] Write class-level tests that the final Markdown file contains `## Pix`
- [ ] Write class-level tests for merging GlobalLoyalty and TransitOpenLoop summaries under `## Global Features`
- [ ] Write context tests for exporting the final output as a single `.md` file
- [ ] Create the final Markdown Release Notes document
- [ ] Add a `## Global Features` section
- [ ] Merge the GlobalLoyalty summary under `## Global Features`
- [ ] Merge the TransitOpenLoop summary under `## Global Features`
- [ ] Add a `## Pix` section
- [ ] Insert the Pix summary under `## Pix`
- [ ] Export the final output as a single `.md` file
- [ ] Enable and run the matching release notes composition class-level tests
- [ ] Run the final output context tests after export code exists

## Phase 9: Cleanup

- [ ] Phase complete
- [ ] Write class-level tests that temporary diff files are deleted after generation
- [ ] Write class-level tests that the final Release Notes file remains after cleanup
- [ ] Write context tests for cleanup at the end of the full workflow
- [ ] Delete the temporary Pix diff Markdown file after final output generation
- [ ] Delete the temporary GlobalLoyalty diff Markdown file after final output generation
- [ ] Delete the temporary TransitOpenLoop diff Markdown file after final output generation
- [ ] Ensure the final Release Notes file remains after cleanup
- [ ] Enable and run the matching cleanup class-level tests
- [ ] Run the cleanup context tests after the full workflow code exists

## Phase 10: Full TDD Verification

- [ ] Phase complete
- [ ] Run the complete class-level/unit test suite
- [ ] Run the complete context/integration test suite
- [ ] Confirm every behavior listed in this plan has a test written before its implementation task
- [ ] Confirm no context/integration test is required before all involved classes and workflow code exist
- [ ] Confirm pending or skipped tests are either implemented or explicitly documented for future scope
