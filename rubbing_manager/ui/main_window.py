from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QToolBar, QStatusBar, QFileDialog,
    QLineEdit, QLabel, QPushButton, QMessageBox, QInputDialog,
    QComboBox, QGroupBox, QFormLayout, QCheckBox, QCompleter,
)
from PySide6.QtCore import QStringListModel
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QIcon, QPixmap
from typing import Optional, Dict, Any, List

from ..core.rubbing_service import RubbingService
from ..db.database import init_db
from .detail_panel import DetailPanel
from .similarity_panel import SimilarityPanel
from .image_editor_dialog import ImageEditorDialog
from .compare_dialog import CompareDialog
from .batch_import_dialog import BatchImportDialog
from .comparison_history_dialog import ComparisonHistoryDialog
from .feedback_history_dialog import FeedbackHistoryDialog
from .edition_manager_dialog import EditionManagerDialog
from .utils import load_pixmap_from_path


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        init_db()
        self._service = RubbingService()
        self._current_rubbing: Optional[Dict[str, Any]] = None
        self._rubbings: List[Dict[str, Any]] = []
        self.setWindowTitle("古钱币拓片管理系统")
        self.resize(1200, 800)
        self._build_ui()
        self._build_toolbar()
        self._build_statusbar()
        self._load_rubbings()
        self._update_eras()
        self._update_materials()
        self._update_excavation_sites()
        self._update_inscription_completer()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)

        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("模糊搜索编号/钱文/出土地/材质...")
        self.search_edit.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_edit)
        left_layout.addLayout(search_layout)

        self.advanced_filter_btn = QPushButton("▼ 高级筛选")
        self.advanced_filter_btn.setCheckable(True)
        self.advanced_filter_btn.toggled.connect(self._toggle_advanced_filters)
        left_layout.addWidget(self.advanced_filter_btn)

        self.advanced_filter_widget = QWidget()
        advanced_layout = QVBoxLayout(self.advanced_filter_widget)
        advanced_layout.setContentsMargins(0, 0, 0, 0)

        filter_form = QFormLayout()

        self.era_filter = QComboBox()
        self.era_filter.addItem("全部", "")
        self.era_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_form.addRow("年代:", self.era_filter)

        self.material_filter = QComboBox()
        self.material_filter.addItem("全部", "")
        self.material_filter.setEditable(True)
        self.material_filter.currentIndexChanged.connect(self._on_filter_changed)
        self.material_filter.editTextChanged.connect(self._on_filter_changed)
        filter_form.addRow("材质:", self.material_filter)

        self.inscription_filter = QLineEdit()
        self.inscription_filter.setPlaceholderText("钱文模糊搜索...")
        self.inscription_filter.textChanged.connect(self._on_filter_changed)
        self.inscription_completer = QCompleter([], self.inscription_filter)
        self.inscription_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.inscription_completer.setFilterMode(Qt.MatchContains)
        self.inscription_completer.setCompletionMode(QCompleter.PopupCompletion)
        self.inscription_filter.setCompleter(self.inscription_completer)
        filter_form.addRow("钱文:", self.inscription_filter)

        self.excavation_filter = QComboBox()
        self.excavation_filter.addItem("全部", "")
        self.excavation_filter.setEditable(True)
        self.excavation_filter.currentIndexChanged.connect(self._on_filter_changed)
        self.excavation_filter.editTextChanged.connect(self._on_filter_changed)
        filter_form.addRow("出土地:", self.excavation_filter)

        advanced_layout.addLayout(filter_form)

        sort_layout = QHBoxLayout()
        sort_layout.addWidget(QLabel("排序:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("创建时间", "created_at")
        self.sort_combo.addItem("编号", "code")
        self.sort_combo.addItem("年代", "era")
        self.sort_combo.addItem("钱文", "inscription")
        self.sort_combo.addItem("材质", "material")
        self.sort_combo.currentIndexChanged.connect(self._on_filter_changed)
        sort_layout.addWidget(self.sort_combo, 1)

        self.sort_order_btn = QPushButton("降序 ↓")
        self.sort_order_btn.setCheckable(True)
        self.sort_order_btn.setChecked(True)
        self.sort_order_btn.toggled.connect(self._on_sort_order_changed)
        sort_layout.addWidget(self.sort_order_btn)
        advanced_layout.addLayout(sort_layout)

        self.contour_only_cb = QCheckBox("仅显示有有效轮廓")
        self.contour_only_cb.toggled.connect(self._on_filter_changed)
        advanced_layout.addWidget(self.contour_only_cb)

        self.advanced_filter_widget.setVisible(False)
        left_layout.addWidget(self.advanced_filter_widget)

        self.rubbing_list = QListWidget()
        self.rubbing_list.setIconSize(QSize(72, 72))
        self.rubbing_list.setUniformItemSizes(True)
        self.rubbing_list.setGridSize(QSize(0, 80))
        self.rubbing_list.itemSelectionChanged.connect(
            self._on_rubbing_selected
        )
        self.rubbing_list.itemDoubleClicked.connect(self._on_rubbing_double_clicked)
        left_layout.addWidget(self.rubbing_list, 1)

        count_label = QLabel()
        self.count_label = count_label
        left_layout.addWidget(count_label)

        splitter.addWidget(left_panel)

        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        self.detail_panel = DetailPanel(self._service)
        self.detail_panel.dataChanged.connect(self._on_detail_changed)
        self.detail_panel.editImageRequested.connect(self._on_edit_image)
        self.detail_panel.deleteRequested.connect(self._on_rubbing_deleted)
        self.detail_panel.findSimilarRequested.connect(self._on_find_similar)
        self.detail_panel.viewComparisonsRequested.connect(self._on_view_comparisons)
        self.detail_panel.viewEditionGraphRequested.connect(self._on_view_edition_graph_from_detail)
        self.detail_panel.editionGroupChanged.connect(self._on_edition_group_changed)
        center_layout.addWidget(self.detail_panel, 1)
        splitter.addWidget(center_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.similarity_panel = SimilarityPanel(self._service)
        self.similarity_panel.compareRequested.connect(self._on_compare_requested)
        self.similarity_panel.feedbackSubmitted.connect(self._on_feedback_submitted)
        right_layout.addWidget(self.similarity_panel, 1)
        splitter.addWidget(right_panel)

        splitter.setSizes([280, 420, 300])

        main_layout.addWidget(splitter)

    def _build_toolbar(self):
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        act_import = QAction("导入图片", self)
        act_import.triggered.connect(self._on_import)
        toolbar.addAction(act_import)

        act_import_batch = QAction("批量导入", self)
        act_import_batch.triggered.connect(self._on_batch_import)
        toolbar.addAction(act_import_batch)

        toolbar.addSeparator()

        self.act_edit = QAction("编辑图片", self)
        self.act_edit.triggered.connect(self._on_edit_image)
        self.act_edit.setEnabled(False)
        toolbar.addAction(self.act_edit)

        toolbar.addSeparator()

        self.act_match = QAction("查找相似", self)
        self.act_match.triggered.connect(self._on_find_similar)
        self.act_match.setEnabled(False)
        toolbar.addAction(self.act_match)

        act_compare_hist = QAction("对比记录", self)
        act_compare_hist.triggered.connect(self._on_view_all_comparisons)
        toolbar.addAction(act_compare_hist)

        act_feedback = QAction("反馈与权重", self)
        act_feedback.triggered.connect(self._on_view_feedback)
        toolbar.addAction(act_feedback)

        act_edition = QAction("版别关系图谱", self)
        act_edition.triggered.connect(self._on_view_edition_graph)
        toolbar.addAction(act_edition)

        toolbar.addSeparator()

        act_about = QAction("关于", self)
        act_about.triggered.connect(self._on_about)
        toolbar.addAction(act_about)

    def _build_statusbar(self):
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("就绪")

    def _load_rubbings(self):
        keyword = self.search_edit.text().strip() if hasattr(self, 'search_edit') else ""
        era = self.era_filter.currentData() if hasattr(self, 'era_filter') else ""
        material = self.material_filter.currentText().strip() if hasattr(self, 'material_filter') else ""
        inscription = self.inscription_filter.text().strip() if hasattr(self, 'inscription_filter') else ""
        excavation = self.excavation_filter.currentText().strip() if hasattr(self, 'excavation_filter') else ""
        has_contour_only = self.contour_only_cb.isChecked() if hasattr(self, 'contour_only_cb') else False
        sort_by = self.sort_combo.currentData() if hasattr(self, 'sort_combo') else "created_at"
        sort_order = "desc" if (not hasattr(self, 'sort_order_btn')) or self.sort_order_btn.isChecked() else "asc"

        self._rubbings = self._service.list_rubbings(
            era=era if era else None,
            keyword=keyword if keyword else None,
            material=material if material else None,
            inscription=inscription if inscription else None,
            excavation_site=excavation if excavation else None,
            has_contour_only=has_contour_only,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        self.rubbing_list.clear()
        for r in self._rubbings:
            item = QListWidgetItem()
            display_text = f"{r.get('code', '')}\n{r.get('era', '—')} · {r.get('inscription', '—')}"
            item.setText(display_text)
            item.setData(Qt.UserRole, r["id"])

            img_path = r.get("processed_path") or r.get("original_path")
            if img_path:
                pixmap = load_pixmap_from_path(img_path, 50, 50)
                if not pixmap.isNull():
                    item.setIcon(pixmap)

            if not r.get("has_valid_contour"):
                font = item.font()
                font.setItalic(True)
                item.setFont(font)
                item.setToolTip("缺少有效轮廓，无法参与自动匹配")

            self.rubbing_list.addItem(item)

        self.count_label.setText(f"共 {len(self._rubbings)} 个拓片")

    def _update_eras(self):
        eras = self._service.get_all_eras()
        current_data = self.era_filter.currentData() if self.era_filter.count() > 0 else ""
        self.era_filter.clear()
        self.era_filter.addItem("全部", "")
        for era in eras:
            self.era_filter.addItem(era, era)
        if current_data:
            idx = self.era_filter.findData(current_data)
            if idx >= 0:
                self.era_filter.setCurrentIndex(idx)
        self.detail_panel.set_eras(eras)

    def _update_materials(self):
        materials = self._service.get_all_materials()
        current_text = self.material_filter.currentText()
        self.material_filter.clear()
        self.material_filter.addItem("全部", "")
        for m in materials:
            self.material_filter.addItem(m, m)
        if current_text:
            idx = self.material_filter.findText(current_text)
            if idx >= 0:
                self.material_filter.setCurrentIndex(idx)
            else:
                self.material_filter.setCurrentText(current_text)

    def _update_excavation_sites(self):
        sites = self._service.get_all_excavation_sites()
        current_text = self.excavation_filter.currentText()
        self.excavation_filter.clear()
        self.excavation_filter.addItem("全部", "")
        for s in sites:
            self.excavation_filter.addItem(s, s)
        if current_text:
            idx = self.excavation_filter.findText(current_text)
            if idx >= 0:
                self.excavation_filter.setCurrentIndex(idx)
            else:
                self.excavation_filter.setCurrentText(current_text)

    def _update_inscription_completer(self):
        inscriptions = self._service.get_all_inscriptions()
        model = QStringListModel(inscriptions)
        self.inscription_completer.setModel(model)

    def _toggle_advanced_filters(self, checked: bool):
        self.advanced_filter_widget.setVisible(checked)
        self.advanced_filter_btn.setText("▲ 高级筛选" if checked else "▼ 高级筛选")

    def _on_sort_order_changed(self, checked: bool):
        self.sort_order_btn.setText("降序 ↓" if checked else "升序 ↑")
        self._load_rubbings()

    def _on_search_changed(self, text: str):
        self._load_rubbings()

    def _on_filter_changed(self):
        self._load_rubbings()

    def _on_rubbing_selected(self):
        items = self.rubbing_list.selectedItems()
        if not items:
            self._current_rubbing = None
            self.detail_panel.set_rubbing(None)
            self.similarity_panel.set_target_rubbing(None)
            self.act_edit.setEnabled(False)
            self.act_match.setEnabled(False)
            return
        item = items[0]
        rubbing_id = item.data(Qt.UserRole)
        rubbing = self._service.get_rubbing(rubbing_id)
        self._current_rubbing = rubbing
        self.detail_panel.set_rubbing(rubbing)
        self.similarity_panel.set_target_rubbing(rubbing)
        self.act_edit.setEnabled(True)
        self.act_match.setEnabled(rubbing.get("has_valid_contour", False))

    def _on_rubbing_double_clicked(self, item: QListWidgetItem):
        pass

    def _on_import(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择拓片图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.tif *.tiff);;所有文件 (*)"
        )
        if not file_path:
            return

        result = self._service.import_single_image(file_path)
        if result["success"]:
            self.statusBar().showMessage(f"导入成功: {result['rubbing'].get('code', '')}", 3000)
            self._load_rubbings()
            self._update_eras()
            self._update_materials()
            self._update_excavation_sites()
            self._update_inscription_completer()
        else:
            QMessageBox.warning(self, "导入失败", result.get("error", "未知错误"))

    def _on_batch_import(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, "选择拓片图片", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.tif *.tiff);;所有文件 (*)"
        )
        if not file_paths:
            return

        dialog = BatchImportDialog(file_paths, self._service, self)
        dialog.importCompleted.connect(self._on_batch_import_completed)
        dialog.show()
        dialog.start_import()
        dialog.exec()

    def _on_batch_import_completed(self):
        self._load_rubbings()
        self._update_eras()
        self._update_materials()
        self._update_excavation_sites()
        self.statusBar().showMessage("批量导入完成", 3000)

    def _on_edit_image(self):
        if not self._current_rubbing:
            QMessageBox.information(self, "提示", "请先选择一个拓片")
            return
        img_path = (
            self._current_rubbing.get("processed_path")
            or self._current_rubbing.get("original_path")
        )
        if not img_path:
            QMessageBox.warning(self, "错误", "找不到图片文件")
            return

        dialog = ImageEditorDialog(img_path, self)
        dialog.imageSaved.connect(self._on_image_edited)
        dialog.exec()

    def _on_image_edited(self, new_path: str):
        if not self._current_rubbing:
            return
        rubbing_id = self._current_rubbing["id"]
        from ..db.database import RubbingDAO
        from ..core.image_processor import get_image_size, load_image

        img = load_image(new_path)
        w, h = get_image_size(img)
        RubbingDAO.update(rubbing_id, {
            "processed_path": new_path,
            "width": w,
            "height": h,
        })
        self._service._refresh_features(rubbing_id)

        updated = self._service.get_rubbing(rubbing_id)
        self._current_rubbing = updated
        self.detail_panel.set_rubbing(updated)
        self.similarity_panel.set_target_rubbing(updated)
        self.similarity_panel.refresh()
        self._load_rubbings()
        self.statusBar().showMessage("图片已更新", 3000)

    def _on_find_similar(self):
        if not self._current_rubbing:
            QMessageBox.information(self, "提示", "请先选择一个拓片")
            return
        if not self._current_rubbing.get("has_valid_contour"):
            QMessageBox.warning(
                self, "无法匹配",
                "该拓片缺少有效轮廓，无法参与自动匹配。\n"
                "请尝试调整图片质量后重试。"
            )
            return
        self.similarity_panel._do_match()

    def _on_compare_requested(self, rubbing_a_id: int, rubbing_b_id: int):
        rubbing_a = self._service.get_rubbing(rubbing_a_id)
        rubbing_b = self._service.get_rubbing(rubbing_b_id)
        if not rubbing_a or not rubbing_b:
            return

        sim_data = self._service.compare_two(rubbing_a_id, rubbing_b_id)
        dialog = CompareDialog(rubbing_a, rubbing_b, sim_data, self._service, self)
        dialog.comparisonSaved.connect(self._on_comparison_saved)
        dialog.exec()

    def _on_comparison_saved(self):
        self.statusBar().showMessage("对比结论已保存", 3000)

    def _on_view_comparisons(self):
        if not self._current_rubbing:
            QMessageBox.information(self, "提示", "请先选择一个拓片")
            return
        dialog = ComparisonHistoryDialog(
            self._service, rubbing_id=self._current_rubbing["id"], parent=self
        )
        dialog.comparisonUpdated.connect(self._on_comparison_updated)
        dialog.exec()

    def _on_view_all_comparisons(self):
        dialog = ComparisonHistoryDialog(self._service, parent=self)
        dialog.comparisonUpdated.connect(self._on_comparison_updated)
        dialog.exec()

    def _on_view_feedback(self):
        dialog = FeedbackHistoryDialog(self._service, parent=self)
        dialog.weightsChanged.connect(self._on_weights_changed)
        dialog.exec()

    def _on_comparison_updated(self):
        self.statusBar().showMessage("对比记录已更新", 3000)

    def _on_feedback_submitted(self):
        self.statusBar().showMessage("反馈已提交，权重已根据反馈动态调整", 3000)

    def _on_weights_changed(self):
        self.similarity_panel.refresh()
        self.statusBar().showMessage("权重已更新", 3000)

    def _on_rubbing_deleted(self, rubbing_id: int):
        self._load_rubbings()
        self._update_eras()
        self._update_materials()
        self._update_excavation_sites()
        self._update_inscription_completer()
        self._current_rubbing = None
        self.detail_panel.set_rubbing(None)
        self.similarity_panel.set_target_rubbing(None)
        self.statusBar().showMessage("拓片已删除", 3000)

    def _on_detail_changed(self):
        self._load_rubbings()
        self._update_eras()
        self._update_materials()
        self._update_excavation_sites()
        self._update_inscription_completer()
        if self._current_rubbing:
            updated = self._service.get_rubbing(self._current_rubbing["id"])
            self._current_rubbing = updated

    def _on_view_edition_graph(self):
        dialog = EditionManagerDialog(self._service, self)
        dialog.exec()

    def _on_view_edition_graph_from_detail(self):
        dialog = EditionManagerDialog(self._service, self)
        if self._current_rubbing:
            groups = self._service.get_edition_groups_for_rubbing(
                self._current_rubbing["id"]
            )
            if groups:
                dialog.focus_on_group(groups[0]["id"])
        dialog.exec()

    def _on_edition_group_changed(self):
        self.statusBar().showMessage("版别组信息已更新", 3000)

    def _on_about(self):
        QMessageBox.about(
            self, "关于",
            "古钱币拓片管理系统 v2.0\n\n"
            "功能：\n"
            "• 批量导入拓片图片\n"
            "• 登记编号、年代、钱文、材质、出土地\n"
            "• 裁剪、旋转、灰度、对比度调整\n"
            "• 基于轮廓与纹理的智能相似度匹配\n"
            "• 并排对比与人工确认结论\n"
            "• 多条件组合筛选与模糊检索\n"
            "• 相似结果人工反馈学习\n"
            "• 动态权重调整与可视化\n"
            "• 版别关系图谱与谱系管理\n\n"
            "技术栈：Python + PySide6 + SQLite + OpenCV"
        )
