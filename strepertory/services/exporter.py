from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from ..config import AppPaths
from ..models.records import AssetRecord
from .repository import CatalogRepository


@dataclass(slots=True, frozen=True)
class ExportedAsset:
    asset_id: str
    title: str
    asset_type: str
    source_path: str
    exported_path: str


@dataclass(slots=True, frozen=True)
class ExportResult:
    export_dir: str
    items: list[ExportedAsset]


def export_assets(
    *,
    paths: AppPaths,
    repository: CatalogRepository,
    asset_ids: list[str],
    destination_root: Path | None = None,
) -> ExportResult:
    if not asset_ids:
        raise ValueError("No assets selected for export")

    export_base = destination_root or paths.exports_dir
    export_dir = export_base
    export_dir.mkdir(parents=True, exist_ok=True)

    exported_items: list[ExportedAsset] = []
    for asset_id in asset_ids:
        asset = repository.get_asset(asset_id)
        if asset is None:
            continue
        exported_items.append(_export_single_asset(export_dir=export_dir, asset=asset))

    return ExportResult(
        export_dir=str(export_dir),
        items=exported_items,
    )


def _export_single_asset(*, export_dir: Path, asset: AssetRecord) -> ExportedAsset:
    source_path = Path(asset.stored_path)
    destination = _build_unique_destination(
        export_dir=export_dir, source_path=source_path
    )
    shutil.copy2(source_path, destination)
    return ExportedAsset(
        asset_id=asset.id,
        title=asset.title,
        asset_type=asset.asset_type.value,
        source_path=str(source_path),
        exported_path=str(destination),
    )


def _build_unique_destination(*, export_dir: Path, source_path: Path) -> Path:
    base_name = source_path.stem
    suffix = source_path.suffix
    candidate = export_dir / source_path.name
    index = 2
    while candidate.exists():
        candidate = export_dir / f"{base_name}-{index}{suffix}"
        index += 1
    return candidate
