"""Pure contributor filtering, prefix classification, and grouping."""

from typing import Iterable, Mapping

from release_notes_generator.domain.configuration import ContributorPolicy, ModulePolicy
from release_notes_generator.domain.repository import ClassifiedCommit, Commit


class CommitSelectionService:
    """Apply exact contributor and ordered module policies to extracted commits."""

    def select(
        self,
        commits: Iterable[Commit],
        contributors: ContributorPolicy,
        modules: ModulePolicy,
    ) -> tuple[ClassifiedCommit, ...]:
        approved_authors = set(contributors.approved_author_emails)
        accepted: list[ClassifiedCommit] = []
        for commit in commits:
            if commit.author_email not in approved_authors:
                continue
            module_name = _classify_module(commit.subject, modules.module_tags)
            if module_name is None:
                continue
            accepted.append(
                ClassifiedCommit(
                    commit_hash=commit.commit_hash,
                    author_email=commit.author_email,
                    subject=commit.subject,
                    module_name=module_name,
                    authored_at=commit.authored_at,
                )
            )
        return tuple(accepted)

    def group(
        self, commits: Iterable[ClassifiedCommit]
    ) -> dict[str, tuple[str, ...]]:
        grouped: dict[str, list[str]] = {}
        for commit in commits:
            grouped.setdefault(commit.module_name, []).append(commit.commit_hash)
        return {
            module_name: tuple(commit_hashes)
            for module_name, commit_hashes in grouped.items()
            if commit_hashes
        }


def _classify_module(
    subject: str, module_tags: Mapping[str, Iterable[str]]
):
    for module_name, tags in module_tags.items():
        if any(tag and subject.startswith(tag) for tag in tags):
            return module_name
    return None
