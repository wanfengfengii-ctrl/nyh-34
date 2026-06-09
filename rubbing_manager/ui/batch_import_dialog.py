from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QTextEdit, QListWidget, QListWidgetItem,
    QMessageBox, QWidget,
)
from PySide6.QtCore import Qt, QThread, Signal
from typing import List, Dict

from ..core.rubbing_service import RubbingService


class ImportWorker(QThread):
    progress = Signal(int, int)
    finished_import = Signal(object)
    error = Signal(str)

    def __init__(self, file_paths: List[str], service: RubbingService):
        super().__init__()
        self._file_paths = file_paths
        self._service = service

    def run(self):
        try:
            def on_progress(current, total):
                self.progress.emit(current, total)
            result = self._service.batch_import(self._file_paths, on_progress)
            self.finished_import.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class BatchImportDialog(QDialog):
    importCompleted = Signal()

    def __init__(self, file_paths: List[str], service: RubbingService, parent=None):
        super().__init__(parent)
        self.setWindowTitle("批量导入")
        self.resize(600, 500)
        self._service = service
        self._file_paths = file_paths
        self._result = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        info_label = QLabel(f"共选择 {len(self._file_paths)} 个文件")
        info_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(info_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, len(self._file_paths))
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("准备开始导入...")
        layout.addWidget(self.status_label)

        self.result_tabs = QWidget()
        result_layout = QVBoxLayout(self.result_tabs)

        self.success_list = QListWidget()
        self.success_list.setVisible(False)
        result_layout.addWidget(QLabel("导入成功:"))
        result_layout.addWidget(self.success_list)

        self.failed_list = QListWidget()
        self.failed_list.setVisible(False)
        result_layout.addWidget(QLabel("导入失败:"))
        result_layout.addWidget(self.failed_list)

        self.dup_list = QListWidget()
        self.dup_list.setVisible(False)
        result_layout.addWidget(QLabel("重复文件:"))
        result_layout.addWidget(self.dup_list)

        layout.addWidget(self.result_tabs, 1)

        btn_row = QHBoxLayout()
        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(self.accept)
        self.btn_close.setEnabled(False)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_close)
        layout.addLayout(btn_row)

    def start_import(self):
        self._worker = ImportWorker(self._file_paths, self._service)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_import.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, current: int, total: int):
        self.progress_bar.setValue(current)
        self.status_label.setText(f"正在导入... ({current}/{total})")

    def _on_finished(self, result):
        self._result = result
        self.progress_bar.setValue(self.progress_bar.maximum())
        self.status_label.setText(
            f"完成：成功 {len(result.success)} 个，"
            f"失败 {len(result.failed)} 个，"
            f"重复 {len(result.duplicates)} 个"
        )

        if result.success:
            self.success_list.setVisible(True)
            for item in result.success:
                list_item = QListWidgetItem(f"{item.get('code', '')} - {item.get('original_path', '')}")
                self.success_list.addItem(list_item)

        if result.failed:
            self.failed_list.setVisible(True)
            for item in result.failed:
                text = f"{item['file_path']}\n  原因: {item['reason']}"
                list_item = QListWidgetItem(text)
                list_item.setForeground(Qt.red)
                self.failed_list.addItem(list_item)

        if result.duplicates:
            self.dup_list.setVisible(True)
            for item in result.duplicates:
                text = f"{item['file_path']}\n  原因: {item['reason']}"
                list_item = QListWidgetItem(text)
                list_item.setForeground(Qt.darkYellow)
                self.dup_list.addItem(list_item)

        self.btn_close.setEnabled(True)
        self.importCompleted.emit()

    def _on_error(self, msg: str):
        QMessageBox.critical(self, "错误", f"导入出错: {msg}")
        self.btn_close.setEnabled(True)

    def accept(self):
        super().accept()
