from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QComboBox, QGroupBox, QFormLayout, QListWidget,
    QListWidgetItem, QSplitter, QWidget, QMessageBox, QTabWidget,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from typing import List, Dict, Any, Optional

from ..core.rubbing_service import RubbingService
from ..core.visualization import SimilarityChartCanvas
from ..db.database import ComparisonDAO, blob_to_array
from .utils import load_pixmap_from_path


CONCLUSION_OPTIONS = [
    ("待确认", ComparisonDAO.CONCLUSION_UNCONFIRMED),
    ("同版", ComparisonDAO.CONCLUSION_SAME_EDITION),
    ("疑似仿品", ComparisonDAO.CONCLUSION_SUSPECTED_FORGERY),
    ("不同版", ComparisonDAO.CONCLUSION_DIFFERENT),
]


class CompareDialog(QDialog):
    comparisonSaved = Signal()

    def __init__(
        self,
        rubbing_a: Dict[str, Any],
        rubbing_b: Dict[str, Any],
        similarity_data: Dict[str, Any],
        service: RubbingService,
        parent=None,
        existing_comparison: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("拓片对比")
        self.resize(1200, 800)
        self._rubbing_a = rubbing_a
        self._rubbing_b = rubbing_b
        self._similarity = similarity_data
        self._service = service
        self._existing = existing_comparison
        self._build_ui()
        self._load_images()
        self._load_charts()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Vertical)

        compare_widget = QWidget()
        compare_layout = QHBoxLayout(compare_widget)

        left_panel = self._build_rubbing_panel(self._rubbing_a, "A")
        right_panel = self._build_rubbing_panel(self._rubbing_b, "B")

        compare_layout.addWidget(left_panel, 1)
        compare_layout.addWidget(right_panel, 1)

        splitter.addWidget(compare_widget)

        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)

        self.tabs = QTabWidget()

        score_tab = QWidget()
        score_layout = QVBoxLayout(score_tab)

        score_box = QGroupBox("相似度分析")
        score_form = QFormLayout(score_box)

        overall = self._similarity.get("similarity_score", 0)
        contour = self._similarity.get("contour_similarity", 0)
        texture = self._similarity.get("texture_similarity", 0)

        score_form.addRow(
            "综合相似度:",
            QLabel(f'<span style="font-size: 20px; font-weight: bold; '
                   f'color: {"#2ecc71" if overall >= 70 else "#f39c12" if overall >= 40 else "#e74c3c"};">'
                   f'{overall:.1f}%</span>')
        )
        score_form.addRow("轮廓相似度:", QLabel(f"{contour:.1f}%"))
        score_form.addRow("纹理相似度:", QLabel(f"{texture:.1f}%"))

        score_layout.addWidget(score_box)

        self.chart_bar = SimilarityChartCanvas(width=5, height=3)
        score_layout.addWidget(self.chart_bar)

        self.tabs.addTab(score_tab, "相似度")

        feature_tab = QWidget()
        feature_layout = QVBoxLayout(feature_tab)
        self.chart_contour = SimilarityChartCanvas(width=5, height=3)
        feature_layout.addWidget(QLabel("轮廓特征对比:"))
        feature_layout.addWidget(self.chart_contour)
        self.chart_texture = SimilarityChartCanvas(width=5, height=3)
        feature_layout.addWidget(QLabel("纹理特征对比:"))
        feature_layout.addWidget(self.chart_texture)
        self.tabs.addTab(feature_tab, "特征分析")

        conclusion_box = QGroupBox("对比结论")
        conclusion_layout = QFormLayout(conclusion_box)

        self.conclusion_combo = QComboBox()
        for label, value in CONCLUSION_OPTIONS:
            self.conclusion_combo.addItem(label, value)
        if self._existing:
            for i in range(self.conclusion_combo.count()):
                if self.conclusion_combo.itemData(i) == self._existing.get("conclusion"):
                    self.conclusion_combo.setCurrentIndex(i)
                    break
        conclusion_layout.addRow("结论:", self.conclusion_combo)

        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("填写备注信息...")
        self.notes_edit.setMaximumHeight(80)
        if self._existing:
            self.notes_edit.setPlainText(self._existing.get("notes", ""))
        conclusion_layout.addRow("备注:", self.notes_edit)

        bottom_layout.addWidget(self.tabs, 1)
        bottom_layout.addWidget(conclusion_box)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_cancel = QPushButton("关闭")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save = QPushButton("保存结论")
        self.btn_save.clicked.connect(self._save_conclusion)
        self.btn_save.setStyleSheet("background: #4a90d9; color: white; padding: 6px 16px;")
        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_save)
        bottom_layout.addLayout(btn_row)

        splitter.addWidget(bottom_widget)
        splitter.setSizes([450, 350])

        main_layout.addWidget(splitter, 1)

    def _build_rubbing_panel(self, rubbing: Dict[str, Any], label: str) -> QWidget:
        panel = QGroupBox(f"拓片 {label} - {rubbing.get('code', '')}")
        layout = QVBoxLayout(panel)

        self.image_labels = getattr(self, "image_labels", {})
        img_label = QLabel()
        img_label.setAlignment(Qt.AlignCenter)
        img_label.setMinimumSize(300, 300)
        img_label.setStyleSheet("border: 1px solid #ddd; background: #fafafa;")
        img_label_name = f"img_{label.lower()}"
        self.image_labels[img_label_name] = img_label
        layout.addWidget(img_label, 1)

        info_layout = QFormLayout()
        info_layout.addRow("编号:", QLabel(rubbing.get("code", "")))
        info_layout.addRow("年代:", QLabel(rubbing.get("era", "—")))
        info_layout.addRow("钱文:", QLabel(rubbing.get("inscription", "—")))
        info_layout.addRow("材质:", QLabel(rubbing.get("material", "—")))
        info_layout.addRow("出土地:", QLabel(rubbing.get("excavation_site", "—")))
        info_layout.addRow(
            "有效轮廓:",
            QLabel("是" if rubbing.get("has_valid_contour") else "否")
        )
        layout.addLayout(info_layout)

        return panel

    def _load_images(self):
        path_a = self._rubbing_a.get("processed_path") or self._rubbing_a.get("original_path")
        path_b = self._rubbing_b.get("processed_path") or self._rubbing_b.get("original_path")

        if path_a:
            pixmap = load_pixmap_from_path(path_a, 400, 400)
            self.image_labels["img_a"].setPixmap(pixmap)
        if path_b:
            pixmap = load_pixmap_from_path(path_b, 400, 400)
            self.image_labels["img_b"].setPixmap(pixmap)

    def _load_charts(self):
        overall = self._similarity.get("similarity_score", 0)
        contour = self._similarity.get("contour_similarity", 0)
        texture = self._similarity.get("texture_similarity", 0)

        self.chart_bar.plot_similarity_bar(
            labels=["综合相似度", "轮廓相似度", "纹理相似度"],
            scores=[overall, contour, texture],
            title="相似度分析",
        )

        feat_a_contour = blob_to_array(self._rubbing_a.get("contour_feature"))
        feat_b_contour = blob_to_array(self._rubbing_b.get("contour_feature"))
        if feat_a_contour is not None and feat_b_contour is not None:
            min_len = min(len(feat_a_contour), len(feat_b_contour))
            self.chart_contour.plot_feature_comparison(
                feat_a_contour[:min_len],
                feat_b_contour[:min_len],
                title="轮廓特征向量对比",
            )
        else:
            self.chart_contour.axes.text(
                0.5, 0.5, "无轮廓特征数据",
                ha="center", va="center", transform=self.chart_contour.axes.transAxes
            )
            self.chart_contour.draw()

        feat_a_tex = blob_to_array(self._rubbing_a.get("texture_feature"))
        feat_b_tex = blob_to_array(self._rubbing_b.get("texture_feature"))
        if feat_a_tex is not None and feat_b_tex is not None:
            min_len = min(len(feat_a_tex), len(feat_b_tex))
            self.chart_texture.plot_feature_comparison(
                feat_a_tex[:min_len],
                feat_b_tex[:min_len],
                title="纹理特征向量对比",
            )
        else:
            self.chart_texture.axes.text(
                0.5, 0.5, "无纹理特征数据",
                ha="center", va="center", transform=self.chart_texture.axes.transAxes
            )
            self.chart_texture.draw()

    def _save_conclusion(self):
        conclusion = self.conclusion_combo.currentData()
        notes = self.notes_edit.toPlainText()

        if self._existing:
            ComparisonDAO.update(self._existing["id"], {
                "conclusion": conclusion,
                "notes": notes,
            })
        else:
            data = {
                "rubbing_a_id": self._rubbing_a["id"],
                "rubbing_b_id": self._rubbing_b["id"],
                "similarity_score": self._similarity.get("similarity_score", 0),
                "contour_similarity": self._similarity.get("contour_similarity", 0),
                "texture_similarity": self._similarity.get("texture_similarity", 0),
                "conclusion": conclusion,
                "notes": notes,
            }
            ComparisonDAO.create(data)

        QMessageBox.information(self, "成功", "对比结论已保存")
        self.comparisonSaved.emit()
        self.accept()
