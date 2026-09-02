## ADDED Requirements

### Requirement: Markdown output is selected by its configured path
The system SHALL select Markdown output when runtime JSON `output_path` resolves to a local path whose suffix is `.md`, compared case-insensitively, and SHALL produce exactly one final report at that path.

#### Scenario: Relative Markdown path
- **WHEN** `output_path` is a relative path ending in `.md`
- **THEN** the system resolves it relative to the runtime JSON file's directory and selects Markdown output

#### Scenario: Home-relative Markdown path
- **WHEN** `output_path` begins with `~` and ends in `.md`
- **THEN** the system expands it to the current user's home directory and selects Markdown output

#### Scenario: Markdown output is selected
- **WHEN** a valid workflow configures an `.md` output path
- **THEN** the system writes one Markdown report and does not write a final PDF

### Requirement: Markdown contains the complete release document information
The system SHALL render the composed release document's mode-specific title, repository name, qualifying-change count, available UTC date range, available ISO-week range, non-empty configured sections, non-empty modules, module counts and UTC date ranges, mode-specific module content, optional task references, and descriptive empty message in their established order.

#### Scenario: AI-summary document contains qualifying changes
- **WHEN** `ai_summary` composition produces sections with summary paragraphs and bullet-prefixed lines
- **THEN** Markdown contains the report context, section and module headings, module context, escaped paragraphs, and list items in document order

#### Scenario: Commit-list document contains qualifying changes
- **WHEN** `commit_list` composition produces ordered exact commit entries
- **THEN** Markdown contains the report context, section and module headings, module context, and one ordered entry per exact subject and complete object ID

#### Scenario: Task references exist
- **WHEN** the composed release document contains task references
- **THEN** Markdown renders a final `Task References` section after configured module sections, grouped by module with every identifier and occurrence count

#### Scenario: No task references exist
- **WHEN** the composed release document contains no task-reference section
- **THEN** Markdown contains no `Task References` heading

#### Scenario: No changes qualify
- **WHEN** the composed release document has no included sections and a descriptive empty message
- **THEN** Markdown identifies the repository, shows zero qualifying changes, omits unavailable date and ISO-week fields, and displays `No qualifying changes.`

### Requirement: Markdown structure is deterministic and safe
The system SHALL generate constrained Markdown structure itself, SHALL escape dynamic text that could otherwise create Markdown or raw HTML structure, SHALL interpret only summary lines beginning with `- ` or `* ` as list items, and SHALL retain the complete commit object ID without truncation.

#### Scenario: Dynamic text contains Markdown-sensitive syntax
- **WHEN** a title, repository, section, module, summary line, commit subject, or task reference contains Markdown punctuation or raw HTML delimiters
- **THEN** the generated Markdown renders that value as report text without creating an unintended heading, list, link, image, emphasis span, code span, or raw HTML element

#### Scenario: Summary contains bullets and paragraphs
- **WHEN** an AI module summary contains lines beginning with `- ` or `* ` and other non-empty lines
- **THEN** Markdown renders prefixed lines as list items, other lines as paragraphs, and blank lines as no content

#### Scenario: Commit uses a non-SHA-1 object ID
- **WHEN** a commit-list entry contains an object ID longer than a SHA-1 ID
- **THEN** Markdown renders the complete object ID in inline code after the exact escaped subject and an em dash

#### Scenario: Identical document is rendered repeatedly
- **WHEN** the same release document is exported to Markdown more than once
- **THEN** each successful serialization has identical UTF-8 content with normalized line separators and one trailing newline

### Requirement: Markdown supports UTF-8 text
The system SHALL encode Markdown output as UTF-8 and SHALL preserve supported non-ASCII text from every release-document field.

#### Scenario: Report contains non-ASCII text
- **WHEN** report metadata, headings, summaries, commit subjects, or task references contain non-ASCII characters
- **THEN** the generated Markdown decodes as UTF-8 and contains those characters without replacement or encoding failure

### Requirement: Markdown is saved atomically
The system SHALL write the complete Markdown report to a temporary sibling of the configured destination and atomically replace the destination only after serialization, UTF-8 writing, and non-empty-output validation succeed.

#### Scenario: Successful Markdown generation
- **WHEN** document serialization and Markdown writing succeed
- **THEN** the configured destination is a non-empty UTF-8 Markdown file, the temporary file is removed, and no final PDF is written

#### Scenario: Markdown generation fails
- **WHEN** Markdown serialization or writing fails before replacement
- **THEN** the system removes the temporary file when possible, preserves any existing destination, reports a Markdown generation error, and returns a nonzero exit status
