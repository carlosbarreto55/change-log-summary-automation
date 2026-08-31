"""Dependency-free release-notes domain model."""

from release_notes_generator.domain.release_document import (
    ReleaseCommitEntry,
    ReleaseDocument,
    ReleaseModuleCommitList,
    ReleaseModuleSummary,
    ReleaseSection,
    TaskReference,
    TaskReferenceSection,
)

__all__ = [
    "ReleaseCommitEntry",
    "ReleaseDocument",
    "ReleaseModuleCommitList",
    "ReleaseModuleSummary",
    "ReleaseSection",
    "TaskReference",
    "TaskReferenceSection",
]
