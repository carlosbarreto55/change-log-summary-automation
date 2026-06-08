# Implementation Plan

This plan breaks the Release Notes Generator scope into TDD implementation phases and small trackable tasks.

Each checkbox indicates whether the phase or task has been completed.

## Current Project State

- [x] Project foundation, package entry point, and expected filesystem directories are in place
- [x] Default and integration JSON configuration files exist for users, modules, and release markers
- [x] JSON configuration loaders accept explicit file paths and validate missing, invalid, or unusable files
- [x] Git release-marker detection and release-range commit extraction are implemented in `release_notes_generator/commits.py`
- [x] Author and module filtering are implemented in `release_notes_generator/commits.py`
- [x] Commit grouping is implemented in `release_notes_generator/commits.py`
- [x] Temporary per-module diff Markdown generation is implemented in `release_notes_generator/diffs.py`
- [x] AI summarization is implemented in `release_notes_generator/summarization.py`
- [x] Unit tests cover project structure, CLI entry point, configuration loading, Git extraction, and filtering
- [x] Unit and context tests cover grouping, diff file generation, and AI summarization with mocked clients
- [x] Redis integration tests follow `tests/integration/PROTOCOL.md` and cover IT configuration loading, marker detection, large commit extraction, filtering, runtime grouping, generated diff-file separation, full workflow orchestration, cleanup, and optional live AI summarization
- [x] Local secrets are read from ignored `.env.local`; AI JSON config stores only an environment variable name, endpoint, model, and prompt
- [x] `ReleaseNotesWorkflow.run()` executes the end-to-end CLI workflow from a runtime JSON config
- [x] Target repository synchronization is implemented as `git fetch --prune` plus `git rebase @{u}`
- [x] Full-workflow composition integration and cleanup are implemented

## Current Tooling State

- [x] Create a project-local Python virtual environment at `.venv/`
- [x] Ignore `.venv/` and local package metadata in Git
- [x] Install the project in editable mode inside `.venv/`
- [x] Run tests through `.venv/bin/python`
- [x] Make the project script available through `.venv/bin/change-log-summary`

## TDD Workflow Rules

- [ ] Write the class-level/unit tests for a behavior before implementing that behavior
- [ ] Keep class-level/unit tests separate from context/integration tests
- [ ] Keep tests pending or skipped until their target class, module, or code path exists
- [ ] After each implementation task, enable and run only the matching class-level tests first
- [ ] Run context/integration tests only after the involved classes and workflow code exist
- [x] Run all tests and project scripts through the project virtual environment

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

- [x] Default JSON configuration scope complete
- [x] Write class-level tests that approved users are loaded from the users JSON file
- [x] Write class-level tests that supported modules are loaded from the modules JSON file
- [x] Write class-level tests for missing or unreadable configuration files
- [x] Create an empty integration test scaffold for future configuration-driven tests
- [x] Add integration test assertions that changing JSON configuration changes filtering behavior without code changes after filtering code exists
- [x] Create the default users JSON configuration file: `config/user.json`
- [x] Create the integration users JSON configuration file: `config/userIT.json`
- [x] Define the default approved author email list in the users JSON files
- [x] Create the default modules JSON configuration file: `config/module.json`
- [x] Create the integration modules JSON configuration file: `config/moduleIT.json`
- [x] Define supported module tags in the modules JSON files
- [x] Create the default release marker JSON configuration file: `config/releaseMarker.json`
- [x] Create the integration release marker JSON configuration file: `config/releaseMarkerIT.json`
- [x] Define the default release marker in the release marker JSON files
- [x] Load the default users JSON file from Python
- [x] Load the default modules JSON file from Python
- [x] Load the default release marker JSON file from Python
- [x] Keep runtime code referencing only the default JSON configuration files
- [x] Accept explicit configuration file paths in loader functions for test and future runtime use
- [x] Accept a single runtime workflow configuration file path for full workflow execution
- [x] Validate that required configuration files exist before processing commits
- [x] Validate that users configuration is readable and usable for author filtering
- [x] Validate that modules configuration is readable and usable for commit classification
- [x] Validate that release marker configuration is readable and usable for marker detection
- [x] Enable and run the matching JSON configuration class-level tests through `.venv/bin/python -m unittest`

## Repository Synchronization

- [x] Write class-level tests that target repository synchronization runs before release-marker detection
- [x] Write class-level tests that synchronization failures stop all later processing
- [x] Implement local target repository synchronization through the Git CLI
- [x] Ensure commit extraction does not run after repository synchronization failure
- [x] Ensure temporary diff generation does not run after repository synchronization failure
- [x] Ensure AI API calls do not run after repository synchronization failure
- [x] Ensure final output writing does not run after repository synchronization failure
- [x] Add integration coverage using the protocol Redis fixture after runtime synchronization exists

## Phase 3: Git Commit Extraction

- [x] Phase complete
- [x] Write class-level tests for detecting the latest `[Release]` marker in Git history
- [x] Write class-level tests for extracting commit hash, author email, and message subject
- [x] Write class-level tests for ignoring commits outside the selected release range
- [x] Write class-level tests for handling no commits after the release marker
- [x] Write class-level tests for handling a missing release marker
- [x] Detect the latest `[Release]` marker in the Git history
- [x] Capture commits created after the latest `[Release]` marker
- [x] Extract each commit hash
- [x] Extract each commit author email
- [x] Extract each commit message subject
- [x] Ensure commits outside the selected release range are ignored
- [x] Handle the case where no commits are found after the release marker
- [x] Raise `GitHistoryError` when no release marker is found
- [x] Add Redis integration coverage for locating the configured marker commit
- [x] Add Redis integration coverage for extracting a large commit range after the marker
- [x] Enable and run the matching Git commit extraction class-level tests

