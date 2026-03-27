from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ..asset_types import ASSET_TYPE_FOLDERS
from ..config import AppPaths
from ..models.enums import AssetType
from ..models.imports import (
    DetectionResult,
    ImportItemResult,
    ImportRequest,
    ImportResult,
)
from .classifier import detect_asset
from .repository import CatalogRepository
from .utils import file_sha256, new_asset_id, slugify


ASSET_DIRECTORY_MAP: dict[AssetType, str] = dict(ASSET_TYPE_FOLDERS)


def import_path(paths: AppPaths, request: ImportRequest) -> ImportResult:
    source_path = Path(request.input_path)
    repository = CatalogRepository(paths.db_path)
    items: list[ImportItemResult] = []

    if not source_path.exists():
        return ImportResult(
            items=[
                ImportItemResult(
                    source_path=str(source_path),
                    status="failed",
                    message="Path does not exist",
                )
            ]
        )

    for file_path in iter_files(source_path):
        items.append(
            import_file(paths, repository, file_path, request.asset_type_override)
        )

    return ImportResult(items=items)


def iter_files(source_path: Path) -> list[Path]:
    if source_path.is_file():
        return [source_path]
    return sorted(path for path in source_path.rglob("*") if path.is_file())


def import_file(
    paths: AppPaths,
    repository: CatalogRepository,
    source_file: Path,
    asset_type_override: AssetType | None,
) -> ImportItemResult:
    source_hash = file_sha256(source_file)
    duplicate = repository.get_asset_by_hash(source_hash)
    if duplicate is not None:
        return ImportItemResult(
            source_path=str(source_file),
            status="skipped",
            message="Duplicate content already imported",
            asset_id=duplicate["id"],
        )

    try:
        detection = detect_asset(source_file, override=asset_type_override)
        asset_id = new_asset_id()
        stored_path = copy_to_library(paths, source_file, asset_id, detection)

        repository.insert_asset(
            asset_id=asset_id,
            detection=detection,
            source_path=source_file,
            stored_path=stored_path,
            source_hash=source_hash,
        )
        return ImportItemResult(
            source_path=str(source_file),
            status="imported",
            message=f"Imported as {detection.asset_type.value}",
            asset_id=asset_id,
        )
    except Exception as exc:
        return ImportItemResult(
            source_path=str(source_file),
            status="failed",
            message=str(exc),
        )


def review_unknown_asset(
    paths: AppPaths,
    asset_id: str,
    asset_type_override: AssetType,
) -> ImportItemResult:
    return retype_asset(paths, asset_id, asset_type_override, unknown_only=True)


def retype_asset(
    paths: AppPaths,
    asset_id: str,
    asset_type_override: AssetType,
    *,
    unknown_only: bool = False,
) -> ImportItemResult:
    repository = CatalogRepository(paths.db_path)
    asset = repository.get_asset(asset_id)
    if asset is None:
        return ImportItemResult(
            source_path=asset_id,
            status="failed",
            message="Asset not found",
        )

    if unknown_only and asset.asset_type != AssetType.UNKNOWN:
        return ImportItemResult(
            source_path=asset.source_path or asset.stored_path,
            status="failed",
            message="Only unknown assets can be reviewed here",
            asset_id=asset.id,
        )

    source_file = _resolve_review_source(asset.source_path, asset.stored_path)
    if source_file is None:
        return ImportItemResult(
            source_path=asset.source_path or asset.stored_path,
            status="failed",
            message="Original or stored file is no longer available",
            asset_id=asset.id,
        )

    try:
        detection = detect_asset(source_file, override=asset_type_override)
        stored_path = recopy_to_library(
            paths=paths,
            source_file=source_file,
            asset_id=asset.id,
            detection=detection,
            current_stored_path=Path(asset.stored_path),
        )
        source_hash = asset.source_hash or file_sha256(source_file)
        source_reference = Path(asset.source_path) if asset.source_path else source_file
        repository.update_asset_after_review(
            asset_id=asset.id,
            detection=detection,
            source_path=source_reference,
            stored_path=stored_path,
            source_hash=source_hash,
        )
        return ImportItemResult(
            source_path=str(source_file),
            status="imported",
            message=(
                f"Reviewed as {detection.asset_type.value}"
                if unknown_only
                else f"Retyped as {detection.asset_type.value}"
            ),
            asset_id=asset.id,
        )
    except Exception as exc:
        return ImportItemResult(
            source_path=str(source_file),
            status="failed",
            message=str(exc),
            asset_id=asset.id,
        )


