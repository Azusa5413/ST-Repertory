from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from strepertory.models.enums import AssetType
from strepertory.models.imports import DetectionResult


IMAGE_SUFFIXES = {".png", ".webp"}
TEXT_SUFFIXES = {".txt", ".md", ".yaml", ".yml", ".json", ".js"}


def detect_asset(file_path: Path, override: AssetType | None = None) -> DetectionResult:
    if override is not None:
        return DetectionResult(
            asset_type=override,
            payload_format=file_path.suffix.lower().lstrip(".") or "unknown",
            title=file_path.stem,
            extracted_summary={"detection": "manual_override"},
        )

    suffix = file_path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return detect_image_asset(file_path)
    if suffix == ".json":
        return detect_json_asset(file_path)
    if suffix == ".js":
        return DetectionResult(
            asset_type=AssetType.METADATA_OVERRIDE,
            payload_format="js",
            title=file_path.stem,
            extracted_summary={
                "detection": "metadata_override_js",
                "confidence": "high",
            },
        )
    if suffix in TEXT_SUFFIXES:
        return detect_text_asset(file_path)
    return DetectionResult(
        asset_type=AssetType.UNKNOWN,
        payload_format=suffix.lstrip(".") or "unknown",
        title=file_path.stem,
        extracted_summary={"detection": "unknown_extension"},
    )


def detect_image_asset(file_path: Path) -> DetectionResult:
    return DetectionResult(
        asset_type=AssetType.CHARACTER_CARD,
        payload_format=file_path.suffix.lower().lstrip("."),
        title=file_path.stem,
        extracted_summary={"detection": "image_container", "confidence": "low"},
    )


def detect_json_asset(file_path: Path) -> DetectionResult:
    try:
        raw_text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raw_text = file_path.read_text(encoding="utf-8-sig")

    data = json.loads(raw_text)
    detected = classify_json_payload(file_path=file_path, data=data)
    extracted_summary = dict(detected.extracted_summary or {})
    extracted_summary.setdefault("top_level_type", type(data).__name__)
    return DetectionResult(
        asset_type=detected.asset_type,
        payload_format="json",
        title=detected.title,
        description=detected.description,
        scope=detected.scope,
        extracted_summary=extracted_summary,
    )


def detect_text_asset(file_path: Path) -> DetectionResult:
    return DetectionResult(
        asset_type=AssetType.UNKNOWN,
        payload_format=file_path.suffix.lower().lstrip(".") or "text",
        title=file_path.stem,
        extracted_summary={"detection": "plain_text_or_unsupported"},
    )


def classify_json_payload(file_path: Path, data: Any) -> DetectionResult:
    filename = file_path.stem
    lowered_name = filename.lower()

    if looks_like_character_card(data):
        title = extract_character_title(data) or filename
        return DetectionResult(
            asset_type=AssetType.CHARACTER_CARD,
            payload_format="json",
            title=title,
            description="Character card JSON",
            extracted_summary={
                "detection": "character_card_json",
                "has_character_book": bool(
                    get_nested(data, ["data", "character_book"])
                ),
            },
        )

    if looks_like_lorebook(data):
        title = extract_lorebook_title(data) or filename
        return DetectionResult(
            asset_type=AssetType.LOREBOOK,
            payload_format="json",
            title=title,
            description="Lorebook / world info JSON",
            extracted_summary={
                "detection": "lorebook_json",
                "entry_count": count_lorebook_entries(data),
            },
        )

    if looks_like_database_table_template(data, lowered_name):
        return DetectionResult(
            asset_type=AssetType.DATABASE_TABLE_TEMPLATE,
            payload_format="json",
            title=extract_generic_title(data) or filename,
            description="Database table template JSON",
            extracted_summary={"detection": "database_table_template_json"},
        )

    if looks_like_regex(data, lowered_name):
        return DetectionResult(
            asset_type=AssetType.REGEX,
            payload_format="json",
            title=extract_generic_title(data) or filename,
            description="Regex JSON",
            extracted_summary={"detection": "regex_json"},
        )

    if looks_like_beautify(data, lowered_name):
        return DetectionResult(
            asset_type=AssetType.BEAUTIFY,
            payload_format="json",
            title=extract_generic_title(data) or filename,
            description="Beautify / theme JSON",
            extracted_summary={"detection": "beautify_json"},
        )

    if looks_like_story_progress_preset(data, lowered_name):
        return DetectionResult(
            asset_type=AssetType.STORY_PROGRESS_PRESET,
            payload_format="json",
            title=extract_generic_title(data) or filename,
            description="Story progress preset JSON",
            extracted_summary={"detection": "story_progress_preset_json"},
        )

    if looks_like_preset(data, lowered_name):
        return DetectionResult(
            asset_type=AssetType.PRESET,
            payload_format="json",
            title=extract_generic_title(data) or filename,
            description="Preset JSON",
            extracted_summary={"detection": "preset_json"},
        )

    if looks_like_helper_script(data, lowered_name):
        return DetectionResult(
            asset_type=AssetType.HELPER_SCRIPT,
            payload_format="json",
            title=extract_generic_title(data) or filename,
            description="Tavern-Helper / JS-Slash-Runner JSON",
            scope=detect_scope(lowered_name, data),
            extracted_summary={"detection": "helper_script_json"},
        )

    return DetectionResult(
        asset_type=AssetType.UNKNOWN,
        payload_format="json",
        title=extract_generic_title(data) or filename,
        extracted_summary={"detection": "unknown_json"},
    )