## Phase 4: Commit Filtering

- [x] Phase complete
- [x] Write class-level tests that unauthorized authors are ignored
- [x] Write class-level tests that unmapped modules are ignored
- [x] Write class-level tests for matching commit message prefixes against configured module tags
- [x] Write context tests for configuration-driven filtering behavior
- [x] Filter commits using the approved users configuration
- [x] Discard commits from unauthorized authors
- [x] Parse the beginning of each commit message for module classification
- [x] Match commit message prefixes against configured module tags
- [x] Discard commits that do not match a configured module tag
- [x] Ensure unauthorized commits are excluded from filtered output before diff generation
- [x] Ensure unmapped module commits are excluded from filtered output before diff generation
- [x] Add Redis integration coverage for filtering by IT users and groups
- [x] Enable and run the matching commit filtering class-level tests
- [x] Run the configuration-driven filtering context tests

## Phase 5: Commit Grouping

- [x] Phase complete
- [x] Write class-level tests for grouping accepted commit hashes by module category
- [x] Write class-level tests for skipping empty groups
- [x] Write context tests that category separation is preserved before AI summarization
- [x] Add Redis integration coverage that groups accepted commits by configured group through runtime code
- [x] Group accepted commit hashes by module category
- [x] Create a Pix commit group
- [x] Create a GlobalLoyalty commit group
- [x] Create a TransitOpenLoop commit group
- [x] Skip empty groups when generating temporary diff files
- [x] Preserve category separation before AI summarization
- [x] Enable and run the matching commit grouping class-level tests
- [x] Run the category separation context tests after grouping code exists

## Phase 6: Diff Generation

- [x] Phase complete
- [x] Write class-level tests that category diff files only include commits for their category
- [x] Write class-level tests that unrelated module diffs are not mixed into the same temporary file
- [x] Write context tests that accepted commits are rendered into the expected temporary Markdown files
- [x] Add Redis integration coverage that renders grouped commits into separate temporary Markdown files under `tests/assets/`
- [x] Run `git show <hash>` for each accepted commit hash
- [x] Write Pix diffs to a temporary Markdown file
- [x] Write GlobalLoyalty diffs to a temporary Markdown file
- [x] Write TransitOpenLoop diffs to a temporary Markdown file
- [x] Ensure temporary files contain only filtered commits for their category
- [x] Ensure unrelated module diffs are not mixed into the same temporary file
- [x] Enable and run the matching diff generation class-level tests
- [x] Run the diff generation context tests after file writing code exists

## Phase 7: AI API Summarization

- [x] Phase complete
- [x] Write class-level tests that AI summarization receives separate category payloads
- [x] Write class-level tests that no AI request contains unauthorized or unmapped commit diffs
- [x] Write context tests for independent Pix, GlobalLoyalty, and TransitOpenLoop summarization calls
- [x] Read each generated temporary diff Markdown file
- [x] Send each category diff file independently to the AI API
- [x] Keep AI requests separated by category
- [x] Receive a standalone summary for the Pix diff file
- [x] Receive a standalone summary for the GlobalLoyalty diff file
- [x] Receive a standalone summary for the TransitOpenLoop diff file
- [x] Ensure no AI request contains unauthorized or unmapped commit diffs
- [x] Load AI API settings from sanitized JSON without storing the API key in config
- [x] Load the real API key from ignored `.env.local` or process environment
- [x] Add optional live Redis AI integration coverage that makes real requests only when `RUN_LIVE_AI_IT=1`
- [x] Enable and run the matching AI summarization class-level tests
- [x] Run the AI summarization context tests with the API client mocked

## Phase 8: Final Release Notes Composition

- [x] Phase complete
- [x] Write class-level tests that the final Markdown file contains `## Global Features`
- [x] Write class-level tests that the final Markdown file contains `## Pix`
- [x] Write class-level tests for merging GlobalLoyalty and TransitOpenLoop summaries under `## Global Features`
- [x] Write context tests for exporting the final output as a single `.md` file
- [x] Create the final Markdown Release Notes document
- [x] Add a `## Global Features` section
- [x] Merge the GlobalLoyalty summary under `## Global Features`
- [x] Merge the TransitOpenLoop summary under `## Global Features`
- [x] Add a `## Pix` section
- [x] Insert the Pix summary under `## Pix`
- [x] Export the final output as a single `.md` file
- [x] Enable and run the matching release notes composition class-level tests
- [x] Run the final output context tests after export code exists

## Phase 9: Cleanup

- [x] Phase complete
- [x] Write class-level tests that temporary diff files are deleted after generation
- [x] Write class-level tests that the final Release Notes file remains after cleanup
- [x] Write context tests for cleanup at the end of the full workflow
- [x] Delete the temporary Pix diff Markdown file after final output generation
- [x] Delete the temporary GlobalLoyalty diff Markdown file after final output generation
- [x] Delete the temporary TransitOpenLoop diff Markdown file after final output generation
- [x] Ensure the final Release Notes file remains after cleanup
- [x] Enable and run the matching cleanup class-level tests
- [x] Run the cleanup context tests after the full workflow code exists

## Phase 10: Full TDD Verification

- [x] Phase complete
- [x] Run the complete class-level/unit test suite
- [x] Run the complete context/integration test suite
- [x] Confirm every behavior listed in this plan has a test written before its implementation task
- [x] Confirm no context/integration test is required before all involved classes and workflow code exist
- [x] Confirm pending or skipped tests are either implemented or explicitly documented for future scope
- [x] Keep future integration tests aligned with `tests/integration/PROTOCOL.md`
- [x] Add full-workflow verification after `ReleaseNotesWorkflow.run()` is implemented
