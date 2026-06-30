"""Base class for all source ingestors."""

from abc import ABC, abstractmethod
from src.schema import RawRecord


class BaseIngestor(ABC):
    source_name: str
    method_name: str

    @abstractmethod
    def ingest(self, source) -> list[RawRecord]:
        """
        Parse the source and return a list of RawRecord (one per candidate found).
        Must never raise — return [] on any failure and log the error.
        """

    def _safe_ingest(self, source) -> list[RawRecord]:
        try:
            return self.ingest(source)
        except Exception as exc:
            print(f"[WARN] {self.source_name} ingestor failed: {exc}")
            return []
