from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QGroupBox, QFormLayout,
    QComboBox, QMessageBox, QSplitter, QWidget,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QColor
from typing import List, Dict, Any, Optional

from ..core.rubbing_service import RubbingService
from ..db.database import ComparisonDAO
from ..core.visualization import SimilarityChartCanvas
from .utils import load_pixmap_from_path
from .compare_dialog import CompareDialog


CONCLUSION_LABELS = {
    ComparisonDAO.CONCLUSION_UNCONFIRMED: "待确认",
    ComparisonDAO.CONCLUSION_SAME_EDITION: "同版",
    ComparisonDAO.CONCLUSION_SUSPECTED_FORGERY: "疑似仿品",
    ComparisonDAO.CONCLUSION_DIFFERENT: "不同版",
}

CONCLUSION_COLORS = {
    ComparisonDAO.CONCLUSION_UNCONFIRMED: "#95a5a6",
    ComparisonDAO.CONCLUSION_SAME_EDITION: "#2ecc71",
    ComparisonDAO.CONCLUSION_SUSPECTED_FORGERY: "#e74c3c",
    ComparisonDAO.CONCLUSION_DIFFERENT: "#3498db",
}


class ComparisonHistoryDialog(QDialog):
    comparisonUpdated = Signal()

    def __init__(
        self,
        service: RubbingService,
        rubbing_id: Optional[int] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("对比记录")
        self.resize(900, 600)
        self._service = service
        self._rubbing_id = rubbing_id
        self._comparisons: List[Dict[str, Any]] = []
        self._selected = None
        self._build_ui()
        self._load_comparisons()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("结论筛选:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("全部", "")
        for label, value in CONCLUSION_LABELS.items():
            self.filter_combo.addItem(label, value)
        self.filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_layout.addWidget(self.filter_combo)
        left_layout.addLayout(filter_layout)

        self.comp_list = QListWidget()
        self.comp_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.comp_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        left_layout.addWidget(self.comp_list, 1)

        count_label = QLabel()
        self.count_label = count_label
        left_layout.addWidget(count_label)

        splitter.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        detail_box = QGroupBox("详情")
        detail_layout = QFormLayout(detail_box)

        self.code_a_label = QLabel("—")
        self.code_b_label = QLabel("—")
        self.sim_label = QLabel("—")
        self.conclusion_label = QLabel("—")
        self.notes_label = QLabel("—")
        self.notes_label.setWordWrap(True)

        detail_layout.addRow("拓片A:", self.code_a_label)
        detail_layout.addRow("拓片B:", self.code_b_label)
        detail_layout.addRow("综合相似度:", self.sim_label)
        detail_layout.addRow("结论:", self.conclusion_label)
        detail_layout.addRow("备注:", self.notes_label)

        right_layout.addWidget(detail_box)

        self.chart = SimilarityChartCanvas(width=4, height=3)
        right_layout.addWidget(self.chart, 1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_view = QPushButton("查看对比")
        self.btn_view.clicked.connect(self._on_view_comparison)
        self.btn_view.setEnabled(False)
        btn_layout.addWidget(self.btn_view)
        right_layout.addLayout(btn_layout)

        splitter.addWidget(right_panel)
        splitter.setSizes([350, 550])

        main_layout.addWidget(splitter, 1)

        close_layout = QHBoxLayout()
        close_layout.addStretch()
        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(self.accept)
        close_layout.addWidget(self.btn_close)
        main_layout.addLayout(close_layout)

    def _load_comparisons(self):
        if self._rubbing_id is not None:
            self._comparisons = self._service.get_comparisons_for_rubbing(
                self._rubbing_id
            )
        else:
            self._comparisons = ComparisonDAO.list_all()

        self._apply_filter()

    def _apply_filter(self):
        filter_val = self.filter_combo.currentData()
        self.comp_list.clear()

        filtered = self._comparisons
        if filter_val:
            filtered = [c for c in self._comparisons if c.get("conclusion") == filter_val]

        for comp in filtered:
            code_a = comp.get("code_a", "?")
            code_b = comp.get("code_b", "?")
            score = comp.get("similarity_score", 0)
            conclusion = comp.get("conclusion", ComparisonDAO.CONCLUSION_UNCONFIRMED)
            conclusion_text = CONCLUSION_LABELS.get(conclusion, "未知")

            text = f"{code_a}  ↔  {code_b}\n相似度: {score:.1f}%  [{conclusion_text}]"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, comp)

            color = CONCLUSION_COLORS.get(conclusion, "#000")
            item.setForeground(QColor(color))
            if conclusion != ComparisonDAO.CONCLUSION_UNCONFIRMED:
                f = item.font()
                f.setBold(True)
                item.setFont(f)

            self.comp_list.addItem(item)

        self.count_label.setText(f"共 {len(filtered)} 条对比记录")
        self._selected = None
        self._update_detail()

    def _on_filter_changed(self):
        self._apply_filter()

    def _on_selection_changed(self):
        items = self.comp_list.selectedItems()
        if items:
            self._selected = items[0].data(Qt.UserRole)
            self.btn_view.setEnabled(True)
        else:
            self._selected = None
            self.btn_view.setEnabled(False)
        self._update_detail()

    def _update_detail(self):
        if not self._selected:
            self.code_a_label.setText("—")
            self.code_b_label.setText("—")
            self.sim_label.setText("—")
            self.conclusion_label.setText("—")
            self.notes_label.setText("—")
            self.chart.clear()
            return

        comp = self._selected
        self.code_a_label.setText(comp.get("code_a", "—"))
        self.code_b_label.setText(comp.get("code_b", "—"))
        self.sim_label.setText(f"{comp.get('similarity_score', 0):.1f}%")

        conclusion = comp.get("conclusion", ComparisonDAO.CONCLUSION_UNCONFIRMED)
        conclusion_text = CONCLUSION_LABELS.get(conclusion, "未知")
        color = CONCLUSION_COLORS.get(conclusion, "#000")
        self.conclusion_label.setText(
            f'<span style="color: {color}; font-weight: bold;">{conclusion_text}</span>'
        )

        self.notes_label.setText(comp.get("notes", "—") or "—")

        overall = comp.get("similarity_score", 0)
        contour = comp.get("contour_similarity", 0) or 0
        texture = comp.get("texture_similarity", 0) or 0
        self.chart.plot_similarity_bar(
            labels=["综合", "轮廓", "纹理"],
            scores=[overall, contour, texture],
            title="相似度分析",
        )

    def _on_item_double_clicked(self, item: QListWidgetItem):
        self._on_view_comparison()

    def _on_view_comparison(self):
        if not self._selected:
            return
        comp = self._selected
        rubbing_a = self._service.get_rubbing(comp["rubbing_a_id"])
        rubbing_b = self._service.get_rubbing(comp["rubbing_b_id"])
        if not rubbing_a or not rubbing_b:
            QMessageBox.warning(self, "提示", "拓片数据不存在")
            return

        sim_data = {
            "similarity_score": comp.get("similarity_score", 0),
            "contour_similarity": comp.get("contour_similarity", 0),
            "texture_similarity": comp.get("texture_similarity", 0),
        }
        dialog = CompareDialog(
            rubbing_a, rubbing_b, sim_data, self._service, self,
            existing_comparison=comp,
        )
        dialog.comparisonSaved.connect(self._on_comparison_updated)
        dialog.exec()

    def _on_comparison_updated(self):
        self._load_comparisons()
        self.comparisonUpdated.emit()
