from __future__ import annotations

import json
import sqlite3
from datetime import datetime, UTC
from pathlib import Path

from ..db.connection import create_connection
from ..models.enums import AssetType, Status
from ..models.imports import DetectionResult
from ..models.records import AssetDetailsRecord, AssetRecord


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class CatalogRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def get_asset_by_hash(self, source_hash: str) -> sqlite3.Row | None:
        with create_connection(self.db_path) as connection:
            return connection.execute(
                "SELECT * FROM assets WHERE source_hash = ? LIMIT 1",
                (source_hash,),
            ).fetchone()

    def list_assets(self, limit: int = 200) -> list[AssetRecord]:
        with create_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM assets
                ORDER BY datetime(imported_at) DESC, imported_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._asset_from_row(row) for row in rows]

    def search_assets(
        self,
        query: str,
        limit: int = 200,
    ) -> list[AssetRecord]:
        normalized_query = f"%{query.strip()}%"
        with create_connection(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM assets
                WHERE title LIKE ? OR asset_type LIKE ? OR source_path LIKE ?
                ORDER BY datetime(imported_at) DESC, imported_at DESC
                LIMIT ?
                """,
                (normalized_query, normalized_query, normalized_query, limit),
            ).fetchall()
        return [self._asset_from_row(row) for row in rows]

    def get_asset(self, asset_id: str) -> AssetRecord | None:
        with create_connection(self.db_path) as connection:
            row = connection.execute(
                "SELECT * FROM assets WHERE id = ? LIMIT 1",
                (asset_id,),
            ).fetchone()
        if row is None:
            return None
        return self._asset_from_row(row)

    def get_asset_details(self, asset_id: str) -> AssetDetailsRecord | None:
        with create_connection(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT
                    assets.*, 
                    asset_payloads.raw_payload,
                    asset_payloads.extracted_summary_json
                FROM assets
                LEFT JOIN asset_payloads ON asset_payloads.asset_id = assets.id
                WHERE assets.id = ?
                LIMIT 1
                """,
                (asset_id,),
            ).fetchone()
        if row is None:
            return None

        summary_raw = row["extracted_summary_json"]
        extracted_summary = {}
        if summary_raw:
            loaded = json.loads(summary_raw)
            if isinstance(loaded, dict):
                extracted_summary = loaded

        return AssetDetailsRecord(
            asset=self._asset_from_row(row),
            raw_payload=row["raw_payload"],
            extracted_summary=extracted_summary,
        )

    def delete_asset_records(self, asset_id: str) -> None:
        with create_connection(self.db_path) as connection:
            connection.execute(
                "DELETE FROM asset_payloads WHERE asset_id = ?",
                (asset_id,),
            )
            connection.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
            connection.commit()

    def insert_asset(
        self,
        *,
        asset_id: str,
        detection: DetectionResult,
        source_path: Path,
        stored_path: Path,
        source_hash: str,
    ) -> None:
        now = utc_now_iso()
        with create_connection(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO assets (
                    id, asset_type, title, slug, description, payload_format,
                    source_path, stored_path, source_hash, scope, status,
                    imported_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    asset_id,
                    detection.asset_type.value,
                    detection.title,
                    None,
                    detection.description,
                    detection.payload_format,
                    str(source_path),
                    str(stored_path),
                    source_hash,
                    detection.scope,
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO asset_payloads (asset_id, raw_payload, extracted_summary_json)
                VALUES (?, ?, ?)
                """,
                (
                    asset_id,
                    read_payload_text(source_path),
                    json.dumps(detection.extracted_summary or {}, ensure_ascii=False),
                ),
            )
            connection.commit()

    def update_asset_after_review(
        self,
        *,
        asset_id: str,
        detection: DetectionResult,
        source_path: Path,
        stored_path: Path,
        source_hash: str,
    ) -> None:
        now = utc_now_iso()
        with create_connection(self.db_path) as connection:
            connection.execute(
                """
                UPDATE assets
                SET asset_type = ?,
                    title = ?,
                    description = ?,
                    payload_format = ?,
                    source_path = ?,
                    stored_path = ?,
                    source_hash = ?,
                    scope = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    detection.asset_type.value,
                    detection.title,
                    detection.description,
                    detection.payload_format,
                    str(source_path),
                    str(stored_path),
                    source_hash,
                    detection.scope,
                    now,
                    asset_id,
                ),
            )
            connection.execute(
                """
                INSERT INTO asset_payloads (asset_id, raw_payload, extracted_summary_json)
                VALUES (?, ?, ?)
                ON CONFLICT(asset_id) DO UPDATE SET
                    raw_payload = excluded.raw_payload,
                    extracted_summary_json = excluded.extracted_summary_json
                """,
                (
                    asset_id,
                    read_payload_text(source_path) or read_payload_text(stored_path),
                    json.dumps(detection.extracted_summary or {}, ensure_ascii=False),
                ),
            )
            connection.commit()

    def rename_asset(
        self,
        *,
        asset_id: str,
        new_title: str,
        stored_path: Path,
    ) -> None:
        now = utc_now_iso()
        with create_connection(self.db_path) as connection:
            connection.execute(
                """
                UPDATE assets
                SET title = ?,
                    stored_path = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (new_title, str(stored_path), now, asset_id),
            )
            connection.commit()

    @staticmethod
    def _asset_from_row(row: sqlite3.Row) -> AssetRecord:
        return AssetRecord(
            id=row["id"],
            asset_type=normalize_asset_type(row["asset_type"]),
            title=row["title"],
            stored_path=row["stored_path"],
            imported_at=datetime.fromisoformat(row["imported_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            slug=row["slug"],
            description=row["description"],
            payload_format=row["payload_format"],
            source_path=row["source_path"],
            preview_path=row["preview_path"],
            source_hash=row["source_hash"],
            external_identity=row["external_identity"],
            author=row["author"],
            version=row["version"],
            scope=row["scope"],
            status=Status(row["status"]),
            exported_at=datetime.fromisoformat(row["exported_at"])
            if row["exported_at"]
            else None,
        )


def read_payload_text(source_path: Path) -> str | None:
    suffix = source_path.suffix.lower()
    if suffix in {".json", ".txt", ".md", ".yaml", ".yml", ".js"}:
        try:
            return source_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return source_path.read_text(encoding="utf-8-sig")
    return None


def normalize_asset_type(raw_value: str) -> AssetType:
    legacy_map = {
        "regex_global": AssetType.REGEX,
        "regex_character": AssetType.REGEX,
    }
    if raw_value in legacy_map:
        return legacy_map[raw_value]
    return AssetType(raw_value)