@dataclass(slots=True, frozen=True)
class DeleteAssetResult:
    asset_id: str
    title: str
    removed_path: str


@dataclass(slots=True, frozen=True)
class RenameAssetResult:
    asset_id: str
    old_title: str
    new_title: str
    stored_path: str


def delete_asset(paths: AppPaths, asset_id: str) -> DeleteAssetResult:
    repository = CatalogRepository(paths.db_path)
    asset = repository.get_asset(asset_id)
    if asset is None:
        raise ValueError("Asset not found")

    managed_root = Path(asset.stored_path).parent
    trash_root = paths.data_dir / ".trash"
    trash_root.mkdir(parents=True, exist_ok=True)
    staged_path = Path(
        tempfile.mkdtemp(prefix=f"delete-{asset.id}-", dir=str(trash_root))
    )
    staged_asset_root = staged_path / managed_root.name
    moved_to_trash = False

    try:
        if managed_root.exists():
            shutil.move(str(managed_root), str(staged_asset_root))
            moved_to_trash = True
        repository.delete_asset_records(asset.id)
    except Exception:
        if moved_to_trash and staged_asset_root.exists():
            managed_root.parent.mkdir(parents=True, exist_ok=True)
            if managed_root.exists():
                shutil.rmtree(managed_root, ignore_errors=True)
            shutil.move(str(staged_asset_root), str(managed_root))
        shutil.rmtree(staged_path, ignore_errors=True)
        raise

    shutil.rmtree(staged_path, ignore_errors=True)
    return DeleteAssetResult(
        asset_id=asset.id,
        title=asset.title,
        removed_path=str(managed_root),
    )


def rename_asset(paths: AppPaths, asset_id: str, new_title: str) -> RenameAssetResult:
    repository = CatalogRepository(paths.db_path)
    asset = repository.get_asset(asset_id)
    if asset is None:
        raise ValueError("Asset not found")

    clean_title = new_title.strip()
    if not clean_title:
        raise ValueError("New title cannot be empty")

    current_stored_path = Path(asset.stored_path)
    asset_root = current_stored_path.parent
    new_filename = f"{slugify(clean_title)}{current_stored_path.suffix.lower() or current_stored_path.suffix}"
    new_stored_path = asset_root / new_filename

    if (
        current_stored_path.exists()
        and current_stored_path.resolve() != new_stored_path.resolve()
    ):
        if new_stored_path.exists():
            raise ValueError("Target filename already exists")
        current_stored_path.rename(new_stored_path)
    else:
        new_stored_path = current_stored_path

    repository.rename_asset(
        asset_id=asset.id,
        new_title=clean_title,
        stored_path=new_stored_path,
    )
    return RenameAssetResult(
        asset_id=asset.id,
        old_title=asset.title,
        new_title=clean_title,
        stored_path=str(new_stored_path),
    )


def copy_to_library(
    paths: AppPaths, source_file: Path, asset_id: str, detection: DetectionResult
) -> Path:
    directory_key = ASSET_DIRECTORY_MAP[detection.asset_type]
    asset_root = paths.asset_type_dirs[directory_key] / asset_id
    asset_root.mkdir(parents=True, exist_ok=True)

    base_name = slugify(detection.title)
    suffix = source_file.suffix.lower() or ".bin"
    destination = asset_root / f"{base_name}{suffix}"
    shutil.copy2(source_file, destination)
    return destination


def recopy_to_library(
    *,
    paths: AppPaths,
    source_file: Path,
    asset_id: str,
    detection: DetectionResult,
    current_stored_path: Path,
) -> Path:
    destination = copy_to_library(paths, source_file, asset_id, detection)
    if (
        current_stored_path.exists()
        and current_stored_path.resolve() != destination.resolve()
    ):
        previous_root = current_stored_path.parent
        current_stored_path.unlink(missing_ok=True)
        if previous_root.exists() and previous_root.name == asset_id:
            shutil.rmtree(previous_root, ignore_errors=True)
    return destination


def _resolve_review_source(
    source_path_text: str | None,
    stored_path_text: str,
) -> Path | None:
    candidates: list[Path] = []
    if source_path_text:
        candidates.append(Path(source_path_text))
    candidates.append(Path(stored_path_text))
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None
