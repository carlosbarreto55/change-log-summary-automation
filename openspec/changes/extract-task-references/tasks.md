## 1. Domain Layer - Task Reference Value Object

- [x] 1.1 Add `TaskReference` frozen dataclass to `domain/release_document.py` with fields `reference_id`, `module_name`, and `reference_count`; verify by running existing unit tests to ensure no regression
- [x] 1.2 Add `TaskReference` to `__all__` exports in `domain/__init__.py`; verify import succeeds without circular dependency errors

## 2. Services Layer - Task Extraction Logic

- [x] 2.1 Define default task regex patterns (`WLT-\d+`, `WLTM-\d+`, `P\d{6}-\d+`) as module-level constants in `services/release_document.py`; verify patterns compile without errors and match test strings
- [x] 2.2 Implement `extract_task_references()` method in `ReleaseDocumentService` that extracts, aggregates by `(reference_id, module_name)`, and counts occurrences; verify with unit tests covering single match, multiple matches, repeated references, and no matches
- [x] 2.3 Add optional `task_patterns` parameter to allow configuration-driven pattern override; verify custom patterns work and invalid regex patterns fail fast with clear error

## 3. Services Layer - Document Composition with Task References

- [x] 3.1 Add `TaskReferenceSection` dataclass to represent grouped task references by module; verify it integrates with existing `ReleaseSection` structure
- [x] 3.2 Update `compose_commit_list()` method to call `extract_task_references()` and include task section in the document; verify task section appears after module sections in commit_list mode
- [x] 3.3 Update `compose()` method for `ai_summary` mode to include task section separate from AI summaries; verify task section is independent of AI backend
- [x] 3.4 Ensure task section is omitted when no references are found; verify empty case produces no task section

## 4. Configuration Layer - Optional Task Pattern Configuration

- [x] 4.1 Extend module JSON schema to accept optional `task_patterns` object with `wlt`, `wltm`, `plm` pattern strings; verify existing module JSON files without `task_patterns` continue to work
- [x] 4.2 Load and validate task patterns in `ConfigurationService` if present; verify invalid regex patterns fail during configuration validation, not at extraction time
- [x] 4.3 Pass configured patterns to `ReleaseDocumentService`; verify configured patterns override defaults

## 5. Presentation Layer - PDF Rendering

- [x] 5.1 Update `ReportLabPDFExporter` to render `TaskReferenceSection` with module grouping and reference counts; verify PDF output shows task section after module sections
- [x] 5.2 Format task references as `ReferenceID (Module Name) - Count: N` or similar clear format; verify PDF is readable and properly escaped
- [x] 5.3 Verify task section title is "Task References" and section is omitted when empty; verify PDF generation succeeds with and without task references

## 6. Testing - Unit Coverage

- [x] 6.1 Add unit tests for `TaskReference` dataclass immutability and equality; verify all fields are accessible and frozen behavior works
- [x] 6.2 Add unit tests for regex pattern matching covering WLT, WLTM, PLM patterns and edge cases; verify no false positives on similar strings
- [x] 6.3 Add unit tests for `extract_task_references()` covering aggregation and counting logic; verify reference counts are accurate
- [x] 6.4 Add unit tests for document composition in both `commit_list` and `ai_summary` modes; verify task section placement and content
- [x] 6.5 Add unit tests for configuration loading with and without `task_patterns`; verify defaults and custom patterns work correctly

## 7. Testing - Integration Coverage

- [ ] 7.1 Add context tests for task extraction end-to-end with real commit fixtures; verify task references are extracted from commits with known patterns
- [ ] 7.2 Add Linux integration test configuration with commits containing WLT/WLTM/PLM patterns; verify task section appears in generated PDF
- [ ] 7.3 Verify task extraction does not invoke AI backend in either report mode; verify no AI calls are made for task-only extraction

## 8. Documentation and Verification

- [ ] 8.1 Update README.md with task reference feature description and configuration examples; verify documentation includes pattern customization guidance
- [x] 8.2 Run complete unit test suite; verify all tests pass (184 passed, 4 skipped)
- [ ] 8.3 Run complete context test suite; verify all tests pass
- [ ] 8.4 Run non-live Linux integration suite; verify task references work with real repository fixtures
- [ ] 8.5 Run `openspec validate extract-task-references --type change --strict`; resolve all validation errors before marking change complete
