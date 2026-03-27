from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path


def file_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    return normalized.strip("-") or "untitled"


def new_asset_id() -> str:
    return f"ast_{uuid.uuid4().hex[:12]}"


def new_import_id() -> str:
    return f"imp_{uuid.uuid4().hex[:12]}"


def new_group_id() -> str:
    return f"grp_{uuid.uuid4().hex[:12]}"
