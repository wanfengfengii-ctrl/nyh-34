from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTextEdit, QPushButton, QGroupBox, QFormLayout,
    QMessageBox, QListWidget, QListWidgetItem,
)
from PySide6.QtCore import Qt, Signal
from typing import Optional, Dict, Any

from ..core.rubbing_service import RubbingService
from ..db.database import EditionRelationDAO


class EditionRelationDialog(QDialog):
    relationSaved = Signal()

    def __init__(
        self,
        service: RubbingService,
        relation_id: Optional[int] = None,
        source_group_id: Optional[int] = None,
        target_group_id: Optional[int] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._service = service
        self._relation_id = relation_id
        self._source_group_id = source_group_id
        self._target_group_id = target_group_id
        self._is_new = relation_id is None
        self.setWindowTitle("新建版别关系" if self._is_new else "编辑版别关系")
        self.resize(500, 450)
        self._build_ui()
        self._load_groups()
        if not self._is_new:
            self._load_relation_data()
        else:
            self._set_defaults()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        form_box = QGroupBox("关系信息")
        form = QFormLayout(form_box)

        self.source_combo = QComboBox()
        form.addRow("源版别组:", self.source_combo)

        self.relation_combo = QComboBox()
        for rel_type, label in EditionRelationDAO.RELATION_LABELS.items():
            self.relation_combo.addItem(label, rel_type)
        form.addRow("关系类型:", self.relation_combo)

        self.target_combo = QComboBox()
        form.addRow("目标版别组:", self.target_combo)

        direction_label = QLabel(
            "<span style='color:#666; font-size:11px;'>"
            "关系方向：源 → 目标（如：演化关系表示源演化为目标）"
            "</span>"
        )
        direction_label.setWordWrap(True)
        form.addRow("", direction_label)

        main_layout.addWidget(form_box)

        evidence_box = QGroupBox("证据与备注")
        evidence_layout = QVBoxLayout(evidence_box)

        evidence_info = QLabel(
            "<span style='color:#666; font-size:11px;'>"
            "可关联对比记录作为证据，或填写备注说明依据"
            "</span>"
        )
        evidence_info.setWordWrap(True)
        evidence_layout.addWidget(evidence_info)

        self.evidence_combo = QComboBox()
        self.evidence_combo.addItem("不关联对比记录", None)
        evidence_layout.addWidget(QLabel("关联对比记录:"))
        evidence_layout.addWidget(self.evidence_combo)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("填写关系判定依据、参考文献、考证说明等...")
        self.notes_edit.setMaximumHeight(150)
        evidence_layout.addWidget(QLabel("备注:"))
        evidence_layout.addWidget(self.notes_edit, 1)

        main_layout.addWidget(evidence_box, 1)

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

    def _load_groups(self):
        groups = self._service.list_edition_groups()
        self.source_combo.clear()
        self.target_combo.clear()
        for g in groups:
            name = g.get("name", "")
            gid = g.get("id")
            self.source_combo.addItem(name, gid)
            self.target_combo.addItem(name, gid)
        self.source_combo.currentIndexChanged.connect(self._on_group_changed)
        self.target_combo.currentIndexChanged.connect(self._on_group_changed)

    def _on_group_changed(self, index: int):
        self._load_evidence_options()

    def _set_defaults(self):
        if self._source_group_id:
            idx = self.source_combo.findData(self._source_group_id)
            if idx >= 0:
                self.source_combo.setCurrentIndex(idx)
                self.source_combo.setEnabled(False)
        if self._target_group_id:
            idx = self.target_combo.findData(self._target_group_id)
            if idx >= 0:
                self.target_combo.setCurrentIndex(idx)
                self.target_combo.setEnabled(False)
        self._load_evidence_options()

    def _load_evidence_options(self):
        source_group_id = self.source_combo.currentData()
        target_group_id = self.target_combo.currentData()
        self.evidence_combo.clear()
        self.evidence_combo.addItem("不关联对比记录", None)
        if not source_group_id or not target_group_id:
            return

        source_members = self._service.get_edition_group_members(source_group_id)
        target_members = self._service.get_edition_group_members(target_group_id)
        if not source_members or not target_members:
            return

        source_rubbing_ids = {m["id"] for m in source_members}
        target_rubbing_ids = {m["id"] for m in target_members}

        from ..db.database import ComparisonDAO
        all_comparisons = ComparisonDAO.list_all()
        for c in all_comparisons:
            a_id = c.get("rubbing_a_id")
            b_id = c.get("rubbing_b_id")
            a_in_source = a_id in source_rubbing_ids
            b_in_source = b_id in source_rubbing_ids
            a_in_target = a_id in target_rubbing_ids
            b_in_target = b_id in target_rubbing_ids
            if (a_in_source and b_in_target) or (b_in_source and a_in_target):
                code_a = c.get("code_a", "")
                code_b = c.get("code_b", "")
                score = c.get("similarity_score", 0)
                conclusion = c.get("conclusion", "")
                conclusion_label = "待确认"
                if conclusion == ComparisonDAO.CONCLUSION_SAME_EDITION:
                    conclusion_label = "同版"
                elif conclusion == ComparisonDAO.CONCLUSION_SUSPECTED_FORGERY:
                    conclusion_label = "疑似仿品"
                elif conclusion == ComparisonDAO.CONCLUSION_DIFFERENT:
                    conclusion_label = "不同版"
                item_text = f"{code_a} ↔ {code_b} ({score:.1f}%, {conclusion_label})"
                self.evidence_combo.addItem(item_text, c.get("id"))

    def _load_relation_data(self):
        if not self._relation_id:
            return
        relation = EditionRelationDAO.get_by_id(self._relation_id)
        if not relation:
            return

        source_id = relation.get("source_group_id")
        target_id = relation.get("target_group_id")

        idx = self.source_combo.findData(source_id)
        if idx >= 0:
            self.source_combo.setCurrentIndex(idx)

        idx = self.target_combo.findData(target_id)
        if idx >= 0:
            self.target_combo.setCurrentIndex(idx)

        rel_type = relation.get("relation_type", "")
        idx = self.relation_combo.findData(rel_type)
        if idx >= 0:
            self.relation_combo.setCurrentIndex(idx)

        self.notes_edit.setPlainText(relation.get("notes", "") or "")

        evidence_id = relation.get("evidence_comparison_id")
        self._load_evidence_options()
        if evidence_id:
            idx = self.evidence_combo.findData(evidence_id)
            if idx >= 0:
                self.evidence_combo.setCurrentIndex(idx)

    def _on_save(self):
        source_id = self.source_combo.currentData()
        target_id = self.target_combo.currentData()
        rel_type = self.relation_combo.currentData()

        if not source_id or not target_id:
            QMessageBox.warning(self, "提示", "请选择源版别组和目标版别组")
            return
        if source_id == target_id:
            QMessageBox.warning(self, "提示", "源版别组和目标版别组不能相同")
            return
        if not rel_type:
            QMessageBox.warning(self, "提示", "请选择关系类型")
            return

        data = {
            "source_group_id": source_id,
            "target_group_id": target_id,
            "relation_type": rel_type,
            "notes": self.notes_edit.toPlainText().strip(),
            "evidence_comparison_id": self.evidence_combo.currentData(),
        }

        try:
            if self._is_new:
                self._service.create_edition_relation(data)
                QMessageBox.information(self, "成功", "关系创建成功")
            else:
                self._service.update_edition_relation(self._relation_id, data)
                QMessageBox.information(self, "成功", "保存成功")
            self.relationSaved.emit()
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "提示", str(e))
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存失败: {e}")
