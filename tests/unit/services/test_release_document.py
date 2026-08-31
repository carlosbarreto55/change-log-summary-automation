import unittest
from datetime import date, datetime

from release_notes_generator.domain.configuration import ModuleDefinition, ModulePolicy
from release_notes_generator.domain.release_document import (
    ReleaseCommitEntry,
    ReleaseDocument,
    ReleaseModuleCommitList,
    ReleaseModuleSummary,
    ReleaseSection,
)
from release_notes_generator.domain.repository import ClassifiedCommit
from release_notes_generator.services.release_document import ReleaseDocumentService


def compose_release_document(summaries, modules, repository_name, accepted_commits):
    return ReleaseDocumentService().compose(
        summaries, modules, repository_name, accepted_commits
    )


def compose_commit_list_document(modules, repository_name, accepted_commits):
    return ReleaseDocumentService().compose_commit_list(
        modules, repository_name, accepted_commits
    )


class ReleaseNotesCompositionTests(unittest.TestCase):
    def test_commit_list_preserves_configured_and_oldest_first_commit_order(self) -> None:
        pix_old_hash = "0123456789abcdef0123456789abcdef01234567"
        global_hash = "a" * 64
        pix_new_hash = "fedcba9876543210fedcba9876543210fedcba98"
        commits = (
            _commit_with_details(
                pix_old_hash,
                "Pix",
                "Pix: preserve <exact> & café",
                "first@example.com",
                "2026-01-03T23:30:00+00:00",
            ),
            _commit_with_details(
                global_hash,
                "GlobalLoyalty",
                "GL: add rewards",
                "second@example.com",
                "2026-01-04T01:00:00+00:00",
            ),
            _commit_with_details(
                pix_new_hash,
                "Pix",
                "Pix: committed feature",
                "second@example.com",
                "2026-01-05T02:00:00+02:00",
            ),
        )

        document = compose_commit_list_document(
            _module_config(), "linux", commits
        )

        self.assertEqual(
            document,
            ReleaseDocument(
                title="Release Commit Report",
                repository_name="linux",
                qualifying_change_count=3,
                change_start_date=date(2026, 1, 3),
                change_end_date=date(2026, 1, 5),
                sections=(
                    ReleaseSection(
                        title="Global Features",
                        modules=(
                            ReleaseModuleCommitList(
                                "GlobalLoyalty",
                                (ReleaseCommitEntry("GL: add rewards", global_hash),),
                                qualifying_change_count=1,
                                change_start_date=date(2026, 1, 4),
                                change_end_date=date(2026, 1, 4),
                            ),
                        ),
                    ),
                    ReleaseSection(
                        title="Pix",
                        modules=(
                            ReleaseModuleCommitList(
                                "Pix",
                                (
                                    ReleaseCommitEntry(
                                        "Pix: preserve <exact> & café", pix_old_hash
                                    ),
                                    ReleaseCommitEntry(
                                        "Pix: committed feature", pix_new_hash
                                    ),
                                ),
                                qualifying_change_count=2,
                                change_start_date=date(2026, 1, 3),
                                change_end_date=date(2026, 1, 5),
                            ),
                        ),
                    ),
                ),
            ),
        )
        self.assertEqual(document.change_start_iso_week, "2026-W01")
        self.assertEqual(document.change_end_iso_week, "2026-W02")
        pix_module = document.sections[1].modules[0]
        self.assertEqual(
            tuple(entry.subject for entry in pix_module.commits),
            ("Pix: preserve <exact> & café", "Pix: committed feature"),
        )
        self.assertFalse(hasattr(pix_module, "authors"))
        self.assertFalse(hasattr(pix_module.commits[0], "author_email"))

    def test_commit_list_omits_empty_modules_and_sections(self) -> None:
        document = compose_commit_list_document(
            _module_config(),
            "linux",
            (_commit("pix", "Pix", "2026-01-03T12:00:00+00:00"),),
        )

        self.assertEqual(tuple(section.title for section in document.sections), ("Pix",))
        self.assertEqual(
            tuple(module.name for module in document.sections[0].modules), ("Pix",)
        )

    def test_empty_commit_list_document_has_commit_title_and_context(self) -> None:
        document = compose_commit_list_document(
            _module_config(), "empty-repository", ()
        )

        self.assertEqual(
            document,
            ReleaseDocument(
                title="Release Commit Report",
                repository_name="empty-repository",
                qualifying_change_count=0,
                change_start_date=None,
                change_end_date=None,
                sections=(),
                empty_message="No qualifying changes.",
            ),
        )

    def test_sections_modules_and_context_follow_configuration_order(self) -> None:
        commits = (
            _commit("pix", "Pix", "2026-01-04T01:00:00+02:00"),
            _commit("global", "GlobalLoyalty", "2026-01-03T23:30:00-03:00"),
            _commit("transit", "TransitOpenLoop", "2026-02-02T12:00:00+00:00"),
        )

        document = compose_release_document(
            {
                "Pix": "- Pix summary",
                "GlobalLoyalty": "- Global loyalty summary",
                "TransitOpenLoop": "- Transit summary",
            },
            _module_config(),
            repository_name="linux",
            accepted_commits=commits,
        )

        self.assertEqual(
            document,
            ReleaseDocument(
                title="Release Notes",
                repository_name="linux",
                qualifying_change_count=3,
                change_start_date=date(2026, 1, 3),
                change_end_date=date(2026, 2, 2),
                sections=(
                    ReleaseSection(
                        title="Global Features",
                        modules=(
                            ReleaseModuleSummary(
                                "GlobalLoyalty",
                                "- Global loyalty summary",
                                qualifying_change_count=1,
                                change_start_date=date(2026, 1, 4),
                                change_end_date=date(2026, 1, 4),
                            ),
                            ReleaseModuleSummary(
                                "TransitOpenLoop",
                                "- Transit summary",
                                qualifying_change_count=1,
                                change_start_date=date(2026, 2, 2),
                                change_end_date=date(2026, 2, 2),
                            ),
                        ),
                    ),
                    ReleaseSection(
                        title="Pix",
                        modules=(
                            ReleaseModuleSummary(
                                "Pix",
                                "- Pix summary",
                                qualifying_change_count=1,
                                change_start_date=date(2026, 1, 3),
                                change_end_date=date(2026, 1, 3),
                            ),
                        ),
                    ),
                ),
            ),
        )
        self.assertEqual(document.change_start_iso_week, "2026-W01")
        self.assertEqual(document.change_end_iso_week, "2026-W06")

    def test_empty_summaries_and_sections_are_omitted(self) -> None:
        document = compose_release_document(
            {"Pix": "- Pix summary", "GlobalLoyalty": "", "Unknown": "ignored"},
            _module_config(),
            repository_name="linux",
            accepted_commits=(
                _commit("pix", "Pix", "2026-01-03T12:00:00+00:00"),
                _commit("global", "GlobalLoyalty", "2026-01-04T12:00:00+00:00"),
            ),
        )

        self.assertEqual(
            document.sections,
            (
                ReleaseSection(
                    title="Pix",
                    modules=(
                        ReleaseModuleSummary(
                            "Pix",
                            "- Pix summary",
                            qualifying_change_count=1,
                            change_start_date=date(2026, 1, 3),
                            change_end_date=date(2026, 1, 3),
                        ),
                    ),
                ),
            ),
        )

    def test_ranges_are_derived_after_utc_normalization_not_input_order(self) -> None:
        document = compose_release_document(
            {"Pix": "- Combined Pix summary"},
            _module_config(),
            repository_name="payments",
            accepted_commits=(
                _commit("later", "Pix", "2026-01-03T23:30:00-03:00"),
                _commit("earlier", "Pix", "2026-01-04T01:00:00+02:00"),
            ),
        )

        module = document.sections[0].modules[0]
        self.assertEqual(document.qualifying_change_count, 2)
        self.assertEqual(document.change_start_date, date(2026, 1, 3))
        self.assertEqual(document.change_end_date, date(2026, 1, 4))
        self.assertEqual(document.change_start_iso_week, "2026-W01")
        self.assertEqual(document.change_end_iso_week, "2026-W01")
        self.assertEqual(module.qualifying_change_count, 2)
        self.assertEqual(module.change_start_date, date(2026, 1, 3))
        self.assertEqual(module.change_end_date, date(2026, 1, 4))

    def test_no_qualifying_changes_document_has_repository_count_and_clear_message(self) -> None:
        document = compose_release_document(
            {},
            _module_config(),
            repository_name="empty-repository",
            accepted_commits=(),
        )

        self.assertEqual(document.title, "Release Notes")
        self.assertEqual(document.repository_name, "empty-repository")
        self.assertEqual(document.qualifying_change_count, 0)
        self.assertIsNone(document.change_start_date)
        self.assertIsNone(document.change_end_date)
        self.assertIsNone(document.change_start_iso_week)
        self.assertIsNone(document.change_end_iso_week)
        self.assertEqual(document.sections, ())
        self.assertEqual(document.empty_message, "No qualifying changes.")


def _commit(commit_hash: str, module_name: str, authored_at: str) -> ClassifiedCommit:
    return ClassifiedCommit(
        commit_hash=commit_hash,
        author_email="approved@example.com",
        subject=f"{module_name}: change",
        module_name=module_name,
        authored_at=datetime.fromisoformat(authored_at),
    )


def _commit_with_details(
    commit_hash: str,
    module_name: str,
    subject: str,
    author_email: str,
    authored_at: str,
) -> ClassifiedCommit:
    return ClassifiedCommit(
        commit_hash=commit_hash,
        author_email=author_email,
        subject=subject,
        module_name=module_name,
        authored_at=datetime.fromisoformat(authored_at),
    )


def _module_config() -> ModulePolicy:
    return ModulePolicy(
        modules=(
            ModuleDefinition("GlobalLoyalty", ("GL:",), "Global Features"),
            ModuleDefinition("TransitOpenLoop", ("TOL:",), "Global Features"),
            ModuleDefinition("Pix", ("Pix:",), "Pix"),
            ModuleDefinition("Unused", ("Unused:",), "Empty Section"),
        )
    )


if __name__ == "__main__":
    unittest.main()