def looks_like_character_card(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    if data.get("spec") == "chara_card_v2":
        return True
    nested = data.get("data")
    if not isinstance(nested, dict):
        return False
    card_keys = {
        "name",
        "description",
        "personality",
        "scenario",
        "first_mes",
        "mes_example",
    }
    return len(card_keys.intersection(nested.keys())) >= 3


def looks_like_lorebook(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    if isinstance(data.get("entries"), list):
        return True
    if isinstance(data.get("entries"), dict):
        return True
    if isinstance(data.get("world_info"), dict):
        return True
    return False


def looks_like_helper_script(data: Any, lowered_name: str) -> bool:
    if looks_like_preset(data, lowered_name):
        return False
    serialized = (
        json.dumps(data, ensure_ascii=False).lower()
        if isinstance(data, (dict, list))
        else str(data).lower()
    )
    helper_markers = ["slash", "script", "javascript", "helper", "tavern", "jsrunner"]
    if any(marker in lowered_name for marker in helper_markers):
        return True
    strong_keys = ["buttons", "slash", "javascript", "script", "jsrunner"]
    return sum(marker in serialized for marker in strong_keys) >= 2


def looks_like_preset(data: Any, lowered_name: str) -> bool:
    if "preset" in lowered_name:
        return True
    if not isinstance(data, dict):
        return False
    preset_markers = {
        "prompts",
        "prompt_order",
        "instruct",
        "temperature",
        "max_context",
        "frequency_penalty",
        "presence_penalty",
        "top_p",
    }
    return len(preset_markers.intersection(data.keys())) >= 2


def looks_like_story_progress_preset(data: Any, lowered_name: str) -> bool:
    if looks_like_regex(data, lowered_name):
        return False
    if any(
        marker in lowered_name
        for marker in ["剧情推进", "story-progress", "story_progress"]
    ):
        if isinstance(data, list):
            return any(
                isinstance(item, dict) and "promptGroup" in item for item in data
            )
        if isinstance(data, dict):
            return True
    if isinstance(data, list):
        return any(
            isinstance(item, dict)
            and isinstance(item.get("promptGroup"), list)
            and any(key in item for key in ("name", "promptGroup"))
            for item in data
        )
    if not isinstance(data, dict):
        return False
    markers = {
        "story_progress",
        "progress_steps",
        "stage_prompts",
        "event_triggers",
        "progress_rules",
        "promptGroup",
        "finalSystemDirective",
        "mainPrompt",
        "contextTurnCount",
        "loopSettings",
    }
    return len(markers.intersection(data.keys())) >= 2


def looks_like_database_table_template(data: Any, lowered_name: str) -> bool:
    if any(
        marker in lowered_name
        for marker in [
            "数据库",
            "table-template",
            "table_template",
            "db-template",
            "db_template",
        ]
    ):
        return True
    if not isinstance(data, dict):
        return False
    markers = {
        "columns",
        "schema",
        "table_name",
        "field_types",
        "primary_key",
        "rows_template",
    }
    return len(markers.intersection(data.keys())) >= 2


def looks_like_regex(data: Any, lowered_name: str) -> bool:
    if not isinstance(data, dict):
        return False
    explicit_keys = {
        "findRegex",
        "replaceString",
        "trimStrings",
        "runOnEdit",
        "substituteRegex",
        "markdownOnly",
        "promptOnly",
    }
    matched_keys = explicit_keys.intersection(data.keys())
    if "findRegex" in matched_keys and "replaceString" in matched_keys:
        return True
    if len(matched_keys) >= 3:
        return True
    lowered_keys = {str(key).lower() for key in data.keys()}
    if {"findregex", "replacestring"}.issubset(lowered_keys):
        return True
    return False


def looks_like_beautify(data: Any, lowered_name: str) -> bool:
    if not isinstance(data, dict):
        return False
    if any(marker in lowered_name for marker in ["dark_", "light_", "theme", "美化"]):
        return True
    beautify_markers = {
        "main_text_color",
        "blur_tint_color",
        "chat_tint_color",
        "font_scale",
        "avatar_style",
        "chat_width",
        "custom_css",
    }
    return len(beautify_markers.intersection(data.keys())) >= 3


def detect_scope(lowered_name: str, data: Any) -> str | None:
    if "preset" in lowered_name or "预设" in lowered_name:
        return "preset"
    if isinstance(data, dict):
        serialized = json.dumps(data, ensure_ascii=False).lower()
        for scope in ("preset",):
            if scope in serialized:
                return scope
    return None


def extract_character_title(data: dict[str, Any]) -> str | None:
    nested = data.get("data") if isinstance(data.get("data"), dict) else data
    if isinstance(nested, dict):
        name = nested.get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return None


def extract_lorebook_title(data: dict[str, Any]) -> str | None:
    for key in ("name", "title", "world_info_name"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def extract_generic_title(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None
    for key in ("name", "title", "display_name"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def count_lorebook_entries(data: dict[str, Any]) -> int | None:
    entries = data.get("entries")
    if isinstance(entries, list):
        return len(entries)
    if isinstance(entries, dict):
        return len(entries)
    world_info = data.get("world_info")
    if isinstance(world_info, dict):
        nested_entries = world_info.get("entries")
        if isinstance(nested_entries, list):
            return len(nested_entries)
        if isinstance(nested_entries, dict):
            return len(nested_entries)
    return None


def get_nested(data: dict[str, Any], path: list[str]) -> Any:
    current: Any = data
    for segment in path:
        if not isinstance(current, dict):
            return None
        current = current.get(segment)
    return current
