from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from strepertory.models.enums import AssetType


@dataclass(slots=True, frozen=True)
class DetectionResult:
    asset_type: AssetType
    payload_format: str
    title: str
    description: str | None = None
    scope: str | None = None
    extracted_summary: dict[str, object] | None = None


@dataclass(slots=True, frozen=True)
class ImportRequest:
    input_path: Path
    asset_type_override: AssetType | None = None


@dataclass(slots=True, frozen=True)
class ImportItemResult:
    source_path: str
    status: str
    message: str
    asset_id: str | None = None


@dataclass(slots=True, frozen=True)
class ImportResult:
    items: list[ImportItemResult]

    @property
    def imported_count(self) -> int:
        return sum(item.status == "imported" for item in self.items)

    @property
    def skipped_count(self) -> int:
        return sum(item.status == "skipped" for item in self.items)

    @property
    def failed_count(self) -> int:
        return sum(item.status == "failed" for item in self.items)
