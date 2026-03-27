from __future__ import annotations

from dataclasses import dataclass

from .models.enums import AssetType


@dataclass(frozen=True, slots=True)
class AssetTypeDefinition:
    asset_type: AssetType
    label: str
    folder: str
    detection_label: str | None = None
    reviewable: bool = True
    order: int = 0


ASSET_TYPE_DEFINITIONS: tuple[AssetTypeDefinition, ...] = (
    AssetTypeDefinition(
        AssetType.CHARACTER_CARD,
        "角色卡",
        "character_cards",
        "角色卡 JSON/图片特征",
        True,
        10,
    ),
    AssetTypeDefinition(
        AssetType.LOREBOOK, "世界书", "lorebooks", "世界书 JSON 特征", True, 20
    ),
    AssetTypeDefinition(
        AssetType.PRESET, "预设", "presets", "预设 JSON 特征", True, 30
    ),
    AssetTypeDefinition(
        AssetType.STORY_PROGRESS_PRESET,
        "剧情推进预设",
        "story_progress_presets",
        "剧情推进预设 JSON 特征",
        True,
        40,
    ),
    AssetTypeDefinition(
        AssetType.DATABASE_TABLE_TEMPLATE,
        "数据库表格模板",
        "database_table_templates",
        "数据库表格模板 JSON 特征",
        True,
        50,
    ),
    AssetTypeDefinition(
        AssetType.HELPER_SCRIPT,
        "辅助脚本",
        "helper_scripts",
        "辅助脚本 JSON 特征",
        True,
        60,
    ),
    AssetTypeDefinition(AssetType.REGEX, "正则", "regex", "正则 JSON 特征", True, 70),
    AssetTypeDefinition(
        AssetType.BEAUTIFY, "美化", "beautify", "美化 JSON 特征", True, 80
    ),
    AssetTypeDefinition(
        AssetType.METADATA_OVERRIDE,
        "元数据覆盖",
        "metadata_overrides",
        "元数据覆盖 JS 特征",
        True,
        90,
    ),
    AssetTypeDefinition(
        AssetType.UNKNOWN, "待复核", "unknown", "待复核 / 未识别", False, 999
    ),
)

ASSET_TYPE_REGISTRY: dict[AssetType, AssetTypeDefinition] = {
    item.asset_type: item for item in ASSET_TYPE_DEFINITIONS
}

ASSET_TYPE_LABELS: dict[AssetType, str] = {
    item.asset_type: item.label for item in ASSET_TYPE_DEFINITIONS
}

ASSET_TYPE_FOLDERS: dict[AssetType, str] = {
    item.asset_type: item.folder for item in ASSET_TYPE_DEFINITIONS
}

ASSET_TYPE_ORDER: list[AssetType] = [item.asset_type for item in ASSET_TYPE_DEFINITIONS]

DETECTION_LABELS_FROM_TYPES: dict[str, str] = {
    "character_card_json": "角色卡 JSON 特征",
    "image_container": "图片容器识别",
    "lorebook_json": "世界书 JSON 特征",
    "preset_json": "预设 JSON 特征",
    "story_progress_preset_json": "剧情推进预设 JSON 特征",
    "database_table_template_json": "数据库表格模板 JSON 特征",
    "helper_script_json": "辅助脚本 JSON 特征",
    "regex_json": "正则 JSON 特征",
    "beautify_json": "美化 JSON 特征",
    "metadata_override_js": "元数据覆盖 JS 特征",
    "manual_override": "手动指定类型",
    "unknown_json": "未识别 JSON 结构",
    "plain_text_or_unsupported": "纯文本或暂不支持格式",
    "unknown_extension": "未知文件扩展名",
}
