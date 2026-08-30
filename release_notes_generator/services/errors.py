"""Expected application errors presented without tracebacks by the CLI."""


class ConfigurationError(ValueError):
    """Raised when JSON configuration cannot be loaded or used."""


class GitHistoryError(RuntimeError):
    """Raised when Git history cannot be inspected or extracted."""


class DiffGenerationError(RuntimeError):
    """Raised when temporary diff artifacts cannot be managed."""


class AISummarizationError(RuntimeError):
    """Raised when AI summarization cannot be completed."""


class PDFGenerationError(RuntimeError):
    """Raised when the final PDF cannot be generated."""


class RepositorySafetyError(ValueError):
    """Raised when analysis paths cannot preserve worktree safety."""
