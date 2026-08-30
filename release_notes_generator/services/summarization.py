"""Bounded, sequential module summarization and reduction."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

from release_notes_generator.domain.analysis import DiffArtifact
from release_notes_generator.domain.configuration import AISettings
from release_notes_generator.domain.summarization import (
    SummarizationOutcome,
    SummarizationProvenance,
)
from release_notes_generator.services.contracts import (
    ArtifactStore,
    SummaryClient,
    SummaryClientFactory,
)
from release_notes_generator.services.errors import AISummarizationError


REDUCTION_SYSTEM_PROMPT = (
    "Combine the partial release-note summaries into one concise summary. "
    "Preserve user-visible facts and return Markdown bullets."
)


class SummarizationService:
    """Read module artifacts and summarize them without crossing module boundaries."""

    def __init__(
        self,
        artifacts: ArtifactStore,
        client_factory: SummaryClientFactory,
        summary_client: Optional[SummaryClient] = None,
    ) -> None:
        self._artifacts = artifacts
        self._client_factory = client_factory
        self._summary_client = summary_client

    def summarize(
        self,
        artifacts: Sequence[DiffArtifact],
        settings: AISettings,
        env_file: Optional[Path],
    ) -> SummarizationOutcome:
        if not artifacts:
            return SummarizationOutcome((), None)

        client = self._summary_client or self._client_factory.create(settings, env_file)
        summaries: list[tuple[str, str]] = []
        limit = settings.max_diff_characters_per_request
        for artifact in artifacts:
            content = self._read(artifact)
            try:
                partials = [
                    client.summarize(artifact.module_name, chunk)
                    for chunk in split_diff_content(content, limit)
                ]
                summary = _reduce_summaries(
                    artifact.module_name, partials, client, limit
                )
            except AISummarizationError:
                raise
            except Exception as exc:
                raise AISummarizationError(
                    f"AI summarization failed for module: {artifact.module_name}"
                ) from exc
            summaries.append((artifact.module_name, summary))
        return SummarizationOutcome(
            tuple(summaries), _client_execution_provenance(client)
        )

    def _read(self, artifact: DiffArtifact) -> str:
        try:
            return self._artifacts.read_text(artifact)
        except AISummarizationError:
            raise
        except Exception as exc:
            raise AISummarizationError(
                f"Unable to read diff file: {artifact.path}"
            ) from exc


def split_diff_content(diff_content: str, max_characters: int) -> tuple[str, ...]:
    """Split text losslessly, preferring commit and then line boundaries."""
    if max_characters <= 0:
        raise AISummarizationError("AI request character limit must be positive.")
    if len(diff_content) <= max_characters:
        return (diff_content,)
    pieces: list[str] = []
    for segment in _commit_segments(diff_content):
        pieces.extend(_bounded_text_pieces(segment, max_characters))
    return _pack_exact_pieces(pieces, max_characters)


def _client_execution_provenance(
    client: SummaryClient,
) -> Optional[SummarizationProvenance]:
    source = getattr(client, "execution_provenance", None)
    if not callable(source):
        return None
    provenance = source()
    if not isinstance(provenance, SummarizationProvenance):
        raise AISummarizationError(
            "Summary client returned unusable execution provenance."
        )
    return provenance


def _commit_segments(content: str) -> tuple[str, ...]:
    boundaries = [0]
    offset = 0
    for line in content.splitlines(keepends=True):
        if offset and line.startswith("commit "):
            boundaries.append(offset)
        offset += len(line)
    boundaries.append(len(content))
    return tuple(
        content[start:end]
        for start, end in zip(boundaries, boundaries[1:])
        if end > start
    ) or (content,)


def _bounded_text_pieces(content: str, max_characters: int) -> tuple[str, ...]:
    if len(content) <= max_characters:
        return (content,)
    pieces: list[str] = []
    current = ""
    for line in content.splitlines(keepends=True):
        while len(line) > max_characters:
            if current:
                pieces.append(current)
                current = ""
            pieces.append(line[:max_characters])
            line = line[max_characters:]
        if current and len(current) + len(line) > max_characters:
            pieces.append(current)
            current = ""
        current += line
    if current:
        pieces.append(current)
    return tuple(pieces)


def _pack_exact_pieces(
    pieces: list[str], max_characters: int
) -> tuple[str, ...]:
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if current and len(current) + len(piece) > max_characters:
            chunks.append(current)
            current = ""
        current += piece
    if current or not chunks:
        chunks.append(current)
    return tuple(chunks)


def _reduce_summaries(
    module_name: str,
    partial_summaries: list[str],
    client: SummaryClient,
    max_characters: int,
) -> str:
    current = partial_summaries
    for _ in range(20):
        if len(current) == 1:
            return current[0]
        payloads = _pack_summary_payloads(current, max_characters)
        current = [client.reduce(module_name, payload) for payload in payloads]
    raise AISummarizationError(
        f"AI summary reduction did not converge for module: {module_name}"
    )


def _pack_summary_payloads(
    summaries: list[str], max_characters: int
) -> tuple[str, ...]:
    pieces: list[str] = []
    for summary in summaries:
        pieces.extend(_bounded_text_pieces(summary, max_characters))
    payloads: list[str] = []
    current = ""
    for piece in pieces:
        separator = "\n\n" if current else ""
        if current and len(current) + len(separator) + len(piece) > max_characters:
            payloads.append(current)
            current = piece
        else:
            current = f"{current}{separator}{piece}"
    if current:
        payloads.append(current)
    return tuple(payloads)
