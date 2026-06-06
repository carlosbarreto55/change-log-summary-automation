# AI-Powered Automated Release Notes Generator

## Objective

Build a Python automation script that extracts, filters, groups, and summarizes Git commit diffs into a final categorized Release Notes document.

The tool must process only commits that match approved authors and mapped module tags, split the resulting diffs into smaller category-specific payloads, send each payload independently to an AI API, and compose the AI responses into a single final Markdown file.

## Context

The project is intended to support release auditing for a global codebase with multiple modules and many contributors.

Because AI APIs have context window limitations, the script must avoid sending the full repository history or unrelated code changes. Instead, it must locally filter commits first, then generate focused diff files for each accepted category.

The main modules currently in scope are:

- Pix
- GlobalLoyalty
- TransitOpenLoop

## Tech Stack

- Python for the automation script
- Git CLI for commit history and diff extraction
- JSON for configurable users and modules
- Markdown for temporary diff files and final release notes output
- AI API integration for summarizing filtered diffs

## Functional Requirements

### Input Filters

The script must support the following filters:

- Starting commit based on the last `[Release]` marker
- Approved author emails loaded from a users JSON file
- Approved module tags loaded from a modules JSON file

### Configuration Files

Approved users and supported modules must be defined through JSON configuration files.

The script must use one JSON file for users and one JSON file for modules.

The users JSON file must define the approved author emails or email-matching rules used during author filtering.

The modules JSON file must define the supported module tags used during commit classification.

These files are required so tests and future changes can update filtering behavior without changing the Python implementation.

### Commit Extraction

The script must capture all commits created after the selected `[Release]` marker.

Commits outside this range must not be processed.

### Author Filtering

The script must discard commits where the author email does not match the approved users configuration loaded from the users JSON file.

Unauthorized authors must not have their code diffs included in temporary files or AI API requests.

### Module Classification

The script must inspect the beginning of each commit message and classify matching commits into supported module categories.

The supported categories are:

- Pix
- GlobalLoyalty
- TransitOpenLoop

The supported categories must come from the modules JSON file.

Commits that do not match one of the supported module tags must be discarded.

### Commit Grouping

After filtering and classification, the script must group matching commit hashes by category.

Each category must be processed independently.

### Diff Generation

For each category group, the script must run `git show <hash>` for each commit hash in that group.

The raw output must be saved into separate temporary Markdown files, such as:

- `diff_pix.md`
- `diff_gl.md`
- `diff_transit.md`

Temporary diff files must contain only commits that passed both the author filter and module classification.

### AI Summarization

Each generated diff Markdown file must be sent independently to the AI API.

The script may send requests sequentially or simultaneously, as long as each request contains only one category-specific diff payload.

The purpose of this step is to generate standalone summaries for each mapped category.

### Final Composition

The script must compose a single final Markdown Release Notes document using the AI-generated summaries.

The final document must follow these grouping rules:

- GlobalLoyalty and TransitOpenLoop summaries must be merged under `## Global Features`
- Pix summaries must be inserted under `## Pix`

The output must be a single `.md` file.

### Cleanup

After the final Release Notes file is generated, the script must delete the temporary category diff files.

## Execution Flow

1. Locate the last `[Release]` marker.
2. Load approved users from the users JSON file.
3. Load supported module tags from the modules JSON file.
4. Capture all commits after that release marker.
5. Filter commits by the approved users configuration.
6. Parse commit message prefixes to classify commits by configured module tag.
7. Discard commits from unauthorized authors or unmapped modules.
8. Group accepted commit hashes by category.
9. Generate temporary raw diff Markdown files per category using `git show <hash>`.
10. Send each temporary diff file independently to the AI API.
11. Receive standalone AI summaries for each category.
12. Merge GlobalLoyalty and TransitOpenLoop summaries under `## Global Features`.
13. Insert the Pix summary under `## Pix`.
14. Export the final Release Notes Markdown file.
15. Delete temporary diff Markdown files.

## Acceptance Criteria

- Commits from unauthorized authors are not processed.
- Commits from unmapped modules are not processed.
- Approved users are loaded from a users JSON file.
- Supported modules are loaded from a modules JSON file.
- Filtering behavior can be changed by updating the JSON configuration files without changing the Python code.
- Temporary diff files contain only strictly filtered code diffs.
- AI API requests are split by category to respect token limits.
- No AI API request contains unrelated module diffs.
- The final output is a single Markdown file.
- The final output contains a `## Global Features` section for GlobalLoyalty and TransitOpenLoop summaries.
- The final output contains a `## Pix` section for Pix summaries.
- Temporary Markdown diff files are deleted after final output generation.

## Out Of Scope For This Spec

- Selecting a specific AI provider or model
- Defining the exact prompt text sent to the AI API
- Defining the final Release Notes file name
- Defining command-line arguments or configuration file format
- Defining retry, rate-limit, or authentication behavior for the AI API
