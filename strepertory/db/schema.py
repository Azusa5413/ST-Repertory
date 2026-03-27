from __future__ import annotations

SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS assets (
        id TEXT PRIMARY KEY,
        asset_type TEXT NOT NULL,
        title TEXT NOT NULL,
        slug TEXT UNIQUE,
        description TEXT,
        payload_format TEXT,
        source_path TEXT,
        stored_path TEXT NOT NULL,
        preview_path TEXT,
        source_hash TEXT,
        external_identity TEXT,
        author TEXT,
        version TEXT,
        scope TEXT,
        status TEXT NOT NULL DEFAULT 'active',
        imported_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        exported_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS asset_payloads (
        asset_id TEXT PRIMARY KEY,
        raw_payload TEXT,
        extracted_summary_json TEXT,
        FOREIGN KEY (asset_id) REFERENCES assets(id)
    )
    """,
)


INDEX_STATEMENTS: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(asset_type)",
    "CREATE INDEX IF NOT EXISTS idx_assets_status ON assets(status)",
    "CREATE INDEX IF NOT EXISTS idx_assets_hash ON assets(source_hash)",
)
