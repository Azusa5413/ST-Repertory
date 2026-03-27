from __future__ import annotations

from dataclasses import dataclass

from strepertory.config import AppPaths
from strepertory.db.connection import create_connection
from strepertory.db.schema import INDEX_STATEMENTS, SCHEMA_STATEMENTS


@dataclass(slots=True, frozen=True)
class BootstrapResult:
    created_directories: list[str]
    database_path: str
    schema_initialized: bool


def ensure_app_directories(paths: AppPaths) -> list[str]:
    created_directories: list[str] = []
    required_dirs = [
        paths.data_dir,
        paths.assets_dir,
        *paths.asset_type_dirs.values(),
        paths.exports_dir,
        paths.previews_dir,
        paths.db_dir,
    ]

    for directory in required_dirs:
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            created_directories.append(str(directory))

    return created_directories


def initialize_database(paths: AppPaths) -> None:
    with create_connection(paths.db_path) as connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
        for statement in INDEX_STATEMENTS:
            connection.execute(statement)
        connection.commit()


def bootstrap_application(paths: AppPaths) -> BootstrapResult:
    created_directories = ensure_app_directories(paths)
    initialize_database(paths)
    return BootstrapResult(
        created_directories=created_directories,
        database_path=str(paths.db_path),
        schema_initialized=True,
    )
