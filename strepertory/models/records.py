from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .enums import AssetType, Status


@dataclass(slots=True, frozen=True)
class AssetRecord:
    id: str
    asset_type: AssetType
    title: str
    stored_path: str
    imported_at: datetime
    updated_at: datetime
    slug: str | None = None
    description: str | None = None
    payload_format: str | None = None
    source_path: str | None = None
    preview_path: str | None = None
    source_hash: str | None = None
    external_identity: str | None = None
    author: str | None = None
    version: str | None = None
    scope: str | None = None
    status: Status = Status.ACTIVE
    exported_at: datetime | None = None


@dataclass(slots=True, frozen=True)
class AssetDetailsRecord:
    asset: AssetRecord
    raw_payload: str | None
    extracted_summary: dict[str, object]
