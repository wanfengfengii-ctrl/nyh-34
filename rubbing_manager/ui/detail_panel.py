from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTextEdit, QFormLayout, QPushButton, QGroupBox, QComboBox,
    QMessageBox, QListWidget, QListWidgetItem,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from typing import Optional, Dict, Any

from ..core.rubbing_service import RubbingService
from .utils import load_pixmap_from_path


class DetailPanel(QWidget):
    dataChanged = Signal()
    editImageRequested = Signal()
    deleteRequested = Signal(int)
    findSimilarRequested = Signal()
    viewComparisonsRequested = Signal()
    viewEditionGraphRequested = Signal()
    editionGroupChanged = Signal()
    exportReportRequested = Signal(int)

    def __init__(self, service: RubbingService, parent=None):
        super().__init__(parent)
        self._service = service
        self._current_rubbing = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumHeight(250)
        self.image_label.setStyleSheet("border: 1px solid #ddd; background: #fafafa;")
        layout.addWidget(self.image_label)

        self.btn_edit_image = QPushButton("编辑图片")
        self.btn_edit_image.clicked.connect(self.editImageRequested.emit)
        self.btn_edit_image.setEnabled(False)
        layout.addWidget(self.btn_edit_image)

        info_box = QGroupBox("拓片信息")
        form = QFormLayout(info_box)

        self.code_edit = QLineEdit()
        self.code_edit.setReadOnly(True)
        form.addRow("编号:", self.code_edit)

        self.era_combo = QComboBox()
        self.era_combo.setEditable(True)
        form.addRow("年代:", self.era_combo)

        self.inscription_edit = QLineEdit()
        form.addRow("钱文:", self.inscription_edit)

        self.material_edit = QLineEdit()
        form.addRow("材质:", self.material_edit)

        self.excavation_edit = QLineEdit()
        form.addRow("出土地:", self.excavation_edit)

        self.contour_label = QLabel("—")
        form.addRow("有效轮廓:", self.contour_label)

        self.size_label = QLabel("—")
        form.addRow("尺寸:", self.size_label)

        layout.addWidget(info_box)

        notes_box = QGroupBox("备注")
        notes_layout = QVBoxLayout(notes_box)
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("填写备注信息...")
        self.notes_edit.setMaximumHeight(80)
        notes_layout.addWidget(self.notes_edit)
        layout.addWidget(notes_box)

        action_layout = QHBoxLayout()
        self.btn_save = QPushButton("保存信息")
        self.btn_save.clicked.connect(self._save_info)
        self.btn_save.setEnabled(False)
        self.btn_delete = QPushButton("删除")
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_delete.setEnabled(False)
        action_layout.addWidget(self.btn_save)
        action_layout.addWidget(self.btn_delete)
        layout.addLayout(action_layout)

        action2_layout = QHBoxLayout()
        self.btn_similar = QPushButton("查找相似")
        self.btn_similar.clicked.connect(self.findSimilarRequested.emit)
        self.btn_similar.setEnabled(False)
        self.btn_comparisons = QPushButton("查看对比记录")
        self.btn_comparisons.clicked.connect(self.viewComparisonsRequested.emit)
        self.btn_comparisons.setEnabled(False)
        action2_layout.addWidget(self.btn_similar)
        action2_layout.addWidget(self.btn_comparisons)
        layout.addLayout(action2_layout)

        action3_layout = QHBoxLayout()
        self.btn_export_report = QPushButton("导出研究报告")
        self.btn_export_report.clicked.connect(self._on_export_report)
        self.btn_export_report.setEnabled(False)
        action3_layout.addWidget(self.btn_export_report)
        layout.addLayout(action3_layout)

        edition_box = QGroupBox("版别组")
        edition_layout = QVBoxLayout(edition_box)

        self.edition_list = QListWidget()
        self.edition_list.setMaximumHeight(80)
        self.edition_list.itemDoubleClicked.connect(self._on_edition_group_double_clicked)
        edition_layout.addWidget(self.edition_list)

        btn_edition_layout = QHBoxLayout()
        self.btn_create_group = QPushButton("新建版别组")
        self.btn_create_group.clicked.connect(self._on_create_group)
        self.btn_create_group.setEnabled(False)
        self.btn_join_group = QPushButton("加入版别组")
        self.btn_join_group.clicked.connect(self._on_join_group)
        self.btn_join_group.setEnabled(False)
        self.btn_leave_group = QPushButton("退出选中")
        self.btn_leave_group.clicked.connect(self._on_leave_group)
        self.btn_leave_group.setEnabled(False)
        btn_edition_layout.addWidget(self.btn_create_group)
        btn_edition_layout.addWidget(self.btn_join_group)
        btn_edition_layout.addWidget(self.btn_leave_group)
        edition_layout.addLayout(btn_edition_layout)

        btn_graph_layout = QHBoxLayout()
        self.btn_view_graph = QPushButton("查看关系图谱")
        self.btn_view_graph.clicked.connect(self.viewEditionGraphRequested.emit)
        self.btn_view_graph.setEnabled(False)
        btn_graph_layout.addWidget(self.btn_view_graph)
        edition_layout.addLayout(btn_graph_layout)

        layout.addWidget(edition_box)

        layout.addStretch()

    def set_rubbing(self, rubbing: Optional[Dict[str, Any]]):
        self._current_rubbing = rubbing
        has_data = rubbing is not None

        self.btn_edit_image.setEnabled(has_data)
        self.btn_save.setEnabled(has_data)
        self.btn_delete.setEnabled(has_data)
        self.btn_comparisons.setEnabled(has_data)

        has_contour = has_data and rubbing.get("has_valid_contour", False)
        self.btn_similar.setEnabled(has_contour)

        self.btn_create_group.setEnabled(has_data)
        self.btn_join_group.setEnabled(has_data)
        self.btn_view_graph.setEnabled(has_data)
        self.btn_export_report.setEnabled(has_data)

        if has_data:
            self._load_edition_groups(rubbing["id"])
        else:
            self.edition_list.clear()
            self.btn_leave_group.setEnabled(False)

        if not rubbing:
            self.image_label.clear()
            self.code_edit.clear()
            self.era_combo.clear()
            self.inscription_edit.clear()
            self.material_edit.clear()
            self.excavation_edit.clear()
            self.notes_edit.clear()
            self.contour_label.setText("—")
            self.size_label.setText("—")
            return

        img_path = rubbing.get("processed_path") or rubbing.get("original_path")
        if img_path:
            pixmap = load_pixmap_from_path(img_path, 300, 250)
            self.image_label.setPixmap(pixmap)
        else:
            self.image_label.clear()

        self.code_edit.setText(rubbing.get("code", ""))
        self.era_combo.setCurrentText(rubbing.get("era", ""))
        self.inscription_edit.setText(rubbing.get("inscription", ""))
        self.material_edit.setText(rubbing.get("material", ""))
        self.excavation_edit.setText(rubbing.get("excavation_site", ""))
        self.notes_edit.setPlainText(rubbing.get("notes", ""))

        has_contour = rubbing.get("has_valid_contour", False)
        self.contour_label.setText("是" if has_contour else "否")
        self.contour_label.setStyleSheet(
            "color: green;" if has_contour else "color: red;"
        )

        w = rubbing.get("width", 0)
        h = rubbing.get("height", 0)
        if w and h:
            self.size_label.setText(f"{w} × {h}")
        else:
            self.size_label.setText("—")

    def _save_info(self):
        if not self._current_rubbing:
            return
        data = {
            "era": self.era_combo.currentText().strip(),
            "inscription": self.inscription_edit.text().strip(),
            "material": self.material_edit.text().strip(),
            "excavation_site": self.excavation_edit.text().strip(),
            "notes": self.notes_edit.toPlainText().strip(),
        }
        try:
            self._service.update_rubbing(self._current_rubbing["id"], data)
            QMessageBox.information(self, "成功", "信息已保存")
            self.dataChanged.emit()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")

    def _on_delete(self):
        if not self._current_rubbing:
            return
        rubbing_id = self._current_rubbing["id"]
        can_delete, msg = self._service.can_delete_rubbing(rubbing_id)
        if not can_delete:
            QMessageBox.warning(self, "无法删除", msg)
            return

        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除拓片 [{self._current_rubbing.get('code', '')}] 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success, msg = self._service.delete_rubbing(rubbing_id)
            if success:
                QMessageBox.information(self, "成功", msg)
                self.deleteRequested.emit(rubbing_id)
            else:
                QMessageBox.warning(self, "提示", msg)

    def _on_export_report(self):
        if not self._current_rubbing:
            return
        self.exportReportRequested.emit(self._current_rubbing["id"])

    def set_eras(self, eras: list):
        current = self.era_combo.currentText()
        self.era_combo.clear()
        self.era_combo.addItems(eras)
        if current:
            idx = self.era_combo.findText(current)
            if idx >= 0:
                self.era_combo.setCurrentIndex(idx)
            else:
                self.era_combo.setCurrentText(current)

    def _load_edition_groups(self, rubbing_id: int):
        self.edition_list.clear()
        groups = self._service.get_edition_groups_for_rubbing(rubbing_id)
        if not groups:
            item = QListWidgetItem("未加入任何版别组")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.edition_list.addItem(item)
            self.btn_leave_group.setEnabled(False)
            return
        for g in groups:
            item = QListWidgetItem(g.get("name", ""))
            item.setData(Qt.UserRole, g.get("id"))
            self.edition_list.addItem(item)
        self.btn_leave_group.setEnabled(True)

    def _on_create_group(self):
        if not self._current_rubbing:
            return
        from .edition_group_dialog import EditionGroupDialog
        dialog = EditionGroupDialog(
            self._service,
            initial_rubbing_id=self._current_rubbing["id"],
            parent=self,
        )
        dialog.groupUpdated.connect(self._on_edition_group_changed)
        dialog.exec()

    def _on_join_group(self):
        if not self._current_rubbing:
            return
        groups = self._service.list_edition_groups()
        if not groups:
            QMessageBox.information(self, "提示", "暂无版别组，请先创建版别组")
            return
        group_names = [g.get("name", "") for g in groups]
        group_ids = [g.get("id") for g in groups]
        from PySide6.QtWidgets import QInputDialog
        choice, ok = QInputDialog.getItem(
            self, "加入版别组", "选择要加入的版别组:",
            group_names, 0, False
        )
        if not ok:
            return
        idx = group_names.index(choice)
        group_id = group_ids[idx]
        if self._service.is_rubbing_in_group(group_id, self._current_rubbing["id"]):
            QMessageBox.information(self, "提示", "该拓片已在此版别组中")
            return
        try:
            self._service.add_rubbing_to_group(group_id, self._current_rubbing["id"])
            self._load_edition_groups(self._current_rubbing["id"])
            QMessageBox.information(self, "成功", "已加入版别组")
            self.editionGroupChanged.emit()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加入失败: {e}")

    def _on_leave_group(self):
        if not self._current_rubbing:
            return
        item = self.edition_list.currentItem()
        if not item or not item.data(Qt.UserRole):
            QMessageBox.information(self, "提示", "请先选择一个版别组")
            return
        group_id = item.data(Qt.UserRole)
        reply = QMessageBox.question(
            self, "确认退出",
            f"确定要退出该版别组吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                self._service.remove_rubbing_from_group(group_id, self._current_rubbing["id"])
                self._load_edition_groups(self._current_rubbing["id"])
                QMessageBox.information(self, "成功", "已退出版别组")
                self.editionGroupChanged.emit()
            except Exception as e:
                QMessageBox.critical(self, "错误", f"退出失败: {e}")

    def _on_edition_group_changed(self):
        if self._current_rubbing:
            self._load_edition_groups(self._current_rubbing["id"])
        self.editionGroupChanged.emit()

    def _on_edition_group_double_clicked(self, item):
        group_id = item.data(Qt.UserRole)
        if not group_id:
            return
        from .edition_group_dialog import EditionGroupDialog
        dialog = EditionGroupDialog(
            self._service,
            group_id=group_id,
            parent=self,
        )
        dialog.groupUpdated.connect(self._on_edition_group_changed)
        dialog.exec()

    def refresh_edition_groups(self):
        if self._current_rubbing:
            self._load_edition_groups(self._current_rubbing["id"])
