## Why

The generated PDF begins with a generic title and presents summaries without identifying the source repository or the period represented. Readers need enough deterministic context to understand which project, qualifying changes, and dates the report covers without inferring them from the file name or AI-written text.

## What Changes

- Add a descriptive report header containing the repository name, the total number of qualifying changes, and the exact calendar-date range covered by those changes.
- Show the corresponding ISO week range as secondary context when qualifying changes exist, while keeping exact dates as the primary representation.
- Add each module's qualifying-change count and exact date range next to its summary so readers can understand when that part of the release evolved.
- Preserve commit author dates through extraction, filtering, and document composition instead of asking the AI to invent or associate dates with summary bullets.
- Keep the existing empty report useful by identifying the repository and stating that no qualifying changes were found, without displaying a fabricated date range.
- Update PDF styling and automated unit, context, and Linux-kernel integration coverage for the richer metadata.

## Capabilities

### New Capabilities

- `release-report-context`: Derive repository, qualifying-change count, calendar range, ISO week range, and per-module temporal context from Git data and render that context in the release-notes PDF.

### Modified Capabilities

None. The repository has no archived main capability specifications.

## Impact

- Affects Git commit extraction and classification models, workflow orchestration, release-document composition, PDF story construction and styles, and release-notes tests.
- The public composition API will require report context and dated classified changes; call sites and tests must be updated together.
- No JSON configuration or output-path changes are required. The repository display name is derived from the configured repository path, and all date metadata comes from Git author timestamps.
- The PDF remains the only output format and retains its existing atomic-write and Unicode behavior.
