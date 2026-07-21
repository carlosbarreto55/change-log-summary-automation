## Context

The project already has JSON loaders, Git extraction and exact email filtering, commit-subject prefix classification, per-module diff generation, an OpenAI-compatible summarization client, Markdown composition, and complete runtime orchestration. The runtime work from `feat/end-to-end-cli-workflow` has been incorporated into the implementation branch, and its non-live baseline suite passes.

The target repository is a large brownfield worktree with dozens of contributors. Only a small configured set of author emails may contribute content to release notes. Each contributor has one email, squash commits do not occur, and commit prefixes are reliable, so identity aliases, pull-request metadata, and path classification are unnecessary. The target worktree must be fetched and rebased before analysis. Configuration remains JSON-based, runtime code continues to receive a configuration-file path, and integration tests must use a separately managed clone of the public Linux kernel repository (`git@github.com:torvalds/linux.git`) with a bounded configured release window.

## Goals / Non-Goals

**Goals:**

- Rebase the configured worktree before analyzing its rebased `HEAD` and report Git failures without a Python traceback.
- Select the release range using a marker loaded from JSON.
- Retain exact email allowlisting and case-sensitive configured subject-prefix classification.
- Drive final sections and ordering from module JSON rather than hard-coded product names.
- Bound every category-specific diff payload sent for AI summarization.
- Generate one readable PDF and save it atomically at the configured local path.
- Cover filesystem, Git, configuration, workflow, and PDF behavior with unit, context, and Linux-kernel integration tests.

**Non-Goals:**

- Supporting multiple emails per contributor, `.mailmap`, co-author parsing, squash attribution, or pull-request APIs.
- Classifying commits by changed paths, regular expressions, or provider metadata.
- Supporting release boundaries based on dates, tags, or multiple selection strategies.
- Supporting output formats other than PDF or introducing a renderer plugin abstraction.
- Rendering arbitrary Markdown. AI output remains a concise set of bullet lines and paragraphs.
- Running summarization requests concurrently.

## Decisions

### Preserve the existing configuration topology

The runtime JSON remains a manifest that references separate user, module, release-marker, and AI JSON files. Relative paths remain relative to the runtime JSON file, and home-relative paths continue to use `~` expansion.

The users file retains its existing shape:

```json
{
  "approved_author_emails": ["alice@example.com", "bob@example.com"]
}
```

Each module gains one required `section` string:

```json
{
  "modules": [
    {
      "name": "GlobalLoyalty",
      "tags": ["GlobalLoyalty"],
      "section": "Global Features"
    }
  ]
}
```

Module JSON order determines module order. Section order is the order in which each distinct section first appears. A commit is assigned to the first configured module whose non-empty tag is a case-sensitive prefix of the subject, preserving existing classification semantics. Exact author email matching remains a prerequisite for classification.

The release-marker file retains the smallest sufficient schema:

```json
{
  "marker": "[Release]"
}
```

The end boundary is always the successfully rebased `HEAD`; additional boundary modes are not introduced.

The AI JSON gains a required positive `max_diff_characters_per_request` value. A character limit is provider-neutral and avoids adding model-specific tokenizers. It bounds diff content rather than claiming an exact model-token limit.

The runtime `output_path` becomes a required `.pdf` path. Markdown output is intentionally not retained as a second output mode.

### Validate JSON configuration before mutating the repository

The workflow loads and validates the runtime, user, module, release-marker, and AI JSON structures before fetching or rebasing. This prevents a known configuration error from modifying the user's worktree. API-key resolution remains deferred until summaries are actually required, preserving the ability to produce a no-change PDF without an AI request.

### Treat fetch and rebase as mandatory ordered workflow stages

Synchronization remains `git fetch --prune` followed by `git rebase @{u}`. A fetch failure prevents the rebase. A rebase failure preserves the original Git standard error, attempts `git rebase --abort`, and raises a domain error containing the failed stage, original Git message, and abort outcome. No release extraction or output work runs after either failure.

The CLI catches expected configuration, Git, diff, AI, and PDF domain errors, prints a concise message to standard error, and returns a nonzero exit code. Expected failures do not print a Python traceback. In the rebase case, the original Git error remains the primary message; an abort failure is appended with a warning that manual repository recovery may be required.

