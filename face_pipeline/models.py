from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class FaceScan:
    """The non-sensitive summary retained from a face scan."""

    detected: bool
    face_count: int
    primary_face_confidence: float
    bounding_box: list[float]
    embedding_dimensions: int
    detector: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SearchResult:
    """A result discovered by the reverse-image search provider."""

    title: str
    url: str
    snippet: str
    source: str
    discovered_at: str
    search_url: str
    is_social: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AnchorRecord:
    """A tamper-evident record written to the local chain."""

    record_id: str
    data_hash: str
    block_index: int
    block_hash: str
    previous_block_hash: str
    created_at: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)