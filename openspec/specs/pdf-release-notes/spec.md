## Purpose

Define how configured release notes are rendered as UTF-8-capable PDF documents and written safely to the requested destination.

## Requirements

### Requirement: Runtime output is a configured PDF path
The system SHALL require `output_path` in runtime JSON to resolve to a local path with a `.pdf` extension.

#### Scenario: Relative PDF path
- **WHEN** `output_path` is relative
- **THEN** the system resolves it relative to the runtime JSON file's directory

#### Scenario: Home-relative PDF path
- **WHEN** `output_path` begins with `~`
- **THEN** the system expands it to the current user's home directory

#### Scenario: Non-PDF output path
- **WHEN** `output_path` does not have a `.pdf` extension
- **THEN** the system exits with a configuration error before fetching or rebasing the repository

### Requirement: PDF content follows configured sections
The system SHALL render a release-notes title followed by non-empty configured section headings, module headings, and AI-generated module summaries in configured order.

#### Scenario: Section contains multiple modules
- **WHEN** multiple included modules share a configured section
- **THEN** the PDF renders the section once and renders each module heading and summary beneath it in module configuration order

#### Scenario: Summary contains bullets and paragraphs
- **WHEN** a module summary contains lines beginning with `- ` or `* ` and other non-empty lines
- **THEN** the PDF renders prefixed lines as bullets and other lines as paragraphs

### Requirement: PDF text supports UTF-8 input
The system SHALL render text using an embedded TrueType font rather than relying exclusively on PDF base fonts.

#### Scenario: Summary contains supported non-ASCII characters
- **WHEN** a release title, section, module, or summary contains UTF-8 characters supported by the embedded font
- **THEN** the generated PDF contains those characters without an encoding failure

### Requirement: PDF is saved atomically
The system SHALL build a temporary PDF beside the destination and atomically replace the configured output only after rendering succeeds.

#### Scenario: Successful PDF generation
- **WHEN** document composition and PDF rendering succeed
- **THEN** the configured destination is a non-empty PDF, the temporary file is removed, and no final Markdown output is written

#### Scenario: PDF rendering fails
- **WHEN** PDF rendering fails before replacement
- **THEN** the system removes the temporary file when possible, preserves any existing destination, and returns a nonzero exit status
