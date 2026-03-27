from __future__ import annotations

import argparse
import importlib
from pathlib import Path

from strepertory import APP_NAME, APP_VERSION
from strepertory.config import get_app_paths
from strepertory.models.enums import AssetType
from strepertory.services.importer import ImportRequest, import_path
from strepertory.services.bootstrap import bootstrap_application


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} {APP_VERSION} 本地资产整理工具"
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init", help="Initialize folders and database")

    import_parser = subparsers.add_parser("import", help="Import a file or directory")
    import_parser.add_argument("path", help="File or directory path to import")
    import_parser.add_argument(
        "--type",
        dest="asset_type",
        choices=[asset_type.value for asset_type in AssetType],
        help="Override detected asset type",
    )

    subparsers.add_parser("gui", help="Launch the desktop GUI")

    return parser


def run_init() -> None:
    paths = get_app_paths()
    result = bootstrap_application(paths)

    print(f"{APP_NAME} {APP_VERSION} 初始化完成。")
    print(f"Database: {result.database_path}")
    if result.created_directories:
        print("Created directories:")
        for directory in result.created_directories:
            print(f"- {directory}")
    else:
        print("No new directories were needed.")


def run_import(import_target: str, asset_type_override: str | None) -> None:
    paths = get_app_paths()
    bootstrap_application(paths)

    request = ImportRequest(
        input_path=Path(import_target).expanduser().resolve(),
        asset_type_override=AssetType(asset_type_override)
        if asset_type_override
        else None,
    )
    result = import_path(paths=paths, request=request)

    print(f"Imported files: {result.imported_count}")
    print(f"Skipped files: {result.skipped_count}")
    print(f"Failed files: {result.failed_count}")

    for item in result.items:
        status = item.status.upper()
        message = f"[{status}] {item.source_path} -> {item.message}"
        if item.asset_id:
            message += f" (asset_id={item.asset_id})"
        print(message)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command in (None, "init"):
        run_init()
        return

    if args.command == "import":
        run_import(args.path, args.asset_type)
        return

    if args.command == "gui":
        gui_module = importlib.import_module("strepertory.gui_qt")
        gui_module.launch_gui()
        return

    parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
