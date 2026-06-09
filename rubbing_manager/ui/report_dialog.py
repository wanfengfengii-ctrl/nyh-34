from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
    QLabel, QTextBrowser, QFileDialog, QMessageBox, QGroupBox,
    QFormLayout, QCheckBox, QProgressDialog, QListWidget,
    QListWidgetItem, QSplitter, QWidget, QLineEdit,
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QPixmap
from typing import Optional, Dict, Any, List
import os
import tempfile

from ..core.rubbing_service import RubbingService
from ..core.report_generator import ReportGenerator
from .edition_graph_widget import EditionGraphWidget


class ReportDialog(QDialog):
    reportExported = Signal(str)

    def __init__(
        self,
        service: RubbingService,
        mode: str = "single",
        rubbing_id: Optional[int] = None,
        group_id: Optional[int] = None,
        rubbing_ids: Optional[List[int]] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._service = service
        self._generator = ReportGenerator(service)
        self._current_report: Optional[Dict[str, Any]] = None
        self._graph_temp_path: Optional[str] = None
        self._mode = mode
        self._initial_rubbing_id = rubbing_id
        self._initial_group_id = group_id
        self._initial_rubbing_ids = rubbing_ids or []

        self.setWindowTitle("研究报告导出")
        self.resize(1000, 700)
        self._build_ui()
        self._init_mode()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        setting_box = QGroupBox("报告设置")
        form = QFormLayout(setting_box)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("单张拓片报告", "single")
        self.mode_combo.addItem("版别组报告", "group")
        self.mode_combo.addItem("批量拓片报告", "batch")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        form.addRow("报告类型:", self.mode_combo)

        self.target_widget = QWidget()
        self.target_layout = QHBoxLayout(self.target_widget)
        self.target_layout.setContentsMargins(0, 0, 0, 0)
        form.addRow("选择对象:", self.target_widget)

        self.include_graph_cb = QCheckBox("包含版别关系图谱")
        self.include_graph_cb.setChecked(True)
        form.addRow("图谱选项:", self.include_graph_cb)

        layout.addWidget(setting_box)

        splitter = QSplitter(Qt.Vertical)

        self.preview_label = QLabel("报告预览")
        self.preview_label.setStyleSheet("font-weight: bold; padding: 4px;")

        self.preview_browser = QTextBrowser()
        self.preview_browser.setOpenExternalLinks(False)
        splitter.addWidget(self.preview_browser)

        btn_layout = QHBoxLayout()

        self.btn_generate = QPushButton("生成预览")
        self.btn_generate.clicked.connect(self._on_generate_preview)
        btn_layout.addWidget(self.btn_generate)

        btn_layout.addStretch()

        self.btn_export_pdf = QPushButton("导出 PDF")
        self.btn_export_pdf.clicked.connect(self._on_export_pdf)
        self.btn_export_pdf.setEnabled(False)
        btn_layout.addWidget(self.btn_export_pdf)

        self.btn_export_zip = QPushButton("导出图片归档包")
        self.btn_export_zip.clicked.connect(self._on_export_zip)
        self.btn_export_zip.setEnabled(False)
        btn_layout.addWidget(self.btn_export_zip)

        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)

        layout.addWidget(self.preview_label)
        layout.addWidget(splitter, 1)
        layout.addLayout(btn_layout)

    def _init_mode(self):
        mode_map = {
            "single": 0,
            "group": 1,
            "batch": 2,
        }
        idx = mode_map.get(self._mode, 0)
        self.mode_combo.setCurrentIndex(idx)
        self._on_mode_changed(idx)

        if self._mode == "single" and self._initial_rubbing_id:
            if hasattr(self, "rubbing_combo"):
                idx = self.rubbing_combo.findData(self._initial_rubbing_id)
                if idx >= 0:
                    self.rubbing_combo.setCurrentIndex(idx)
        elif self._mode == "group" and self._initial_group_id:
            if hasattr(self, "group_combo"):
                idx = self.group_combo.findData(self._initial_group_id)
                if idx >= 0:
                    self.group_combo.setCurrentIndex(idx)
        elif self._mode == "batch" and self._initial_rubbing_ids:
            if hasattr(self, "rubbing_list"):
                for i in range(self.rubbing_list.count()):
                    item = self.rubbing_list.item(i)
                    if item.data(Qt.UserRole) in self._initial_rubbing_ids:
                        item.setSelected(True)
                self._update_batch_count()

    def _on_mode_changed(self, index: int):
        mode = self.mode_combo.itemData(index)
        self._clear_target_widget()

        if mode == "single":
            self._build_single_target()
        elif mode == "group":
            self._build_group_target()
        elif mode == "batch":
            self._build_batch_target()

        self._current_report = None
        self.btn_export_pdf.setEnabled(False)
        self.btn_export_zip.setEnabled(False)
        self.preview_browser.clear()

    def _clear_target_widget(self):
        while self.target_layout.count():
            item = self.target_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _build_single_target(self):
        self.rubbing_combo = QComboBox()
        rubbings = self._service.list_rubbings()
        for r in rubbings:
            self.rubbing_combo.addItem(
                f"{r.get('code', '')} - {r.get('inscription', '—')}",
                r.get("id"),
            )
        self.target_layout.addWidget(self.rubbing_combo)

    def _build_group_target(self):
        self.group_combo = QComboBox()
        groups = self._service.list_edition_groups()
        for g in groups:
            self.group_combo.addItem(
                f"{g.get('name', '')} ({g.get('member_count', 0)}成员)",
                g.get("id"),
            )
        self.target_layout.addWidget(self.group_combo)

    def _build_batch_target(self):
        batch_widget = QWidget()
        batch_layout = QVBoxLayout(batch_widget)
        batch_layout.setContentsMargins(0, 0, 0, 0)

        btn_row = QHBoxLayout()
        self.btn_select_all = QPushButton("全选")
        self.btn_select_all.clicked.connect(self._on_select_all)
        self.btn_select_none = QPushButton("全不选")
        self.btn_select_none.clicked.connect(self._on_select_none)
        btn_row.addWidget(self.btn_select_all)
        btn_row.addWidget(self.btn_select_none)
        btn_row.addStretch()
        self.batch_count_label = QLabel("已选择: 0 个")
        btn_row.addWidget(self.batch_count_label)
        batch_layout.addLayout(btn_row)

        self.rubbing_list = QListWidget()
        self.rubbing_list.setSelectionMode(QListWidget.MultiSelection)
        rubbings = self._service.list_rubbings()
        for r in rubbings:
            item = QListWidgetItem(
                f"{r.get('code', '')} - {r.get('inscription', '—')} - {r.get('era', '—')}"
            )
            item.setData(Qt.UserRole, r.get("id"))
            self.rubbing_list.addItem(item)
        self.rubbing_list.itemSelectionChanged.connect(self._update_batch_count)
        batch_layout.addWidget(self.rubbing_list, 1)

        self.target_layout.addWidget(batch_widget, 1)

    def _on_select_all(self):
        self.rubbing_list.selectAll()

    def _on_select_none(self):
        self.rubbing_list.clearSelection()

    def _update_batch_count(self):
        count = len(self.rubbing_list.selectedItems())
        self.batch_count_label.setText(f"已选择: {count} 个")

    def _on_generate_preview(self):
        mode = self.mode_combo.currentData()
        include_graph = self.include_graph_cb.isChecked()

        progress = QProgressDialog("正在生成报告...", None, 0, 0, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()

        try:
            if mode == "single":
                rubbing_id = self.rubbing_combo.currentData()
                if not rubbing_id:
                    QMessageBox.warning(self, "提示", "请选择一个拓片")
                    progress.close()
                    return
                report = self._generator.generate_single_report(rubbing_id)
                if include_graph:
                    self._add_graph_to_single_report(report, rubbing_id)

            elif mode == "group":
                group_id = self.group_combo.currentData()
                if not group_id:
                    QMessageBox.warning(self, "提示", "请选择一个版别组")
                    progress.close()
                    return
                report = self._generator.generate_group_report(group_id)
                if include_graph:
                    self._add_graph_to_group_report(report, group_id)

            elif mode == "batch":
                selected = self.rubbing_list.selectedItems()
                if not selected:
                    QMessageBox.warning(self, "提示", "请至少选择一个拓片")
                    progress.close()
                    return
                ids = [item.data(Qt.UserRole) for item in selected]
                report = self._generator.generate_batch_report(
                    ids, title=f"批量研究报告 ({len(ids)}张)"
                )
                if include_graph:
                    self._add_graph_to_batch_report(report, ids)

            else:
                progress.close()
                return

            self._current_report = report
            html = self._generator.render_html(report)
            self.preview_browser.setHtml(html)
            self.btn_export_pdf.setEnabled(True)
            self.btn_export_zip.setEnabled(True)

        except Exception as e:
            QMessageBox.critical(self, "错误", f"生成报告失败: {e}")
        finally:
            progress.close()

    def _add_graph_to_single_report(self, report: Dict[str, Any], rubbing_id: int):
        groups = self._service.get_edition_groups_for_rubbing(rubbing_id)
        if groups:
            graph_img = self._render_graph_for_group(groups[0]["id"])
            if graph_img:
                report["graph_image_path"] = graph_img

    def _add_graph_to_group_report(self, report: Dict[str, Any], group_id: int):
        graph_img = self._render_graph_for_group(group_id)
        if graph_img:
            report["graph_image_path"] = graph_img

    def _add_graph_to_batch_report(self, report: Dict[str, Any], rubbing_ids: List[int]):
        pass

    def _render_graph_for_group(self, group_id: int) -> Optional[str]:
        try:
            graph_widget = EditionGraphWidget(self._service)
            graph_widget.refresh()
            graph_widget.focus_on_group(group_id)
            graph_widget.resize(800, 600)

            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, lambda: None)

            pixmap = graph_widget.grab_graph_image()
            if pixmap and not pixmap.isNull():
                tmp_path = os.path.join(
                    tempfile.gettempdir(),
                    f"graph_{group_id}_{os.getpid()}.png"
                )
                pixmap.save(tmp_path, "PNG")
                self._graph_temp_path = tmp_path
                return tmp_path
        except Exception as e:
            print(f"图谱渲染失败: {e}")
        return None

    def _on_export_pdf(self):
        if not self._current_report:
            return

        default_name = self._current_report.get("title", "研究报告").replace(" ", "_")
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出 PDF 报告",
            f"{default_name}.pdf",
            "PDF 文件 (*.pdf)",
        )
        if not file_path:
            return

        try:
            success = self._generator.export_pdf(self._current_report, file_path)
            if success:
                QMessageBox.information(self, "成功", f"PDF 报告已导出:\n{file_path}")
                self.reportExported.emit(file_path)
            else:
                QMessageBox.critical(self, "失败", "PDF 导出失败，请重试")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败: {e}")

    def _on_export_zip(self):
        if not self._current_report:
            return

        default_name = self._current_report.get("title", "研究报告").replace(" ", "_")
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出图片归档包",
            f"{default_name}.zip",
            "ZIP 归档 (*.zip)",
        )
        if not file_path:
            return

        try:
            success = self._generator.export_image_package(
                self._current_report, file_path, include_original=True
            )
            if success:
                QMessageBox.information(
                    self, "成功",
                    f"图片归档包已导出:\n{file_path}\n\n"
                    "包含: 拓片图片、信息文本、相似数据、对比记录等"
                )
                self.reportExported.emit(file_path)
            else:
                QMessageBox.critical(self, "失败", "归档包导出失败，请重试")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出失败: {e}")

    def closeEvent(self, event):
        self._cleanup_temp_files()
        super().closeEvent(event)

    def _cleanup_temp_files(self):
        if self._graph_temp_path and os.path.exists(self._graph_temp_path):
            try:
                os.unlink(self._graph_temp_path)
            except Exception:
                pass
            self._graph_temp_path = None
