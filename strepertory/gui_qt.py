from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QHeaderView,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .asset_types import (
    ASSET_TYPE_FOLDERS,
    ASSET_TYPE_LABELS,
    ASSET_TYPE_ORDER,
    DETECTION_LABELS_FROM_TYPES,
)
from . import APP_AUTHOR, APP_NAME, APP_VERSION
from .config import get_app_paths
from .models.enums import AssetType
from .models.imports import ImportItemResult, ImportRequest, ImportResult
from .models.records import AssetDetailsRecord, AssetRecord
from .services.bootstrap import bootstrap_application
from .services.exporter import export_assets
from .services.importer import (
    delete_asset,
    import_path,
    rename_asset,
    retype_asset,
    review_unknown_asset,
)
from .services.repository import CatalogRepository


ALL_TYPES_LABEL = "全部类型"
AUTO_DETECT_LABEL = "自动识别"
STATUS_LABELS = {"imported": "已导入", "skipped": "已跳过", "failed": "失败"}
CONFIDENCE_LABELS = {"low": "低", "medium": "中", "high": "高"}


class TavernAssetLibraryWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.paths = get_app_paths()
        bootstrap_application(self.paths)
        self.repository = CatalogRepository(self.paths.db_path)

        self.current_asset_id: str | None = None
        self.asset_row_map: list[str] = []
        self.current_preview_pixmap: QPixmap | None = None

        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        icon_path = self.paths.root / "assets" / "app_icon.svg"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(1600, 980)
        self.setMinimumSize(1280, 860)
        self._apply_style_system()

        self.import_type_labels = [AUTO_DETECT_LABEL, *self._asset_type_labels()]
        self.type_filter_labels = [ALL_TYPES_LABEL, *self._asset_type_labels()]
        self.manual_type_labels = [
            self._asset_type_label(asset_type)
            for asset_type in ASSET_TYPE_ORDER
            if asset_type != AssetType.UNKNOWN
        ]
        self.import_type_value = AUTO_DETECT_LABEL
        self.type_filter_value = ALL_TYPES_LABEL
        self.manual_type_value = (
            self.manual_type_labels[0] if self.manual_type_labels else ""
        )

        self._build_ui()
        self.refresh_assets()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(14)
        self.setCentralWidget(root)

        header_box = QGroupBox(f"{APP_NAME} 控制台")
        header_box.setObjectName("HeroBox")
        header_layout = QVBoxLayout(header_box)
        header_layout.setSpacing(10)
        header_desc = QLabel(
            "以“资源类型 + 受管目录”为核心来整理素材；导入、筛选、批量管理、详情查看与导出都在同一工作台内完成。"
        )
        header_desc.setWordWrap(True)
        header_desc.setFont(QFont("Microsoft YaHei UI", 10))
        self.status_label = QLabel("就绪")
        self.summary_label = QLabel("")
        self.meta_label = QLabel(f"版本：{APP_VERSION}    作者：{APP_AUTHOR}")
        self.status_label.setStyleSheet("color: #355b52; font-weight: 600;")
        self.summary_label.setStyleSheet("color: #6e6255;")
        self.meta_label.setStyleSheet("color: #8a7f72; font-size: 11px;")
        header_layout.addWidget(header_desc)
        header_layout.addWidget(self.meta_label)
        header_layout.addWidget(self.status_label)
        header_layout.addWidget(self.summary_label)
        root_layout.addWidget(header_box)

        import_box = QGroupBox("导入")
        import_box.setObjectName("ToolbarBox")
        import_layout = QHBoxLayout(import_box)
        import_layout.setContentsMargins(14, 14, 14, 14)
        import_controls = QHBoxLayout()
        import_controls.setSpacing(10)
        import_controls.addWidget(QLabel("导入类型"))
        self.import_type_button = self._create_selector_button(self.import_type_value)
        self._attach_selector_menu(
            self.import_type_button,
            self.import_type_labels,
            self._set_import_type,
        )
        import_controls.addWidget(self.import_type_button)
        self.import_file_button = QPushButton("导入文件")
        self.import_file_button.clicked.connect(self.import_file)
        self.import_file_button.setMinimumHeight(38)
        self.import_dir_button = QPushButton("导入文件夹")
        self.import_dir_button.clicked.connect(self.import_directory)
        self.import_dir_button.setMinimumHeight(38)
        import_controls.addWidget(self.import_file_button)
        import_controls.addWidget(self.import_dir_button)
        import_controls.addStretch(1)
        import_layout.addLayout(import_controls)
        root_layout.addWidget(import_box, 0)

        workspace_splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(workspace_splitter, 7)
        workspace_splitter.setChildrenCollapsible(False)

        left_box = QWidget()
        left_layout = QVBoxLayout(left_box)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        filter_box = QGroupBox("资产浏览")
        filter_box.setObjectName("PanelBox")
        filter_layout = QGridLayout(filter_box)
        filter_layout.setHorizontalSpacing(12)
        filter_layout.setVerticalSpacing(10)
        filter_layout.addWidget(QLabel("搜索"), 0, 0)
        self.search_edit = QLineEdit()
        self.search_edit.returnPressed.connect(self.refresh_assets)
        self.search_edit.setMinimumHeight(38)
        filter_layout.addWidget(self.search_edit, 0, 1)

        filter_layout.addWidget(QLabel("类型"), 0, 2)
        self.type_filter_button = self._create_selector_button(self.type_filter_value)
        self._attach_selector_menu(
            self.type_filter_button,
            self.type_filter_labels,
            self._set_type_filter,
        )
        filter_layout.addWidget(self.type_filter_button, 0, 3)

        type_hint = QLabel("按类型筛选与浏览资产。")
        type_hint.setWordWrap(True)
        filter_layout.addWidget(type_hint, 1, 0, 1, 2)

        self.filter_button = QPushButton("筛选")
        self.filter_button.clicked.connect(self.refresh_assets)
        self.filter_button.setObjectName("SecondaryButton")
        self.filter_button.setMinimumHeight(38)
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.refresh_assets)
        self.refresh_button.setObjectName("SecondaryButton")
        self.refresh_button.setMinimumHeight(38)
        self.export_button = QPushButton("导出选中资产")
        self.export_button.clicked.connect(self.export_selected_assets)
        self.export_button.setObjectName("PrimaryButton")
        self.export_button.setMinimumHeight(38)
        self.select_all_button = QPushButton("全选")
        self.select_all_button.clicked.connect(self.select_all_assets)
        self.select_all_button.setObjectName("SecondaryButton")
        self.select_all_button.setMinimumHeight(38)
        self.clear_selection_button = QPushButton("清空选择")
        self.clear_selection_button.clicked.connect(self.clear_asset_selection)
        self.clear_selection_button.setObjectName("GhostButton")
        self.clear_selection_button.setMinimumHeight(38)
        self.delete_button = QPushButton("删除选中资产")
        self.delete_button.clicked.connect(self.delete_selected_assets)
        self.delete_button.setObjectName("DangerButton")
        self.delete_button.setMinimumHeight(38)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        for button in (
            self.filter_button,
            self.refresh_button,
            self.export_button,
            self.select_all_button,
            self.clear_selection_button,
            self.delete_button,
        ):
            action_row.addWidget(button)
        action_row.addStretch(1)
        filter_layout.addLayout(action_row, 1, 2, 1, 2)
        left_layout.addWidget(filter_box)

        summary_box = QGroupBox("分类摘要")
        summary_box.setObjectName("PanelBox")
        summary_layout = QVBoxLayout(summary_box)
        self.type_summary_label = QLabel("")
        self.type_summary_label.setWordWrap(True)
        self.folder_summary_label = QLabel("")
        self.folder_summary_label.setWordWrap(True)
        summary_layout.addWidget(self.type_summary_label)
        summary_layout.addWidget(self.folder_summary_label)
        left_layout.addWidget(summary_box)

        self.assets_table = QTableWidget(0, 5)
        self.assets_table.setObjectName("AssetsTable")
        self.assets_table.setHorizontalHeaderLabels(
            ["批量", "标题", "类型", "格式", "分类文件夹"]
        )
        self.assets_table.setSelectionBehavior(
            self.assets_table.SelectionBehavior.SelectRows
        )
        self.assets_table.setSelectionMode(
            self.assets_table.SelectionMode.SingleSelection
        )
        self.assets_table.setEditTriggers(self.assets_table.EditTrigger.NoEditTriggers)
        self.assets_table.verticalHeader().setVisible(False)
        header = self.assets_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.assets_table.setColumnWidth(0, 58)
        self.assets_table.itemSelectionChanged.connect(self._handle_asset_selection)
        self.assets_table.cellClicked.connect(self._handle_asset_cell_clicked)
        self.assets_table.cellDoubleClicked.connect(
            self._handle_asset_cell_double_clicked
        )
        self.assets_table.setAlternatingRowColors(True)
        self.assets_table.setSortingEnabled(True)
        left_layout.addWidget(self.assets_table, 1)

        workspace_splitter.addWidget(left_box)

        right_splitter = QSplitter(Qt.Orientation.Vertical)
        workspace_splitter.addWidget(right_splitter)
        workspace_splitter.setStretchFactor(0, 6)
        workspace_splitter.setStretchFactor(1, 5)
        right_splitter.setChildrenCollapsible(False)

        detail_box = QGroupBox("资产详情")
        detail_box.setObjectName("PanelBox")
        detail_layout = QVBoxLayout(detail_box)
        detail_layout.setContentsMargins(14, 14, 14, 14)
        self.detail_summary_label = QLabel("请选择一个资产以查看详情。")
        self.detail_summary_label.setWordWrap(True)
        self.detail_summary_label.setStyleSheet("font-weight: 600;")
        detail_layout.addWidget(self.detail_summary_label)
        self.detail_text = QPlainTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setPlaceholderText(
            "选中资产后，这里会显示基础信息、检测摘要和原始文本预览。"
        )
        detail_layout.addWidget(self.detail_text, 1)
        right_splitter.addWidget(detail_box)

        lower_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.addWidget(lower_splitter)
        right_splitter.setStretchFactor(0, 5)
        right_splitter.setStretchFactor(1, 4)

        preview_box = QGroupBox("角色卡预览")
        preview_box.setObjectName("PanelBox")
        preview_layout = QVBoxLayout(preview_box)
        preview_layout.setContentsMargins(14, 14, 14, 14)
        self.preview_hint_label = QLabel("当前资产没有可显示的角色卡图片预览。")
        self.preview_hint_label.setWordWrap(True)
        self.preview_label = QLabel()
        self.preview_label.setObjectName("PreviewCanvas")
        self.preview_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        self.preview_label.setMinimumHeight(180)
        preview_layout.addWidget(self.preview_hint_label)
        preview_layout.addWidget(self.preview_label, 1)
        lower_splitter.addWidget(preview_box)

        ops_box = QGroupBox("资产操作")
        ops_box.setObjectName("PanelBox")
        ops_layout = QVBoxLayout(ops_box)
        ops_layout.setContentsMargins(14, 14, 14, 14)
        ops_layout.setSpacing(12)

        self.manual_hint_label = QLabel(
            "请先在资产库中选中一个资产，再执行手动改类型或复核。"
        )
        self.manual_hint_label.setWordWrap(True)
        ops_layout.addWidget(self.manual_hint_label)

        retype_layout = QHBoxLayout()
        retype_layout.addWidget(QLabel("改为类型"))
        self.manual_type_button = self._create_selector_button(self.manual_type_value)
        self._attach_selector_menu(
            self.manual_type_button,
            self.manual_type_labels,
            self._set_manual_type,
        )
        retype_layout.addWidget(self.manual_type_button)
        self.retype_button = QPushButton("执行手动改类型")
        self.retype_button.clicked.connect(self.retype_selected_asset)
        self.retype_button.setObjectName("SecondaryButton")
        self.retype_button.setMinimumHeight(38)
        retype_layout.addWidget(self.retype_button)
        self.rename_button = QPushButton("重命名资产")
        self.rename_button.clicked.connect(self.rename_selected_asset)
        self.rename_button.setObjectName("SecondaryButton")
        self.rename_button.setMinimumHeight(38)
        retype_layout.addWidget(self.rename_button)
        retype_layout.addStretch(1)
        ops_layout.addLayout(retype_layout)

        ops_layout.addStretch(1)
        lower_splitter.addWidget(ops_box)

        workspace_splitter.setSizes([940, 660])
        right_splitter.setSizes([520, 420])
        lower_splitter.setSizes([240, 180])

        self._update_action_states()

    def _apply_style_system(self) -> None:
        self.setStyleSheet(
            """
            QWidget#Root {
                background: #f4f1ea;
            }
            QGroupBox {
                background: #fbf9f4;
                border: 1px solid #d8d1c5;
                border-radius: 12px;
                margin-top: 12px;
                padding-top: 10px;
                color: #2f2923;
                font-size: 12px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 6px;
                color: #3a645a;
            }
            QGroupBox#HeroBox {
                background: #f7f5ef;
                border: 1px solid #cfc6b8;
            }
            QGroupBox#ToolbarBox {
                background: #f8f6f1;
                border: 1px solid #ddd5ca;
            }
            QGroupBox#PanelBox {
                background: #fffdfa;
            }
            QLabel {
                color: #2f2923;
            }
            QGroupBox#ToolbarBox QLabel,
            QGroupBox#PanelBox QLabel {
                color: #5d544a;
                font-weight: 600;
            }
            QLineEdit, QPlainTextEdit {
                background: #fffdfa;
                border: 1px solid #d8d1c5;
                border-radius: 19px;
                padding: 8px 10px;
                color: #2f2923;
                selection-background-color: #9fc5ba;
                selection-color: #1f1a16;
            }
            QLineEdit:focus, QPlainTextEdit:focus {
                border: 1px solid #5e8b80;
            }
            QPushButton#SelectorButton {
                background: rgba(255, 253, 250, 0.92);
                color: #2f2923;
                border: 1px solid #ddd5ca;
                border-radius: 19px;
                padding: 8px 30px 8px 16px;
                text-align: center;
                font-weight: 500;
            }
            QPushButton#SelectorButton:hover {
                background: rgba(255, 253, 250, 0.98);
                border: 1px solid #d3cabd;
            }
            QPushButton#SelectorButton:pressed {
                background: #f4efe7;
                border: 1px solid #cfc6b8;
            }
            QPushButton#SelectorButton::menu-indicator {
                subcontrol-origin: padding;
                subcontrol-position: right center;
                right: 12px;
                width: 12px;
                height: 12px;
            }
            QPushButton {
                background: #ece7dd;
                color: #2f2923;
                border: 1px solid #d4cbbd;
                border-radius: 10px;
                padding: 8px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #e6e0d4;
            }
            QPushButton:pressed {
                background: #ddd5c7;
            }
            QPushButton#PrimaryButton {
                background: #3f6f65;
                color: #ffffff;
                border: 1px solid #355c54;
            }
            QPushButton#PrimaryButton:hover {
                background: #4a7e73;
            }
            QPushButton#DangerButton {
                background: #8f5757;
                color: #ffffff;
                border: 1px solid #774545;
            }
            QPushButton#DangerButton:hover {
                background: #9d6262;
            }
            QPushButton#GhostButton {
                background: #f8f6f1;
                border: 1px dashed #cdbfaa;
            }
            QPushButton:disabled {
                background: #efebe3;
                color: #9c9387;
                border: 1px solid #e2dbcf;
            }
            QTableWidget#AssetsTable {
                background: #fffdfa;
                alternate-background-color: #f7f2ea;
                border: 1px solid #d8d1c5;
                border-radius: 12px;
                gridline-color: #ece4d8;
                selection-background-color: #d7e3f2;
                selection-color: #1f1a16;
                outline: none;
            }
            QTableWidget#AssetsTable::item {
                padding: 6px 8px;
            }
            QTableWidget::indicator {
                width: 18px;
                height: 18px;
            }
            QHeaderView::section {
                background: #efe9df;
                color: #3d352e;
                border: none;
                border-right: 1px solid #ddd5ca;
                border-bottom: 1px solid #d8d1c5;
                padding: 8px 10px;
                font-weight: 700;
                min-height: 34px;
            }
            QHeaderView::section:first {
                border-top-left-radius: 10px;
                padding-left: 12px;
            }
            QHeaderView::section:last {
                border-top-right-radius: 10px;
                border-right: none;
            }
            QSplitter::handle {
                background: #ddd5ca;
                margin: 2px;
                border-radius: 2px;
            }
            QSplitter::handle:hover {
                background: #a8c3bc;
            }
            QLabel#PreviewCanvas {
                background: #fffdfa;
                border: 1px solid #d8d1c5;
                border-radius: 12px;
                padding: 10px;
            }
            """
        )

    def _asset_type_label(self, asset_type: AssetType) -> str:
        return ASSET_TYPE_LABELS.get(asset_type, asset_type.value)

    def _asset_type_labels(self) -> list[str]:
        return [self._asset_type_label(asset_type) for asset_type in ASSET_TYPE_ORDER]

    def _create_selector_button(self, text: str) -> QPushButton:
        button = QPushButton(self._format_selector_label(text))
        button.setObjectName("SelectorButton")
        button.setMinimumHeight(38)
        button.setMinimumWidth(196)
        return button

    def _format_selector_label(self, text: str) -> str:
        return text

    def _attach_selector_menu(
        self,
        button: QPushButton,
        options: list[str],
        setter,
    ) -> None:
        menu = QMenu(button)
        menu.setStyleSheet(
            """
            QMenu {
                background: #fffdfa;
                border: 1px solid #d8d1c5;
                border-radius: 14px;
                padding: 6px;
            }
            QMenu::item {
                padding: 10px 14px;
                border-radius: 10px;
            }
            QMenu::item:selected {
                background: #dde8f5;
                color: #1f1a16;
            }
            """
        )
        for option in options:
            action = menu.addAction(option)
            action.triggered.connect(lambda checked=False, value=option: setter(value))
        button.setMenu(menu)

    def _set_import_type(self, label: str) -> None:
        self.import_type_value = label
        self.import_type_button.setText(self._format_selector_label(label))

    def _set_type_filter(self, label: str) -> None:
        self.type_filter_value = label
        self.type_filter_button.setText(self._format_selector_label(label))
        self.refresh_assets()

    def _set_manual_type(self, label: str) -> None:
        self.manual_type_value = label
        self.manual_type_button.setText(self._format_selector_label(label))

    def _label_to_asset_type(self, label: str) -> AssetType:
        if label == AUTO_DETECT_LABEL:
            return AssetType.UNKNOWN
        for asset_type, asset_label in ASSET_TYPE_LABELS.items():
            if asset_label == label:
                return asset_type
        return AssetType.UNKNOWN

    def _resolve_override(self) -> AssetType | None:
        label = self.import_type_value
        if label == AUTO_DETECT_LABEL:
            return None
        asset_type = self._label_to_asset_type(label)
        return None if asset_type == AssetType.UNKNOWN else asset_type

    def _resolve_type_filter(self) -> AssetType | None:
        label = self.type_filter_value
        if label == ALL_TYPES_LABEL:
            return None
        return self._label_to_asset_type(label)

    def refresh_assets(self) -> None:
        query = self.search_edit.text().strip()
        assets = (
            self.repository.search_assets(query=query)
            if query
            else self.repository.list_assets()
        )
        filtered_type = self._resolve_type_filter()
        if filtered_type is not None:
            assets = [asset for asset in assets if asset.asset_type == filtered_type]
        self._populate_assets(assets)

    def _populate_assets(self, assets: list[AssetRecord]) -> None:
        sorting_enabled = self.assets_table.isSortingEnabled()
        if sorting_enabled:
            self.assets_table.setSortingEnabled(False)
        self.assets_table.blockSignals(True)
        self.assets_table.setRowCount(0)
        self.asset_row_map = []
        for asset in assets:
            row = self.assets_table.rowCount()
            self.assets_table.insertRow(row)
            checkbox_item = QTableWidgetItem("○")
            checkbox_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            )
            checkbox_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            checkbox_item.setData(Qt.ItemDataRole.UserRole, asset.id)
            checkbox_item.setData(Qt.ItemDataRole.UserRole + 1, False)
            checkbox_item.setFont(QFont("Microsoft YaHei UI", 16, QFont.Weight.Bold))
            self.assets_table.setItem(row, 0, checkbox_item)
            values = [
                asset.title,
                self._asset_type_label(asset.asset_type),
                (asset.payload_format or "—").upper(),
                self._folder_label_for_asset(asset),
            ]
            for column, value in enumerate(values, start=1):
                item = QTableWidgetItem(value)
                if column == 1:
                    item.setData(Qt.ItemDataRole.UserRole, asset.id)
                self.assets_table.setItem(row, column, item)
            self.asset_row_map.append(asset.id)

        self.assets_table.blockSignals(False)

        if sorting_enabled:
            self.assets_table.setSortingEnabled(True)

        self._apply_row_visuals()
        self._update_type_and_folder_summary(assets)
        self._update_status()
        self._update_action_states()
        if self.current_asset_id and self._select_row_by_asset_id(
            self.current_asset_id
        ):
            self._load_asset_details(self.current_asset_id)
        else:
            self.current_asset_id = None
            self._clear_asset_details()

    def _selected_asset_ids(self) -> list[str]:
        asset_ids: list[str] = []
        for row in range(self.assets_table.rowCount()):
            item = self.assets_table.item(row, 0)
            if item is None:
                continue
            if not bool(item.data(Qt.ItemDataRole.UserRole + 1)):
                continue
            asset_id = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(asset_id, str):
                asset_ids.append(asset_id)
        return asset_ids

    def _select_row_by_asset_id(self, asset_id: str) -> bool:
        for row in range(self.assets_table.rowCount()):
            item = self.assets_table.item(row, 1)
            if item is None:
                continue
            if item.data(Qt.ItemDataRole.UserRole) == asset_id:
                self.assets_table.selectRow(row)
                return True
        return False

    def _handle_asset_cell_clicked(self, row: int, column: int) -> None:
        if column != 0:
            return
        item = self.assets_table.item(row, 0)
        if item is None:
            return
        checked = bool(item.data(Qt.ItemDataRole.UserRole + 1))
        sorting_enabled = self.assets_table.isSortingEnabled()
        if sorting_enabled:
            self.assets_table.setSortingEnabled(False)
        self._set_batch_mark(item, not checked)
        if sorting_enabled:
            self.assets_table.setSortingEnabled(True)
        if self.current_asset_id:
            self._select_row_by_asset_id(self.current_asset_id)
        else:
            self.assets_table.clearSelection()
        self._apply_row_visuals()
        self._update_status()
        self._update_action_states()

    def _handle_asset_cell_double_clicked(self, row: int, column: int) -> None:
        if column != 1:
            return
        item = self.assets_table.item(row, 0)
        if item is None:
            return
        checked = bool(item.data(Qt.ItemDataRole.UserRole + 1))
        sorting_enabled = self.assets_table.isSortingEnabled()
        if sorting_enabled:
            self.assets_table.setSortingEnabled(False)
        self._set_batch_mark(item, not checked)
        if sorting_enabled:
            self.assets_table.setSortingEnabled(True)
        self._apply_row_visuals()
        self._update_status()
        self._update_action_states()

    def _set_batch_mark(self, item: QTableWidgetItem, checked: bool) -> None:
        item.setData(Qt.ItemDataRole.UserRole + 1, checked)
        item.setText("●" if checked else "○")

    def _handle_asset_selection(self) -> None:
        selected_ranges = self.assets_table.selectedRanges()
        if selected_ranges:
            row = selected_ranges[0].topRow()
            item = self.assets_table.item(row, 1)
            asset_id = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
            self.current_asset_id = asset_id if isinstance(asset_id, str) else None
        else:
            self.current_asset_id = None
        if self.current_asset_id:
            self._load_asset_details(self.current_asset_id)
        else:
            self._clear_asset_details()
        self._apply_row_visuals()
        self._update_status()
        self._update_action_states()

    def _load_asset_details(self, asset_id: str | None) -> None:
        if not asset_id:
            self._clear_asset_details()
            return
        details = self.repository.get_asset_details(asset_id)
        if details is None:
            self.current_asset_id = None
            self._clear_asset_details()
            return
        self.detail_summary_label.setText(
            f"{details.asset.title} · {self._asset_type_label(details.asset.asset_type)} · {self._folder_label_for_asset(details.asset)}"
        )
        self.detail_text.setPlainText(self._format_asset_details(details))
        self._update_asset_preview(details.asset)
        if details.asset.asset_type == AssetType.UNKNOWN:
            self.manual_hint_label.setText(
                "当前资产处于“待复核”状态，执行手动改类型时会优先走复核流程。"
            )
        else:
            self.manual_hint_label.setText(
                "当前资产支持通用手动改类型，操作后会归回对应类型文件夹。"
            )
        self._update_action_states()

    def _clear_asset_details(self) -> None:
        self.detail_summary_label.setText("请选择一个资产以查看详情。")
        self.detail_text.setPlainText(
            "当前没有选中的资产。\n\n建议：点击某一行查看详情，勾选左侧复选框用于批量删除或批量导出。"
        )
        self.manual_hint_label.setText(
            "请先在资产库中选中一个资产，再执行手动改类型或复核。"
        )
        self.preview_label.clear()
        self.preview_hint_label.setText("当前资产没有可显示的角色卡图片预览。")
        self.current_preview_pixmap = None
        self._apply_row_visuals()
        self._update_action_states()

    def _format_asset_details(self, details: AssetDetailsRecord) -> str:
        asset = details.asset
        summary = details.extracted_summary
        metadata_lines = [
            f"标题：{asset.title}",
            f"类型：{self._asset_type_label(asset.asset_type)}",
            f"分类文件夹：{self._folder_label_for_asset(asset)}",
            f"格式：{(asset.payload_format or '—').upper()}",
            f"来源路径：{asset.source_path or '—'}",
        ]
        highlights: list[str] = []
        detection = summary.get("detection")
        if detection:
            highlights.append(f"识别方式：{self._detection_label(detection)}")
        if summary.get("entry_count") is not None:
            highlights.append(f"条目数：{summary.get('entry_count')}")
        if summary.get("has_character_book") is True:
            highlights.append("包含角色书内容")
        if asset.description:
            highlights.append(f"说明：{asset.description}")
        raw_payload = (details.raw_payload or "").strip()
        if len(raw_payload) > 400:
            raw_payload = raw_payload[:400] + "\n...（已截断）"
        raw_payload_text = raw_payload or "（无额外摘要内容）"
        return (
            "【基础信息】\n"
            + "\n".join(metadata_lines)
            + "\n\n【摘要】\n"
            + ("\n".join(highlights) if highlights else "（无额外摘要信息）")
            + "\n\n【内容预览】\n"
            + raw_payload_text
        )

    def _folder_label_for_asset(self, asset: AssetRecord) -> str:
        stored_path = Path(asset.stored_path)
        if (
            stored_path.parent.name.startswith("ast_")
            and stored_path.parent.parent.name
        ):
            return stored_path.parent.parent.name
        return stored_path.parent.name

    def _detection_label(self, value: object) -> str:
        return DETECTION_LABELS_FROM_TYPES.get(str(value), str(value or "—"))

    def _confidence_label(self, value: object) -> str:
        if value is None:
            return "—"
        return CONFIDENCE_LABELS.get(str(value), str(value))

    def _update_asset_preview(self, asset: AssetRecord) -> None:
        stored_path = Path(asset.stored_path)
        if (
            asset.asset_type != AssetType.CHARACTER_CARD
            or stored_path.suffix.lower() != ".png"
        ):
            self.preview_label.clear()
            self.preview_hint_label.setText("当前资产没有可显示的角色卡图片预览。")
            return
        pixmap = QPixmap(str(stored_path))
        if pixmap.isNull():
            self.preview_label.clear()
            self.preview_hint_label.setText("当前角色卡图片无法预览。")
            self.current_preview_pixmap = None
            return
        self.current_preview_pixmap = pixmap
        self._refresh_preview_pixmap()
        self.preview_hint_label.setText(f"预览文件：{stored_path.name}")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._refresh_preview_pixmap()

    def _refresh_preview_pixmap(self) -> None:
        if self.current_preview_pixmap is None:
            return
        size = self.preview_label.size()
        if size.width() <= 0 or size.height() <= 0:
            return
        scaled = self.current_preview_pixmap.scaled(
            max(1, size.width() - 12),
            max(1, size.height() - 12),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled)

    def _update_type_and_folder_summary(self, assets: list[AssetRecord]) -> None:
        counts = {asset_type: 0 for asset_type in ASSET_TYPE_ORDER}
        for asset in assets:
            counts[asset.asset_type] = counts.get(asset.asset_type, 0) + 1
        selected_type = self._resolve_type_filter()
        if selected_type is None:
            summary = (
                "、".join(
                    f"{self._asset_type_label(asset_type)} {count} 项"
                    for asset_type, count in counts.items()
                    if count > 0
                )
                or "当前还没有任何资产。"
            )
            self.type_summary_label.setText("分类统计：" + summary)
            self.folder_summary_label.setText(
                f"受管目录根路径：{self.paths.assets_dir}"
            )
        else:
            self.type_summary_label.setText(
                f"当前类型：{self._asset_type_label(selected_type)} · {counts.get(selected_type, 0)} 项"
            )
            self.folder_summary_label.setText(
                f"对应受管目录：{self.paths.asset_type_dirs[ASSET_TYPE_FOLDERS[selected_type]]}"
            )
        self.folder_summary_label.setWordWrap(True)

    def _update_status(self) -> None:
        selected_count = len(self._selected_asset_ids())
        focused = "无"
        if self.current_asset_id:
            details = self.repository.get_asset_details(self.current_asset_id)
            if details is not None:
                focused = details.asset.title
        self.summary_label.setText(
            f"当前显示 {len(self.asset_row_map)} 条资产 · 已勾选 {selected_count} 项 · 当前查看：{focused}"
        )

    def _update_action_states(self) -> None:
        asset_selected = self.current_asset_id is not None
        any_selected = bool(self._selected_asset_ids())
        selected_count = len(self._selected_asset_ids())
        self.retype_button.setEnabled(asset_selected)
        self.rename_button.setEnabled(asset_selected)
        self.clear_selection_button.setEnabled(any_selected)
        self.select_all_button.setEnabled(bool(self.asset_row_map))
        self.delete_button.setEnabled(any_selected)
        self.export_button.setEnabled(any_selected)
        self.export_button.setText(
            f"导出已选（{selected_count}）" if any_selected else "导出已选"
        )
        self.delete_button.setText(
            f"删除已选（{selected_count}）" if any_selected else "删除已选"
        )
        self.clear_selection_button.setText(
            f"清空勾选（{selected_count}）" if any_selected else "清空勾选"
        )

    def _apply_row_visuals(self) -> None:
        checked_color = QBrush(QColor("#e3f3ea"))
        focused_color = QBrush(QColor("#e2ebf7"))
        focused_checked_color = QBrush(QColor("#d5e8e0"))
        odd_base = QBrush(QColor("#f7f2ea"))
        even_base = QBrush(QColor("#fffdfa"))
        checked_mark_color = QBrush(QColor("#427366"))
        unchecked_mark_color = QBrush(QColor("#b7afa3"))
        focused_mark_color = QBrush(QColor("#355f8a"))

        for row in range(self.assets_table.rowCount()):
            checkbox_item = self.assets_table.item(row, 0)
            title_item = self.assets_table.item(row, 1)
            if checkbox_item is None or title_item is None:
                continue

            asset_id = title_item.data(Qt.ItemDataRole.UserRole)
            is_focused = isinstance(asset_id, str) and asset_id == self.current_asset_id
            is_checked = bool(checkbox_item.data(Qt.ItemDataRole.UserRole + 1))

            if is_focused and is_checked:
                brush = focused_checked_color
            elif is_focused:
                brush = focused_color
            elif is_checked:
                brush = checked_color
            else:
                brush = odd_base if row % 2 else even_base

            for column in range(self.assets_table.columnCount()):
                item = self.assets_table.item(row, column)
                if item is not None:
                    item.setBackground(brush)

            if is_focused:
                checkbox_item.setForeground(focused_mark_color)
            elif is_checked:
                checkbox_item.setForeground(checked_mark_color)
            else:
                checkbox_item.setForeground(unchecked_mark_color)

    def _show_import_result(self, result: ImportResult) -> None:
        lines = [
            f"{self._status_label(item.status)} · {Path(item.source_path).name} · {self._localize_result_message(item)}"
            for item in result.items
        ]
        if not lines:
            return
        QMessageBox.information(self, "导入结果", "\n".join(lines[:12]))

    def import_file(self) -> None:
        selected_path, _ = QFileDialog.getOpenFileName(self, "选择要导入的文件")
        if selected_path:
            self.run_import(Path(selected_path))

    def import_directory(self) -> None:
        selected_path = QFileDialog.getExistingDirectory(self, "选择要导入的文件夹")
        if selected_path:
            self.run_import(Path(selected_path))

    def run_import(self, selected_path: Path) -> None:
        self.status_label.setText(f"正在导入：{selected_path}")
        QApplication.processEvents()
        request = ImportRequest(
            input_path=selected_path.expanduser().resolve(),
            asset_type_override=self._resolve_override(),
        )
        result = import_path(paths=self.paths, request=request)
        self._show_import_result(result)
        self.refresh_assets()
        self.status_label.setText(
            f"导入完成：新增 {result.imported_count}，跳过 {result.skipped_count}，失败 {result.failed_count}"
        )

    def retype_selected_asset(self) -> None:
        if not self.current_asset_id:
            QMessageBox.information(self, "酒馆素材库", "请先在资产库中选中一个资产。")
            return
        details = self.repository.get_asset_details(self.current_asset_id)
        if details is None:
            self.current_asset_id = None
            self._clear_asset_details()
            return
        target_type = self._label_to_asset_type(self.manual_type_value)
        if target_type == AssetType.UNKNOWN:
            QMessageBox.information(self, "酒馆素材库", "请选择一个明确的目标类型。")
            return
        confirmed = QMessageBox.question(
            self,
            "确认改类型",
            f"确定要将“{details.asset.title}”改为“{self._asset_type_label(target_type)}”吗？",
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        result = (
            review_unknown_asset(self.paths, details.asset.id, target_type)
            if details.asset.asset_type == AssetType.UNKNOWN
            else retype_asset(self.paths, details.asset.id, target_type)
        )
        self._show_import_result(ImportResult(items=[result]))
        self.refresh_assets()
        if result.status == "failed":
            QMessageBox.critical(
                self, "改类型失败", self._localize_result_message(result)
            )

    def rename_selected_asset(self) -> None:
        if not self.current_asset_id:
            QMessageBox.information(self, "酒馆素材库", "请先在资产库中选中一个资产。")
            return
        asset = self.repository.get_asset(self.current_asset_id)
        if asset is None:
            self.current_asset_id = None
            self._clear_asset_details()
            return
        dialog = QInputDialog(self)
        dialog.setWindowTitle("重命名资产")
        dialog.setLabelText("请输入新的资产名称：")
        dialog.setTextValue(asset.title)
        dialog.resize(560, dialog.sizeHint().height())
        if not dialog.exec():
            return
        new_title = dialog.textValue()
        try:
            result = rename_asset(self.paths, asset.id, new_title)
        except Exception as exc:
            QMessageBox.critical(self, "重命名失败", str(exc))
            return
        self.current_asset_id = result.asset_id
        self.refresh_assets()
        self.status_label.setText(
            f"已将“{result.old_title}”重命名为“{result.new_title}”"
        )

    def delete_selected_assets(self) -> None:
        asset_ids = self._selected_asset_ids()
        if not asset_ids:
            QMessageBox.information(
                self, "酒馆素材库", "请先选择至少一个要删除的资产。"
            )
            return
        confirmed = QMessageBox.question(
            self,
            "确认删除资产",
            f"确定要删除 {len(asset_ids)} 个选中资产吗？\n\n此操作会同时清理数据库记录和对应的受管文件。",
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        deleted_titles: list[str] = []
        for asset_id in asset_ids:
            result = delete_asset(self.paths, asset_id)
            deleted_titles.append(result.title)
        self._show_import_result(
            ImportResult(
                items=[
                    ImportItemResult(
                        source_path=title, status="imported", message="Deleted asset"
                    )
                    for title in deleted_titles
                ]
            )
        )
        self.current_asset_id = None
        self.refresh_assets()
        self.status_label.setText(f"已删除 {len(deleted_titles)} 个资产")

    def export_selected_assets(self) -> None:
        asset_ids = self._selected_asset_ids()
        if not asset_ids:
            QMessageBox.information(
                self, "酒馆素材库", "请先在资产库中选择至少一个要导出的资产。"
            )
            return
        destination = QFileDialog.getExistingDirectory(self, "选择导出目标文件夹")
        if not destination:
            return
        result = export_assets(
            paths=self.paths,
            repository=self.repository,
            asset_ids=asset_ids,
            destination_root=Path(destination),
        )
        self.status_label.setText(
            f"已导出 {len(result.items)} 个资产到 {result.export_dir}"
        )
        QMessageBox.information(
            self,
            "导出完成",
            f"已原样导出 {len(result.items)} 个文件。\n\n目标目录：{result.export_dir}",
        )

    def select_all_assets(self) -> None:
        sorting_enabled = self.assets_table.isSortingEnabled()
        if sorting_enabled:
            self.assets_table.setSortingEnabled(False)
        for row in range(self.assets_table.rowCount()):
            item = self.assets_table.item(row, 0)
            if item is not None:
                self._set_batch_mark(item, True)
        if sorting_enabled:
            self.assets_table.setSortingEnabled(True)
        self._apply_row_visuals()
        self._update_status()
        self._update_action_states()

    def clear_asset_selection(self) -> None:
        sorting_enabled = self.assets_table.isSortingEnabled()
        if sorting_enabled:
            self.assets_table.setSortingEnabled(False)
        for row in range(self.assets_table.rowCount()):
            item = self.assets_table.item(row, 0)
            if item is not None:
                self._set_batch_mark(item, False)
        if sorting_enabled:
            self.assets_table.setSortingEnabled(True)
        self._apply_row_visuals()
        self._update_status()
        self._update_action_states()

    def _status_label(self, status: str) -> str:
        return STATUS_LABELS.get(status, status)

    def _localize_result_message(self, item: ImportItemResult) -> str:
        mapping = {
            "Duplicate content already imported": "重复内容已存在，已跳过",
            "Deleted asset": "已删除资产",
        }
        return mapping.get(item.message, item.message)


def launch_gui() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    window = TavernAssetLibraryWindow()
    window.show()
    app.exec()
