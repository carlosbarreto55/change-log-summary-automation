"""Runtime flow definition for release notes generation."""

from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class WorkflowStep:
    """A named step in the release notes generation flow."""

    name: str


DEFAULT_WORKFLOW_STEPS: Tuple[WorkflowStep, ...] = (
    WorkflowStep("locate release marker"),
    WorkflowStep("load approved users"),
    WorkflowStep("load supported modules"),
    WorkflowStep("capture commits after release marker"),
    WorkflowStep("filter commits by approved users"),
    WorkflowStep("classify commits by module tag"),
    WorkflowStep("discard unauthorized or unmapped commits"),
    WorkflowStep("group accepted commits by category"),
    WorkflowStep("generate category diff files"),
    WorkflowStep("send category diffs to AI API"),
    WorkflowStep("receive category summaries"),
    WorkflowStep("merge global feature summaries"),
    WorkflowStep("insert pix summary"),
    WorkflowStep("export final release notes"),
    WorkflowStep("delete temporary diff files"),
)


class ReleaseNotesWorkflow:
    """Coordinates the release notes generation flow."""

    def __init__(self, steps: Optional[Iterable[WorkflowStep]] = None) -> None:
        self._steps = tuple(steps) if steps is not None else DEFAULT_WORKFLOW_STEPS

    def step_names(self) -> List[str]:
        """Return the configured runtime flow in execution order."""
        return [step.name for step in self._steps]

    def run(self) -> int:
        """Execute the workflow once later phases implement each step."""
        raise NotImplementedError(
            "Release notes generation workflow execution is not implemented yet."
        )
