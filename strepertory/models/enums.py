from __future__ import annotations

from enum import StrEnum


class AssetType(StrEnum):
    CHARACTER_CARD = "character_card"
    LOREBOOK = "lorebook"
    HELPER_SCRIPT = "helper_script"
    PRESET = "preset"
    STORY_PROGRESS_PRESET = "story_progress_preset"
    DATABASE_TABLE_TEMPLATE = "database_table_template"
    REGEX = "regex"
    BEAUTIFY = "beautify"
    METADATA_OVERRIDE = "metadata_override"
    UNKNOWN = "unknown"


class Status(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    CONFLICT = "conflict"
