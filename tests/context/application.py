"""Context-test assembly around the public release-notes use case."""

from pathlib import Path

from release_notes_generator.presentation.composition import compose_release_notes_service


class ReleaseNotesRunner:
    """Small test-facing runner that preserves command-style status assertions."""

    def __init__(self, summary_client=None, warning_handler=None) -> None:
        self._service = compose_release_notes_service(
            summary_client=summary_client, warning_handler=warning_handler
        )

    def run(self, config_path: Path) -> int:
        self._service.generate(config_path)
        return 0

    def step_names(self) -> list[str]:
        return self._service.step_names()
