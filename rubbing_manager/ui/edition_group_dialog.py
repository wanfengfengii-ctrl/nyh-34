from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QComboBox, QPushButton, QListWidget, QListWidgetItem,
    QGroupBox, QFormLayout, QMessageBox, QSplitter, QWidget,
    QInputDialog, QTabWidget,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon
from typing import Optional, Dict, Any, List

from ..core.rubbing_service import RubbingService
from ..db.database import EditionGroupDAO, EditionRelationDAO
from .utils import load_pixmap_from_path


class EditionGroupDialog(QDialog):
    groupUpdated = Signal()

    def __init__(
        self,
        service: RubbingService,
        group_id: Optional[int] = None,
        initial_rubbing_id: Optional[int] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._service = service
        self._group_id = group_id
        self._initial_rubbing_id = initial_rubbing_id
        self._is_new = group_id is None
        self.setWindowTitle("新建版别组" if self._is_new else "编辑版别组")
        self.resize(800, 600)
        self._build_ui()
        if not self._is_new:
            self._load_group_data()
        elif initial_rubbing_id:
            self._prefill_from_rubbing(initial_rubbing_id)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        tabs = QTabWidget()

        info_tab = QWidget()
        info_layout = QVBoxLayout(info_tab)

        info_box = QGroupBox("基本信息")
        form = QFormLayout(info_box)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("输入版别组名称...")
        form.addRow("名称:", self.name_edit)

        self.era_combo = QComboBox()
        self.era_combo.setEditable(True)
        self._load_eras()
        form.addRow("年代:", self.era_combo)

        self.inscription_edit = QLineEdit()
        self.inscription_edit.setPlaceholderText("钱文...")
        form.addRow("钱文:", self.inscription_edit)

        self.material_edit = QLineEdit()
        self.material_edit.setPlaceholderText("材质...")
        form.addRow("材质:", self.material_edit)

        info_layout.addWidget(info_box)

        desc_box = QGroupBox("描述")
        desc_layout = QVBoxLayout(desc_box)
        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("输入版别组描述、特征说明、断代依据等...")
        desc_layout.addWidget(self.desc_edit)
        info_layout.addWidget(desc_box)

        tabs.addTab(info_tab, "基本信息")

        members_tab = QWidget()
        members_layout = QVBoxLayout(members_tab)

        member_toolbar = QHBoxLayout()
        member_toolbar.addWidget(QLabel("成员拓片:"))
        member_toolbar.addStretch()
        self.btn_add_member = QPushButton("添加拓片")
        self.btn_add_member.clicked.connect(self._on_add_member)
        member_toolbar.addWidget(self.btn_add_member)
        self.btn_remove_member = QPushButton("移除选中")
        self.btn_remove_member.clicked.connect(self._on_remove_member)
        member_toolbar.addWidget(self.btn_remove_member)
        members_layout.addLayout(member_toolbar)

        self.members_list = QListWidget()
        self.members_list.setIconSize(QSize(60, 60))
        self.members_list.setUniformItemSizes(False)
        self.members_list.setViewMode(QListWidget.ListMode)
        members_layout.addWidget(self.members_list, 1)

        self.member_count_label = QLabel("共 0 个拓片")
        members_layout.addWidget(self.member_count_label)

        tabs.addTab(members_tab, "成员管理")

        relations_tab = QWidget()
        relations_layout = QVBoxLayout(relations_tab)

        rel_toolbar = QHBoxLayout()
        rel_toolbar.addWidget(QLabel("关联关系:"))
        rel_toolbar.addStretch()
        self.btn_add_relation = QPushButton("添加关系")
        self.btn_add_relation.clicked.connect(self._on_add_relation)
        rel_toolbar.addWidget(self.btn_add_relation)
        self.btn_edit_relation = QPushButton("编辑关系")
        self.btn_edit_relation.clicked.connect(self._on_edit_relation)
        rel_toolbar.addWidget(self.btn_edit_relation)
        self.btn_delete_relation = QPushButton("删除关系")
        self.btn_delete_relation.clicked.connect(self._on_delete_relation)
        rel_toolbar.addWidget(self.btn_delete_relation)
        relations_layout.addLayout(rel_toolbar)

        self.relations_list = QListWidget()
        relations_layout.addWidget(self.relations_list, 1)

        tabs.addTab(relations_tab, "关系管理")

        main_layout.addWidget(tabs, 1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        self.btn_save = QPushButton("保存")
        self.btn_save.clicked.connect(self._on_save)
        self.btn_save.setStyleSheet("background: #4a90d9; color: white; padding: 6px 16px;")
        btn_layout.addWidget(self.btn_save)
        main_layout.addLayout(btn_layout)

        if self._is_new:
            self.btn_add_member.setEnabled(False)
            self.btn_remove_member.setEnabled(False)
            self.btn_add_relation.setEnabled(False)
            self.btn_edit_relation.setEnabled(False)
            self.btn_delete_relation.setEnabled(False)

    def _load_eras(self):
        eras = self._service.get_all_eras()
        self.era_combo.addItems(eras)

    def _prefill_from_rubbing(self, rubbing_id: int):
        rubbing = self._service.get_rubbing(rubbing_id)
        if rubbing:
            self.era_combo.setCurrentText(rubbing.get("era", ""))
            self.inscription_edit.setText(rubbing.get("inscription", ""))
            self.material_edit.setText(rubbing.get("material", ""))
            code = rubbing.get("code", "")
            inscription = rubbing.get("inscription", "")
            default_name = f"{inscription}版别组" if inscription else f"{code}版别组"
            self.name_edit.setText(default_name)

    def _load_group_data(self):
        if not self._group_id:
            return
        group = self._service.get_edition_group(self._group_id)
        if not group:
            return

        self.name_edit.setText(group.get("name", ""))
        self.era_combo.setCurrentText(group.get("era", ""))
        self.inscription_edit.setText(group.get("inscription", ""))
        self.material_edit.setText(group.get("material", ""))
        self.desc_edit.setPlainText(group.get("description", ""))

        self._load_members()
        self._load_relations()

    def _load_members(self):
        if not self._group_id:
            return
        self.members_list.clear()
        members = self._service.get_edition_group_members(self._group_id)
        for m in members:
            item = QListWidgetItem()
            display_text = f"{m.get('code', '')}\n{m.get('era', '—')} · {m.get('inscription', '—')}"
            item.setText(display_text)
            item.setData(Qt.UserRole, m.get("id"))
            item.setSizeHint(QSize(0, 70))

            img_path = m.get("processed_path") or m.get("original_path")
            if img_path:
                pixmap = load_pixmap_from_path(img_path, 60, 60)
                if not pixmap.isNull():
                    item.setIcon(QIcon(pixmap))

            self.members_list.addItem(item)
        self.member_count_label.setText(f"共 {len(members)} 个拓片")

    def _load_relations(self):
        if not self._group_id:
            return
        self.relations_list.clear()
        relations = self._service.get_relations_for_group(self._group_id)
        for r in relations:
            rel_type = r.get("relation_type", "")
            label = EditionRelationDAO.RELATION_LABELS.get(rel_type, rel_type)
            source_name = r.get("source_name", "")
            target_name = r.get("target_name", "")
            if r.get("source_group_id") == self._group_id:
                direction = "→"
                other_name = target_name
            else:
                direction = "←"
                other_name = source_name
            item_text = f"[{label}] {direction} {other_name}"
            notes = r.get("notes", "")
            if notes:
                item_text += f"\n  备注: {notes[:30]}..."
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, r.get("id"))
            self.relations_list.addItem(item)

    def _on_add_member(self):
        if not self._group_id:
            return
        rubbing_id, ok = QInputDialog.getInt(
            self, "添加拓片", "输入拓片ID:"
        )
        if not ok:
            return
        rubbing = self._service.get_rubbing(rubbing_id)
        if not rubbing:
            QMessageBox.warning(self, "错误", "找不到该拓片")
            return
        if self._service.is_rubbing_in_group(self._group_id, rubbing_id):
            QMessageBox.information(self, "提示", "该拓片已在此版别组中")
            return
        try:
            self._service.add_rubbing_to_group(self._group_id, rubbing_id)
            self._load_members()
            QMessageBox.information(self, "成功", "拓片已添加到版别组")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"添加失败: {e}")

    def _on_remove_member(self):
        if not self._group_id:
            return
        item = self.members_list.currentItem()
        if not item:
            QMessageBox.information(self, "提示", "请先选择一个拓片")
            return
        rubbing_id = item.data(Qt.UserRole)
        reply = QMessageBox.question(
            self, "确认移除",
            "确定要将该拓片从版别组中移除吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                self._service.remove_rubbing_from_group(self._group_id, rubbing_id)
                self._load_members()
                QMessageBox.information(self, "成功", "已从版别组中移除")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"移除失败: {e}")

    def _on_add_relation(self):
        if not self._group_id:
            return
        from .edition_relation_dialog import EditionRelationDialog
        dialog = EditionRelationDialog(
            self._service,
            source_group_id=self._group_id,
            parent=self,
        )
        dialog.relationSaved.connect(self._on_relation_saved)
        dialog.exec()

    def _on_edit_relation(self):
        item = self.relations_list.currentItem()
        if not item:
            QMessageBox.information(self, "提示", "请先选择一条关系")
            return
        relation_id = item.data(Qt.UserRole)
        from .edition_relation_dialog import EditionRelationDialog
        dialog = EditionRelationDialog(
            self._service,
            relation_id=relation_id,
            parent=self,
        )
        dialog.relationSaved.connect(self._on_relation_saved)
        dialog.exec()

    def _on_delete_relation(self):
        item = self.relations_list.currentItem()
        if not item:
            QMessageBox.information(self, "提示", "请先选择一条关系")
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
                self._load_relations()
                QMessageBox.information(self, "成功", "关系已删除")
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除失败: {e}")

    def _on_relation_saved(self):
        self._load_relations()
        self.groupUpdated.emit()

    def _on_save(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入版别组名称")
            return

        data = {
            "name": name,
            "era": self.era_combo.currentText().strip(),
            "inscription": self.inscription_edit.text().strip(),
            "material": self.material_edit.text().strip(),
            "description": self.desc_edit.toPlainText().strip(),
        }

        try:
            if self._is_new:
                group_id = self._service.create_edition_group(data)
                self._group_id = group_id
                self._is_new = False
                self.setWindowTitle("编辑版别组")
                self.btn_add_member.setEnabled(True)
                self.btn_remove_member.setEnabled(True)
                self.btn_add_relation.setEnabled(True)
                self.btn_edit_relation.setEnabled(True)
                self.btn_delete_relation.setEnabled(True)

                if self._initial_rubbing_id:
                    self._service.add_rubbing_to_group(group_id, self._initial_rubbing_id)
                    self._load_members()

                self._load_relations()
                QMessageBox.information(self, "成功", "版别组创建成功")
            else:
                self._service.update_edition_group(self._group_id, data)
                QMessageBox.information(self, "成功", "保存成功")

            self.groupUpdated.emit()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")

    def get_group_id(self) -> Optional[int]:
        return self._group_id
