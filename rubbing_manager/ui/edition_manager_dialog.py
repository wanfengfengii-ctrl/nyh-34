from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QSplitter, QWidget,
    QLineEdit, QComboBox, QMessageBox, QTabWidget, QGroupBox,
    QFormLayout, QTextEdit,
)
from PySide6.QtCore import Qt, Signal
from typing import Optional, Dict, Any, List

from ..core.rubbing_service import RubbingService
from ..db.database import EditionRelationDAO
from .edition_graph_widget import EditionGraphWidget
from .edition_group_dialog import EditionGroupDialog
from .edition_relation_dialog import EditionRelationDialog
from .utils import load_pixmap_from_path


class EditionManagerDialog(QDialog):
    rubbingSelected = Signal(int)

    def __init__(self, service: RubbingService, parent=None):
        super().__init__(parent)
        self._service = service
        self.setWindowTitle("版别关系图谱与谱系管理")
        self.resize(1200, 800)
        self._build_ui()
        self._refresh_all()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索版别组名称...")
        self.search_edit.textChanged.connect(self._on_search_changed)
        self.search_edit.setMaximumWidth(200)
        toolbar.addWidget(self.search_edit)

        toolbar.addSpacing(20)

        self.btn_new_group = QPushButton("新建版别组")
        self.btn_new_group.clicked.connect(self._on_new_group)
        toolbar.addWidget(self.btn_new_group)

        self.btn_edit_group = QPushButton("编辑选中组")
        self.btn_edit_group.clicked.connect(self._on_edit_group)
        self.btn_edit_group.setEnabled(False)
        toolbar.addWidget(self.btn_edit_group)

        self.btn_delete_group = QPushButton("删除选中组")
        self.btn_delete_group.clicked.connect(self._on_delete_group)
        self.btn_delete_group.setEnabled(False)
        toolbar.addWidget(self.btn_delete_group)

        toolbar.addSeparator()

        self.btn_new_relation = QPushButton("新建关系")
        self.btn_new_relation.clicked.connect(self._on_new_relation)
        toolbar.addWidget(self.btn_new_relation)

        toolbar.addStretch()

        stats_label = QLabel()
        self.stats_label = stats_label
        toolbar.addWidget(stats_label)

        main_layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        left_header = QLabel("版别组列表")
        left_header.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px;")
        left_layout.addWidget(left_header)

        self.group_list = QListWidget()
        self.group_list.itemSelectionChanged.connect(self._on_group_selected)
        self.group_list.itemDoubleClicked.connect(self._on_group_double_clicked)
        left_layout.addWidget(self.group_list, 1)

        splitter.addWidget(left_panel)

        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)

        self.graph_widget = EditionGraphWidget(self._service)
        self.graph_widget.groupSelected.connect(self._on_graph_group_selected)
        self.graph_widget.groupDoubleClicked.connect(self._on_graph_group_double_clicked)
        center_layout.addWidget(self.graph_widget, 1)

        splitter.addWidget(center_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        right_header = QLabel("关系列表")
        right_header.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px;")
        right_layout.addWidget(right_header)

        self.relation_list = QListWidget()
        self.relation_list.itemDoubleClicked.connect(self._on_relation_double_clicked)
        right_layout.addWidget(self.relation_list, 1)

        rel_btn_layout = QHBoxLayout()
        self.btn_edit_rel = QPushButton("编辑关系")
        self.btn_edit_rel.clicked.connect(self._on_edit_relation)
        self.btn_edit_rel.setEnabled(False)
        self.btn_delete_rel = QPushButton("删除关系")
        self.btn_delete_rel.clicked.connect(self._on_delete_relation)
        self.btn_delete_rel.setEnabled(False)
        rel_btn_layout.addWidget(self.btn_edit_rel)
        rel_btn_layout.addWidget(self.btn_delete_rel)
        right_layout.addLayout(rel_btn_layout)

        splitter.addWidget(right_panel)

        splitter.setSizes([250, 600, 300])

        main_layout.addWidget(splitter, 1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)
        main_layout.addLayout(btn_layout)

        self.relation_list.itemSelectionChanged.connect(self._on_relation_selection_changed)

    def _refresh_all(self):
        self._refresh_group_list()
        self._refresh_relation_list()
        self._refresh_stats()
        self.graph_widget.refresh()

    def _refresh_group_list(self):
        current_id = self._get_selected_group_id()
        keyword = self.search_edit.text().strip()
        self.group_list.clear()

        groups = self._service.list_edition_groups(keyword=keyword if keyword else None)
        for g in groups:
            member_count = g.get("member_count", 0) if "member_count" in g else 0
            if member_count == 0:
                member_count = self._service.get_edition_group_members(g["id"]).__len__() if False else 0
            name = g.get("name", "")
            era = g.get("era", "") or "—"
            item_text = f"{name}\n  {era} · {g.get('inscription', '—') or '—'}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, g.get("id"))
            self.group_list.addItem(item)
            if current_id and g.get("id") == current_id:
                self.group_list.setCurrentItem(item)

        has_selection = self.group_list.currentItem() is not None
        self.btn_edit_group.setEnabled(has_selection)
        self.btn_delete_group.setEnabled(has_selection)

    def _refresh_relation_list(self):
        self.relation_list.clear()
        relations = self._service.list_edition_relations()
        for r in relations:
            rel_type = r.get("relation_type", "")
            label = EditionRelationDAO.RELATION_LABELS.get(rel_type, rel_type)
            source = r.get("source_name", "")
            target = r.get("target_name", "")
            item_text = f"[{label}] {source} → {target}"
            notes = r.get("notes", "")
            if notes:
                item_text += f"\n  备注: {notes[:40]}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, r.get("id"))
            self.relation_list.addItem(item)

        has_sel = self.relation_list.currentItem() is not None
        self.btn_edit_rel.setEnabled(has_sel)
        self.btn_delete_rel.setEnabled(has_sel)

    def _refresh_stats(self):
        group_count = self._service.count_edition_groups()
        rel_count = self._service.count_edition_relations()
        self.stats_label.setText(f"共 {group_count} 个版别组 · {rel_count} 条关系")

    def _get_selected_group_id(self) -> Optional[int]:
        item = self.group_list.currentItem()
        if item:
            return item.data(Qt.UserRole)
        return None

    def _on_search_changed(self, text: str):
        self._refresh_group_list()

    def _on_group_selected(self):
        group_id = self._get_selected_group_id()
        has_selection = group_id is not None
        self.btn_edit_group.setEnabled(has_selection)
        self.btn_delete_group.setEnabled(has_selection)
        if group_id:
            self.graph_widget.focus_on_group(group_id)

    def _on_group_double_clicked(self, item: QListWidgetItem):
        group_id = item.data(Qt.UserRole)
        if group_id:
            self._edit_group(group_id)

    def _on_graph_group_selected(self, group_id: int):
        for i in range(self.group_list.count()):
            item = self.group_list.item(i)
            if item.data(Qt.UserRole) == group_id:
                self.group_list.setCurrentItem(item)
                break

    def _on_graph_group_double_clicked(self, group_id: int):
        self._edit_group(group_id)

    def _on_new_group(self):
        dialog = EditionGroupDialog(self._service, parent=self)
        dialog.groupUpdated.connect(self._on_group_updated)
        dialog.exec()

    def _on_edit_group(self):
        group_id = self._get_selected_group_id()
        if group_id:
            self._edit_group(group_id)

    def _edit_group(self, group_id: int):
        dialog = EditionGroupDialog(self._service, group_id=group_id, parent=self)
        dialog.groupUpdated.connect(self._on_group_updated)
        dialog.exec()

    def _on_delete_group(self):
        group_id = self._get_selected_group_id()
        if not group_id:
            return
        group = self._service.get_edition_group(group_id)
        if not group:
            return
        can_delete, msg = self._service.can_delete_edition_group(group_id)
        if not can_delete:
            QMessageBox.warning(self, "无法删除", msg)
            return
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除版别组 [{group.get('name', '')}] 吗？\n此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                success, msg = self._service.delete_edition_group(group_id)
                if success:
                    QMessageBox.information(self, "成功", msg)
                    self._refresh_all()
                else:
                    QMessageBox.warning(self, "提示", msg)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除失败: {e}")

    def _on_group_updated(self):
        self._refresh_all()

    def _on_new_relation(self):
        dialog = EditionRelationDialog(self._service, parent=self)
        dialog.relationSaved.connect(self._on_relation_saved)
        dialog.exec()

    def _on_edit_relation(self):
        item = self.relation_list.currentItem()
        if not item:
            return
        relation_id = item.data(Qt.UserRole)
        dialog = EditionRelationDialog(self._service, relation_id=relation_id, parent=self)
        dialog.relationSaved.connect(self._on_relation_saved)
        dialog.exec()

    def _on_delete_relation(self):
        item = self.relation_list.currentItem()
        if not item:
            return
        relation_id = item.data(Qt.UserRole)
        reply = QMessageBox.question(
            self, "确认删除",
            "确定要删除这条关系吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                self._service.delete_edition_relation(relation_id)
                QMessageBox.information(self, "成功", "关系已删除")
                self._refresh_all()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除失败: {e}")

    def _on_relation_double_clicked(self, item: QListWidgetItem):
        relation_id = item.data(Qt.UserRole)
        if relation_id:
            dialog = EditionRelationDialog(self._service, relation_id=relation_id, parent=self)
            dialog.relationSaved.connect(self._on_relation_saved)
            dialog.exec()

    def _on_relation_saved(self):
        self._refresh_all()

    def _on_relation_selection_changed(self):
        has_sel = self.relation_list.currentItem() is not None
        self.btn_edit_rel.setEnabled(has_sel)
        self.btn_delete_rel.setEnabled(has_sel)

    def focus_on_group(self, group_id: int):
        for i in range(self.group_list.count()):
            item = self.group_list.item(i)
            if item.data(Qt.UserRole) == group_id:
                self.group_list.setCurrentItem(item)
                break
        self.graph_widget.focus_on_group(group_id)
