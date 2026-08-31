from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.models.legal_authority import LegalAuthorityType


@dataclass
class RawLegalSourcePayload:
    source_system: str
    external_identifier: str
    source_type: LegalAuthorityType
    raw_content: str
    raw_metadata: dict[str, Any]
    retrieval_url: str | None = None
    content_checksum: str = ""


class BaseLegalSourceProvider(ABC):
    """Abstract interface for ingesting raw Indian legal sources (Acts, Regulations, Judgments)."""

    @property
    @abstractmethod
    def source_system_name(self) -> str:
        pass

    @abstractmethod
    def fetch_source(self, external_identifier: str) -> RawLegalSourcePayload:
        pass

    @abstractmethod
    def fetch_all(self) -> list[RawLegalSourcePayload]:
        pass
