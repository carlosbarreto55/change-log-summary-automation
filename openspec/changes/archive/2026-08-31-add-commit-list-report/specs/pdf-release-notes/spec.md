## MODIFIED Requirements

### Requirement: PDF content follows configured sections
The system SHALL render the mode-specific report title followed by non-empty configured section headings, module headings, and either AI-generated module summaries or deterministic commit-list entries in configured order.

#### Scenario: Section contains multiple modules
- **WHEN** multiple included modules share a configured section in `ai_summary` mode
- **THEN** the PDF renders the section once and renders each module heading and summary beneath it in module configuration order

#### Scenario: Summary contains bullets and paragraphs
- **WHEN** an AI module summary contains lines beginning with `- ` or `* ` and other non-empty lines
- **THEN** the PDF renders prefixed lines as bullets and other lines as paragraphs

#### Scenario: Commit-list section contains multiple modules
- **WHEN** multiple included modules share a configured section in `commit_list` mode
- **THEN** the PDF renders the section once and renders each module heading and ordered commit entries beneath it in module configuration order

### Requirement: PDF text supports UTF-8 input
The system SHALL render text using embedded TrueType fonts rather than relying exclusively on PDF base fonts.

#### Scenario: Summary contains supported non-ASCII characters
- **WHEN** a release title, section, module, or AI summary contains UTF-8 characters supported by the embedded font
- **THEN** the generated PDF contains those characters without an encoding failure

#### Scenario: Commit subject contains supported non-ASCII characters
- **WHEN** a commit-list subject contains UTF-8 characters supported by the embedded font
- **THEN** the generated PDF contains those characters without an encoding failure
