from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QGroupBox, QTabWidget, QWidget,
    QFormLayout, QDoubleSpinBox, QMessageBox, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView,
)
from PySide6.QtCore import Qt, Signal
from typing import List, Dict, Any, Optional

from ..core.rubbing_service import RubbingService
from ..core.visualization import SimilarityChartCanvas


class FeedbackHistoryDialog(QDialog):
    weightsChanged = Signal()

    def __init__(self, service: RubbingService, parent=None):
        super().__init__(parent)
        self.setWindowTitle("反馈历史与权重管理")
        self.resize(900, 700)
        self._service = service
        self._build_ui()
        self._refresh_all()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        stats_box = QGroupBox("统计概览")
        stats_layout = QHBoxLayout(stats_box)

        self.total_label = QLabel("总反馈数: 0")
        self.total_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        stats_layout.addWidget(self.total_label)

        self.correct_label = QLabel("正确: 0")
        self.correct_label.setStyleSheet("font-size: 14px; color: #2ecc71; font-weight: bold;")
        stats_layout.addWidget(self.correct_label)

        self.wrong_label = QLabel("错误: 0")
        self.wrong_label.setStyleSheet("font-size: 14px; color: #e74c3c; font-weight: bold;")
        stats_layout.addWidget(self.wrong_label)

        self.accuracy_label = QLabel("准确率: —")
        self.accuracy_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        stats_layout.addWidget(self.accuracy_label)

        stats_layout.addStretch()

        self.current_weight_label = QLabel()
        self.current_weight_label.setStyleSheet("font-size: 13px; color: #666;")
        stats_layout.addWidget(self.current_weight_label)

        main_layout.addWidget(stats_box)

        self.tabs = QTabWidget()

        feedback_tab = QWidget()
        feedback_layout = QVBoxLayout(feedback_tab)

        self.feedback_table = QTableWidget()
        self.feedback_table.setColumnCount(6)
        self.feedback_table.setHorizontalHeaderLabels(
            ["时间", "源拓片", "目标拓片", "反馈类型", "相似度", "权重(轮廓/纹理)"]
        )
        self.feedback_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.feedback_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.feedback_table.setEditTriggers(QTableWidget.NoEditTriggers)
        feedback_layout.addWidget(self.feedback_table)

        self.tabs.addTab(feedback_tab, "反馈历史")

        weight_tab = QWidget()
        weight_layout = QVBoxLayout(weight_tab)

        weight_splitter = QSplitter(Qt.Vertical)

        chart_box = QGroupBox("权重变化趋势")
        chart_layout = QVBoxLayout(chart_box)
        self.weight_chart = SimilarityChartCanvas(width=6, height=3)
        chart_layout.addWidget(self.weight_chart)
        weight_splitter.addWidget(chart_box)

        weight_table_box = QGroupBox("权重历史记录")
        weight_table_layout = QVBoxLayout(weight_table_box)
        self.weight_table = QTableWidget()
        self.weight_table.setColumnCount(4)
        self.weight_table.setHorizontalHeaderLabels(
            ["时间", "轮廓权重", "纹理权重", "调整原因"]
        )
        self.weight_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.weight_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.weight_table.setEditTriggers(QTableWidget.NoEditTriggers)
        weight_table_layout.addWidget(self.weight_table)
        weight_splitter.addWidget(weight_table_box)

        weight_splitter.setSizes([200, 200])
        weight_layout.addWidget(weight_splitter)

        self.tabs.addTab(weight_tab, "权重变化")

        main_layout.addWidget(self.tabs, 1)

        control_box = QGroupBox("手动调整权重")
        control_layout = QFormLayout(control_box)

        weight_input_layout = QHBoxLayout()
        self.contour_spin = QDoubleSpinBox()
        self.contour_spin.setRange(0.1, 0.9)
        self.contour_spin.setSingleStep(0.01)
        self.contour_spin.setDecimals(2)
        self.contour_spin.setValue(0.4)
        self.contour_spin.valueChanged.connect(self._on_contour_weight_changed)
        weight_input_layout.addWidget(QLabel("轮廓:"))
        weight_input_layout.addWidget(self.contour_spin, 1)

        self.texture_spin = QDoubleSpinBox()
        self.texture_spin.setRange(0.1, 0.9)
        self.texture_spin.setSingleStep(0.01)
        self.texture_spin.setDecimals(2)
        self.texture_spin.setValue(0.6)
        self.texture_spin.valueChanged.connect(self._on_texture_weight_changed)
        weight_input_layout.addWidget(QLabel("纹理:"))
        weight_input_layout.addWidget(self.texture_spin, 1)

        control_layout.addRow("权重设置:", weight_input_layout)

        btn_layout = QHBoxLayout()
        self.btn_reset = QPushButton("重置为默认")
        self.btn_reset.clicked.connect(self._on_reset_weights)
        self.btn_apply = QPushButton("应用权重")
        self.btn_apply.setStyleSheet("background: #4a90d9; color: white; padding: 6px 16px;")
        self.btn_apply.clicked.connect(self._on_apply_weights)
        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_reset)
        btn_layout.addWidget(self.btn_close)
        btn_layout.addWidget(self.btn_apply)
        control_layout.addRow("", btn_layout)

        main_layout.addWidget(control_box)

    def _refresh_all(self):
        self._refresh_stats()
        self._refresh_feedback_list()
        self._refresh_weight_history()
        self._refresh_weight_inputs()

    def _refresh_stats(self):
        stats = self._service.get_feedback_statistics()
        self.total_label.setText(f"总反馈数: {stats['total']}")
        self.correct_label.setText(f"正确: {stats['correct']}")
        self.wrong_label.setText(f"错误: {stats['wrong']}")
        if stats["total"] > 0:
            self.accuracy_label.setText(f"准确率: {stats['accuracy']:.1f}%")
        else:
            self.accuracy_label.setText("准确率: —")

        contour_w, texture_w = self._service.get_current_weights()
        self.current_weight_label.setText(
            f"当前权重 - 轮廓: {contour_w:.1%} | 纹理: {texture_w:.1%}"
        )

    def _refresh_feedback_list(self):
        feedbacks = self._service.get_feedback_history(limit=200)
        self.feedback_table.setRowCount(len(feedbacks))

        for row, fb in enumerate(feedbacks):
            self.feedback_table.setItem(row, 0, QTableWidgetItem(fb.get("created_at", "")))
            self.feedback_table.setItem(row, 1, QTableWidgetItem(fb.get("source_code", "")))
            self.feedback_table.setItem(row, 2, QTableWidgetItem(fb.get("target_code", "")))

            fb_type = fb.get("feedback_type", "")
            type_text = "✓ 推荐正确" if fb_type == "correct" else "✗ 推荐错误"
            type_item = QTableWidgetItem(type_text)
            if fb_type == "correct":
                type_item.setForeground(Qt.green)
            else:
                type_item.setForeground(Qt.red)
            self.feedback_table.setItem(row, 3, type_item)

            overall = fb.get("overall_similarity", 0) * 100
            self.feedback_table.setItem(row, 4, QTableWidgetItem(f"{overall:.1f}%"))

            cw = fb.get("contour_weight_at_time", 0)
            tw = fb.get("texture_weight_at_time", 0)
            self.feedback_table.setItem(row, 5, QTableWidgetItem(f"{cw:.2f} / {tw:.2f}"))

    def _refresh_weight_history(self):
        history = self._service.get_weight_history(limit=100)
        history.reverse()

        self.weight_table.setRowCount(len(history))
        for row, wh in enumerate(history):
            self.weight_table.setItem(row, 0, QTableWidgetItem(wh.get("created_at", "")))
            self.weight_table.setItem(row, 1, QTableWidgetItem(f"{wh.get('contour_weight', 0):.4f}"))
            self.weight_table.setItem(row, 2, QTableWidgetItem(f"{wh.get('texture_weight', 0):.4f}"))
            self.weight_table.setItem(row, 3, QTableWidgetItem(wh.get("adjustment_reason", "")))

        self._plot_weight_chart(history)

    def _plot_weight_chart(self, history: List[Dict[str, Any]]):
        if not history:
            self.weight_chart.axes.clear()
            self.weight_chart.axes.text(
                0.5, 0.5, "暂无权重历史数据",
                ha="center", va="center", transform=self.weight_chart.axes.transAxes
            )
            self.weight_chart.draw()
            return

        x = list(range(len(history)))
        contour_weights = [h.get("contour_weight", 0) for h in history]
        texture_weights = [h.get("texture_weight", 0) for h in history]

        self.weight_chart.axes.clear()
        self.weight_chart.axes.plot(
            x, contour_weights, "o-",
            label="轮廓权重", linewidth=2, color="#3498db"
        )
        self.weight_chart.axes.plot(
            x, texture_weights, "s-",
            label="纹理权重", linewidth=2, color="#e74c3c"
        )
        self.weight_chart.axes.fill_between(
            x, contour_weights, texture_weights,
            alpha=0.1, color="#95a5a6"
        )
        self.weight_chart.axes.set_title("权重变化趋势")
        self.weight_chart.axes.set_xlabel("调整次数")
        self.weight_chart.axes.set_ylabel("权重值")
        self.weight_chart.axes.set_ylim(0, 1)
        self.weight_chart.axes.legend()
        self.weight_chart.axes.grid(True, alpha=0.3)
        self.weight_chart.fig.tight_layout()
        self.weight_chart.draw()

    def _refresh_weight_inputs(self):
        contour_w, texture_w = self._service.get_current_weights()
        self.contour_spin.blockSignals(True)
        self.texture_spin.blockSignals(True)
        self.contour_spin.setValue(round(contour_w, 2))
        self.texture_spin.setValue(round(texture_w, 2))
        self.contour_spin.blockSignals(False)
        self.texture_spin.blockSignals(False)

    def _on_contour_weight_changed(self, value: float):
        self.texture_spin.blockSignals(True)
        self.texture_spin.setValue(round(1.0 - value, 2))
        self.texture_spin.blockSignals(False)

    def _on_texture_weight_changed(self, value: float):
        self.contour_spin.blockSignals(True)
        self.contour_spin.setValue(round(1.0 - value, 2))
        self.contour_spin.blockSignals(False)

    def _on_apply_weights(self):
        contour_w = self.contour_spin.value()
        texture_w = self.texture_spin.value()

        if abs(contour_w + texture_w - 1.0) > 0.01:
            total = contour_w + texture_w
            contour_w = contour_w / total
            texture_w = texture_w / total

        reply = QMessageBox.question(
            self, "确认调整",
            f"确定要将权重设置为\n轮廓: {contour_w:.2%}, 纹理: {texture_w:.2%} 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            self._service.set_weights_manually(contour_w, texture_w, reason="手动调整")
            self.weightsChanged.emit()
            self._refresh_all()
            QMessageBox.information(self, "成功", "权重已更新")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"权重设置失败: {e}")

    def _on_reset_weights(self):
        reply = QMessageBox.question(
            self, "确认重置",
            "确定要将权重重置为默认值\n(轮廓: 40%, 纹理: 60%)吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        try:
            self._service.reset_weights_to_default()
            self.weightsChanged.emit()
            self._refresh_all()
            QMessageBox.information(self, "成功", "权重已重置为默认值")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"权重重置失败: {e}")
