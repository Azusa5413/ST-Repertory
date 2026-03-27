from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from .asset_types import ASSET_TYPE_DEFINITIONS


@dataclass(frozen=True)
class AppPaths:
    root: Path
    bundle_root: Path
    data_dir: Path
    assets_dir: Path
    exports_dir: Path
    previews_dir: Path
    db_dir: Path
    db_path: Path

    @classmethod
    def from_roots(cls, root: Path, bundle_root: Path) -> "AppPaths":
        data_dir = root / "data"
        db_dir = root / "db"
        return cls(
            root=root,
            bundle_root=bundle_root,
            data_dir=data_dir,
            assets_dir=data_dir / "assets",
            exports_dir=data_dir / "exports",
            previews_dir=data_dir / "previews",
            db_dir=db_dir,
            db_path=db_dir / "catalog.db",
        )

    @property
    def asset_type_dirs(self) -> dict[str, Path]:
        return {
            item.folder: self.assets_dir / item.folder
            for item in ASSET_TYPE_DEFINITIONS
        }


def get_app_paths(root: Path | None = None) -> AppPaths:
    if root is not None:
        app_root = root
        bundle_root = root
    elif getattr(sys, "frozen", False):
        app_root = Path(sys.executable).resolve().parent
        bundle_root = Path(getattr(sys, "_MEIPASS", app_root))
    else:
        app_root = Path(__file__).resolve().parent.parent
        bundle_root = app_root
    return AppPaths.from_roots(app_root, bundle_root)
