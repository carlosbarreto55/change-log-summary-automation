## Context

The workflow currently composes a `ReleaseDocument` that is independent of its final representation, then passes that document to a PDF-specific exporter port. The document already contains the mode-specific title, repository identity, qualifying-change count, UTC date and ISO-week ranges, ordered sections and modules, AI summaries or deterministic commit entries, task references, and the empty-report message. This separation makes a second renderer possible without changing Git analysis, commit filtering, diff generation, AI summarization, or document composition.

Runtime configuration currently rejects every `output_path` that does not end in `.pdf`. Dependency composition always injects `ReportLabPDFExporter`, application names and workflow text refer to PDF, and the CLI catches only `PDFGenerationError`. The PDF adapter writes through a temporary sibling and atomically replaces the destination after successful rendering. Markdown must preserve that safety boundary and the repository's existing external-output containment rules.

The implementation must remain Python 3.9 compatible, add no unnecessary dependencies, keep unit and integration tests separate, and exercise cross-filesystem/workflow behavior against JSON configuration and the public Linux repository fixture.

## Goals / Non-Goals

**Goals:**

- Select PDF or Markdown from the case-insensitive suffix of `output_path`, producing exactly one final report per run.
- Preserve all information in the composed `ReleaseDocument` in both output formats.
- Keep existing `.pdf` configurations and PDF behavior backward compatible.
- Produce deterministic, UTF-8 Markdown whose dynamic values cannot inject unintended Markdown or raw HTML structure.
- Preserve path containment, temporary-file cleanup, existing-destination preservation, and atomic replacement for Markdown.
- Keep report content mode (`ai_summary` or `commit_list`) independent from output format (`.pdf` or `.md`).

**Non-Goals:**

- Producing PDF and Markdown simultaneously from one run.
- Adding a separate `output_format` configuration field or supporting `.markdown` and other aliases.
- Reproducing PDF typography, pagination, fonts, or visual layout in Markdown.
- Passing arbitrary AI-generated Markdown through unchanged.
- Converting a rendered PDF into Markdown or changing release-range, filtering, task-reference, diff, or AI behavior.

## Decisions

### Use `output_path` as the format selector

Configuration will accept `.pdf` and `.md` suffixes case-insensitively and reject all others before path validation or Git activity. Existing runtime JSON needs no migration, and one field cannot disagree with another format field.

An explicit `output_format` field was considered, but it would duplicate information already carried by the destination and require mismatch rules. Accepting `.markdown` was also considered, but `.md` is sufficient for the requested feature and keeps validation explicit under YAGNI.

### Keep one shared document-composition pipeline

Both renderers will consume the existing `ReleaseDocument`. The application exporter protocol and collaborator names will become format-neutral, while presentation composition will inject a suffix-selecting exporter backed by `ReportLabPDFExporter` and a new `MarkdownExporter`. The selector will defensively reject unsupported suffixes even though configuration validation normally prevents them.

Adding output-format branches to both `commit_list` and `ai_summary` workflow paths was rejected because it would duplicate selection logic and couple content generation to representation.

### Serialize constrained Markdown rather than trusting source Markdown

The Markdown exporter will map the document structure deterministically:

- level-one document title;
- labeled report metadata;
- level-two configured sections;
- level-three module headings and module context;
- escaped summary paragraphs or list items according to the same `- ` and `* ` line-prefix rule used by PDF;
- commit-list bullets containing the escaped exact subject, an em dash, and the complete object ID in inline code;
- a final task-reference section, grouped and ordered as represented by the document; and
- the descriptive empty message when no section is present.

Dynamic text will be escaped for CommonMark punctuation and raw HTML delimiters before structural Markdown is added. The serializer will emit normalized `\n` separators and one trailing newline. This preserves rendered information and deterministic tests while intentionally not preserving arbitrary Markdown styling supplied by an AI summary.

Allowing raw summary Markdown was rejected because the PDF renderer recognizes only bullets and paragraphs; pass-through would produce behavior that is neither parity nor safe structure.

### Preserve adapter-specific atomic export

The Markdown adapter will encode the complete serialization as UTF-8, write it to a temporary sibling, verify that the temporary output is non-empty, and call `os.replace` only after the write succeeds. It will remove the temporary file when possible on success or failure and leave an existing destination untouched when failure occurs before replacement.

The ReportLab adapter will retain its existing path-based temporary rendering. A generalized callback-based atomic-output framework was considered, but the two adapters have materially different write mechanisms and do not yet justify a broader abstraction.

### Generalize application errors without breaking PDF callers

A report-generation base error will allow the CLI to handle PDF and Markdown failures uniformly without a traceback. `PDFGenerationError` will retain its existing public identity, and a Markdown-specific error will identify Markdown serialization or export failures. Configuration and repository-safety failures remain unchanged.

### Test information parity at the document boundary and workflow boundary

Unit tests will assert exact Markdown for representative AI-summary, commit-list, task-reference, UTF-8, escaped-syntax, and empty documents. Export tests will cover atomic success and failure. Configuration and exporter-selection tests will prove suffix behavior before Git activity. Context tests will exercise both report modes through `.md` destinations. A JSON-configured, non-live Linux integration case will exercise deterministic Markdown generation, and installed-wheel coverage will prove the packaged CLI includes the new adapter.

## Risks / Trade-offs

- [Markdown renders slightly differently across viewers] → Use conservative CommonMark headings, emphasis, lists, inline code, blank-line separation, and escaping; assert semantic content rather than viewer-specific appearance.
- [Escaping can make the raw `.md` source noisier] → Prefer safe, stable rendered information over accepting unintended links, headings, lists, or raw HTML.
- [PDF and Markdown renderers can drift as `ReleaseDocument` evolves] → Keep both adapters exhaustive over the same module-content variants and add parity fixtures that fail when a new document field is omitted.
- [A failure after `os.replace` cannot restore the previous destination] → Perform serialization, encoding, writing, and validation before replacement, matching the existing PDF guarantee.
- [The active task-reference OpenSpec change is not archived even though its code is merged] → Define Markdown task-reference rendering explicitly in this change and avoid depending on PDF renderer internals; reconcile the task-reference capability when changes are archived.

## Migration Plan

1. Add `.md` acceptance and format-neutral exporter contracts while retaining `.pdf` as an unchanged supported suffix.
2. Add and wire the Markdown exporter, then update CLI error handling and workflow terminology.
3. Add unit, context, packaging, and JSON-configured Linux integration coverage before documenting the format.
4. Update README, `SPEC.md`, `PLAN.md`, and affected OpenSpec capability text.

Rollback consists of reverting this change. Existing `.pdf` configurations and ReportLab output require no data migration and remain usable throughout.

## Open Questions

None. The proposal fixes `.md` as the only new suffix, selects one output per run from `output_path`, and requires semantic information parity rather than visual parity.
