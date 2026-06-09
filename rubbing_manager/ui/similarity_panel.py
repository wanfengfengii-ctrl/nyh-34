from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QGroupBox, QSplitter,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap
from typing import List, Dict, Any, Optional

from ..core.rubbing_service import RubbingService
from ..db.database import SimilarityFeedbackDAO
from .utils import load_pixmap_from_path


class SimilarityPanel(QWidget):
    compareRequested = Signal(int, int)
    feedbackSubmitted = Signal()

    def __init__(self, service: RubbingService, parent=None):
        super().__init__(parent)
        self._service = service
        self._target_rubbing = None
        self._results = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel("相似拓片推荐")
        header.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px;")
        layout.addWidget(header)

        self.weight_label = QLabel()
        self.weight_label.setStyleSheet("color: #666; font-size: 11px; padding: 2px 8px;")
        self._update_weight_display()
        layout.addWidget(self.weight_label)

        self.info_label = QLabel("请选择一个拓片以查找相似拓片")
        self.info_label.setStyleSheet("color: #666; padding: 8px;")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        self.result_list = QListWidget()
        self.result_list.setItemAlignment(Qt.AlignLeft)
        self.result_list.setIconSize(QSize(64, 64))
        self.result_list.setUniformItemSizes(True)
        self.result_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.result_list, 1)

        btn_layout = QHBoxLayout()
        self.btn_match = QPushButton("查找相似")
        self.btn_match.clicked.connect(self._do_match)
        self.btn_compare = QPushButton("对比选中")
        self.btn_compare.clicked.connect(self._on_compare_clicked)
        self.btn_compare.setEnabled(False)
        btn_layout.addWidget(self.btn_match)
        btn_layout.addWidget(self.btn_compare)
        layout.addLayout(btn_layout)

        feedback_box = QGroupBox("反馈")
        feedback_layout = QHBoxLayout(feedback_box)
        self.btn_correct = QPushButton("✓ 推荐正确")
        self.btn_correct.setStyleSheet("background: #2ecc71; color: white; padding: 6px;")
        self.btn_correct.clicked.connect(lambda: self._on_feedback("correct"))
        self.btn_correct.setEnabled(False)
        self.btn_wrong = QPushButton("✗ 推荐错误")
        self.btn_wrong.setStyleSheet("background: #e74c3c; color: white; padding: 6px;")
        self.btn_wrong.clicked.connect(lambda: self._on_feedback("wrong"))
        self.btn_wrong.setEnabled(False)
        feedback_layout.addWidget(self.btn_correct)
        feedback_layout.addWidget(self.btn_wrong)
        layout.addWidget(feedback_box)

        self.result_list.currentItemChanged.connect(self._on_selection_changed)

    def _update_weight_display(self):
        contour_w, texture_w = self._service.get_current_weights()
        self.weight_label.setText(
            f"当前权重 - 轮廓: {contour_w:.1%} | 纹理: {texture_w:.1%}"
        )

    def _on_selection_changed(self):
        has_selection = self.result_list.currentItem() is not None
        self.btn_compare.setEnabled(has_selection)
        self.btn_correct.setEnabled(has_selection)
        self.btn_wrong.setEnabled(has_selection)

    def set_target_rubbing(self, rubbing: Optional[Dict[str, Any]]):
        self._target_rubbing = rubbing
        if rubbing:
            if not rubbing.get("has_valid_contour"):
                self.info_label.setText(
                    f"当前拓片 [{rubbing.get('code', '')}] 缺少有效轮廓，\n无法参与自动匹配。"
                )
                self.btn_match.setEnabled(False)
            else:
                self.info_label.setText(
                    f"当前拓片: {rubbing.get('code', '')}\n点击「查找相似」开始匹配"
                )
                self.btn_match.setEnabled(True)
        else:
            self.info_label.setText("请选择一个拓片以查找相似拓片")
            self.btn_match.setEnabled(False)
        self._results = []
        self.result_list.clear()
        self.btn_correct.setEnabled(False)
        self.btn_wrong.setEnabled(False)
        self._update_weight_display()

    def _do_match(self):
        if not self._target_rubbing:
            return
        rubbing_id = self._target_rubbing["id"]
        results = self._service.find_similar(rubbing_id, top_k=20)
        self._results = results
        self._populate_results(results)
        self._update_weight_display()

    def _populate_results(self, results: List[Dict[str, Any]]):
        self.result_list.clear()
        if not results:
            self.info_label.setText("未找到相似拓片")
            return
        self.info_label.setText(f"找到 {len(results)} 个相似拓片")

        for item_data in results:
            item_text = (
                f"{item_data.get('code', '')}\n"
                f"相似度: {item_data.get('similarity_score', 0):.1f}%  "
                f"(轮廓: {item_data.get('contour_similarity', 0):.0f}%, "
                f"纹理: {item_data.get('texture_similarity', 0):.0f}%)"
            )
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, item_data)

            rubbing = self._service.get_rubbing(item_data["id"])
            if rubbing:
                img_path = rubbing.get("processed_path") or rubbing.get("original_path")
                if img_path:
                    pixmap = load_pixmap_from_path(img_path, 60, 60)
                    if not pixmap.isNull():
                        item.setIcon(pixmap)

            self.result_list.addItem(item)

    def _on_item_double_clicked(self, item: QListWidgetItem):
        data = item.data(Qt.UserRole)
        if data and self._target_rubbing:
            self.compareRequested.emit(self._target_rubbing["id"], data["id"])

    def _on_compare_clicked(self):
        item = self.result_list.currentItem()
        if item and self._target_rubbing:
            data = item.data(Qt.UserRole)
            self.compareRequested.emit(self._target_rubbing["id"], data["id"])

    def _on_feedback(self, feedback_type: str):
        item = self.result_list.currentItem()
        if not item or not self._target_rubbing:
            return

        data = item.data(Qt.UserRole)
        if not data:
            return

        target_id = data["id"]
        source_id = self._target_rubbing["id"]
        contour_sim = data.get("contour_similarity", 0) / 100.0
        texture_sim = data.get("texture_similarity", 0) / 100.0
        overall_sim = data.get("similarity_score", 0) / 100.0

        try:
            self._service.add_feedback(
                source_rubbing_id=source_id,
                target_rubbing_id=target_id,
                feedback_type=feedback_type,
                contour_similarity=contour_sim,
                texture_similarity=texture_sim,
                overall_similarity=overall_sim,
            )
            msg = "已标记为推荐正确" if feedback_type == "correct" else "已标记为推荐错误"
            QMessageBox.information(self, "反馈成功", msg)
            self.feedbackSubmitted.emit()
            self._update_weight_display()
            self._do_match()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"反馈提交失败: {e}")

    def refresh(self):
        if self._target_rubbing:
            self._do_match()
            self._update_weight_display()