### Resolve the release marker against rebased HEAD

After successful synchronization, Git history is searched from `HEAD` for the newest commit whose subject contains the configured non-empty marker. The selected range is `<marker-hash>..HEAD`; the marker commit is excluded and later commits are returned oldest first. A missing marker is an expected Git-history failure and prevents diff, AI, and PDF work.

### Chunk within categories and reduce summaries hierarchically

Generated diffs remain separated by module. Each module diff is divided in commit order, preferring commit boundaries and then line boundaries when a single commit exceeds the configured character limit. No chunk may contain another module's content, and no diff text is dropped.

Each chunk receives an independent AI summary. When a module has multiple chunk summaries, those summaries are combined in bounded, module-specific reduction requests until one final module summary remains. This keeps all AI input stages bounded without introducing concurrency or a tokenizer dependency.

### Compose a structured document before rendering PDF

Composition produces an ordered in-memory release document made of a title, configured sections, module headings, and module summaries. Modules without accepted commits are omitted. Sections with no included modules are omitted. If no commits qualify, the document contains the title and a clear `No qualifying changes.` message.

This structure is deliberately small and is consumed directly by the PDF renderer; it is not a general document framework. Summary lines beginning with `- ` or `* ` render as bullets and other non-empty lines render as paragraphs. Renderer-sensitive characters are escaped before being passed to the PDF library.

### Render directly with ReportLab and replace the destination atomically

ReportLab is added as the single runtime PDF dependency. Its Platypus document primitives fit the known title/heading/paragraph/bullet structure without an HTML engine or external executable. The bundled Vera TrueType family is registered and embedded so UTF-8 text is not limited to the PDF base fonts.

The renderer creates the parent directory, writes a temporary PDF beside the destination, closes it successfully, and atomically replaces the configured output path. A render or replacement failure removes the temporary file when possible and leaves any previous destination intact. Successful output starts with the PDF signature and no final Markdown document is written.

### Align integration tests with repository policy

Redis-specific integration tests and JSON fixtures are replaced with equivalents based on a separately available clone of the public Linux kernel repository. A configured marker bounds routine processing to a meaningful brownfield stress window even when Linux's dense merge ancestry causes a nominal shallow clone to retain the complete graph. Contributor emails, category prefixes, and the release marker are selected from and verified against that history. Tests use JSON configuration paths and exercise real Git extraction, filtering, grouping, bounded diff preparation, PDF creation, and cleanup. Networked AI remains opt-in; normal integration runs use a recording summary client.

## Risks / Trade-offs

- [A rebase can conflict and mutate the local branch] → Preserve Git's error, automatically attempt `git rebase --abort`, stop immediately, and explicitly report whether recovery succeeded.
- [The abort command can also fail] → Report both errors without hiding the original rebase failure and tell the user the repository may need manual recovery.
- [A character limit does not exactly equal a model token limit] → Use a conservative configured value and document that it bounds payload text without promising provider-specific token counts.
- [Hierarchical summaries can lose detail] → Preserve commit order, keep all reduction requests module-specific, and use a dedicated reduction instruction that retains user-visible facts.
- [The bundled Vera font does not contain every writing-system glyph] → Guarantee UTF-8 handling for the supported bundled font and fail clearly on rendering errors; broader font coverage remains future scope unless target content requires it.
- [PDF replaces the inspectable Markdown output] → Keep composition independently testable as structured data and retain temporary diffs only for the existing workflow lifetime.

## Migration Plan

1. Add `section` to every module JSON entry and add `max_diff_characters_per_request` to every AI JSON file.
2. Change runtime output paths from `.md` to `.pdf`.
3. Add the ReportLab runtime dependency and update installation metadata.
4. Replace Redis integration fixtures with JSON configurations for the public Linux kernel repository.
5. Run unit tests first, then context tests, then non-live integration tests before enabling the new workflow.

Rollback consists of reverting the change and restoring the previous module, AI, and Markdown output configuration files. Repository synchronization failures never proceed to output generation, and a failed rebase is aborted before returning control when Git permits it.

## Open Questions

None. Contributor identity, commit classification, mandatory rebase behavior, release-boundary semantics, configuration layout, and PDF-only output are resolved for this change.
