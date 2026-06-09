from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSlider, QSpinBox, QDoubleSpinBox, QGroupBox, QFormLayout,
    QMessageBox, QWidget,
)
from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QMouseEvent
import cv2
import numpy as np

from ..core.image_processor import (
    load_image,
    rotate_image,
    crop_image,
    to_grayscale,
    adjust_contrast,
)
from .utils import cvimg_to_qpixmap


class ImageLabel(QLabel):
    cropSelected = Signal(int, int, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(400, 400)
        self.setStyleSheet("border: 1px solid #ccc; background: #f5f5f5;")
        self._cropping = False
        self._start_pos = None
        self._end_pos = None
        self._pixmap = None
        self._pixmap_pos = None
        self._pixmap_rect = None

    def setImage(self, img: np.ndarray):
        self._pixmap = cvimg_to_qpixmap(img, 500, 500)
        self.setPixmap(self._pixmap)
        self._update_pixmap_rect()

    def _update_pixmap_rect(self):
        if self._pixmap is None:
            self._pixmap_rect = None
            return
        pw = self._pixmap.width()
        ph = self._pixmap.height()
        w = self.width()
        h = self.height()
        x = (w - pw) // 2
        y = (h - ph) // 2
        self._pixmap_rect = QRect(x, y, pw, ph)

    def setCropping(self, enabled: bool):
        self._cropping = enabled
        self._start_pos = None
        self._end_pos = None
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._cropping and self._start_pos and self._end_pos:
            painter = QPainter(self)
            pen = QPen(QColor(0, 255, 0), 2, Qt.DashLine)
            painter.setPen(pen)
            rect = QRect(self._start_pos, self._end_pos).normalized()
            painter.drawRect(rect)

    def mousePressEvent(self, ev: QMouseEvent):
        if self._cropping and ev.button() == Qt.LeftButton:
            self._start_pos = ev.pos()
            self._end_pos = ev.pos()
            self.update()

    def mouseMoveEvent(self, ev: QMouseEvent):
        if self._cropping and self._start_pos:
            self._end_pos = ev.pos()
            self.update()

    def mouseReleaseEvent(self, ev: QMouseEvent):
        if self._cropping and ev.button() == Qt.LeftButton and self._start_pos:
            self._end_pos = ev.pos()
            if self._pixmap_rect and self._pixmap:
                rect = QRect(self._start_pos, self._end_pos).normalized()
                inter = rect.intersected(self._pixmap_rect)
                if inter.width() > 10 and inter.height() > 10:
                    rel_x = inter.x() - self._pixmap_rect.x()
                    rel_y = inter.y() - self._pixmap_rect.y()
                    scale_x = self._original_size[0] / self._pixmap_rect.width()
                    scale_y = self._original_size[1] / self._pixmap_rect.height()
                    x = int(rel_x * scale_x)
                    y = int(rel_y * scale_y)
                    w = int(inter.width() * scale_x)
                    h = int(inter.height() * scale_y)
                    self.cropSelected.emit(x, y, w, h)

    def setOriginalSize(self, w: int, h: int):
        self._original_size = (w, h)


class ImageEditorDialog(QDialog):
    imageSaved = Signal(str)

    def __init__(self, image_path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("图片编辑器")
        self.resize(900, 600)
        self._image_path = image_path
        try:
            self._original_img = load_image(image_path)
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法加载图片: {e}")
            self.reject()
            return
        self._current_img = self._original_img.copy()
        self._history = [self._original_img.copy()]
        self._history_idx = 0
        self._build_ui()
        self._update_display()

    def _build_ui(self):
        main_layout = QHBoxLayout(self)

        left_layout = QVBoxLayout()
        self.image_label = ImageLabel()
        self.image_label.setOriginalSize(
            self._original_img.shape[1],
            self._original_img.shape[0],
        )
        self.image_label.cropSelected.connect(self._on_crop_selected)
        left_layout.addWidget(self.image_label, 1)

        btn_row = QHBoxLayout()
        self.btn_undo = QPushButton("撤销")
        self.btn_undo.clicked.connect(self._undo)
        self.btn_redo = QPushButton("重做")
        self.btn_redo.clicked.connect(self._redo)
        self.btn_reset = QPushButton("重置")
        self.btn_reset.clicked.connect(self._reset)
        btn_row.addWidget(self.btn_undo)
        btn_row.addWidget(self.btn_redo)
        btn_row.addWidget(self.btn_reset)
        left_layout.addLayout(btn_row)

        main_layout.addLayout(left_layout, 2)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        rotate_box = QGroupBox("旋转")
        rotate_layout = QFormLayout(rotate_box)
        self.angle_spin = QDoubleSpinBox()
        self.angle_spin.setRange(-180, 180)
        self.angle_spin.setValue(0)
        self.angle_spin.setSuffix("°")
        self.btn_rotate = QPushButton("应用旋转")
        self.btn_rotate.clicked.connect(self._apply_rotate)
        rotate_layout.addRow("角度:", self.angle_spin)
        rotate_layout.addRow(self.btn_rotate)
        btn_row2 = QHBoxLayout()
        btn_rot_left = QPushButton("左旋90°")
        btn_rot_left.clicked.connect(lambda: self._quick_rotate(-90))
        btn_rot_right = QPushButton("右旋90°")
        btn_rot_right.clicked.connect(lambda: self._quick_rotate(90))
        btn_row2.addWidget(btn_rot_left)
        btn_row2.addWidget(btn_rot_right)
        rotate_layout.addRow(btn_row2)
        right_layout.addWidget(rotate_box)

        crop_box = QGroupBox("裁剪")
        crop_layout = QVBoxLayout(crop_box)
        self.btn_crop_mode = QPushButton("开启裁剪模式")
        self.btn_crop_mode.setCheckable(True)
        self.btn_crop_mode.toggled.connect(self._toggle_crop_mode)
        crop_layout.addWidget(self.btn_crop_mode)
        crop_info = QLabel("提示：开启后在图片上拖拽选择裁剪区域")
        crop_info.setWordWrap(True)
        crop_info.setStyleSheet("color: #666; font-size: 11px;")
        crop_layout.addWidget(crop_info)
        right_layout.addWidget(crop_box)

        grayscale_box = QGroupBox("灰度处理")
        gray_layout = QVBoxLayout(grayscale_box)
        self.btn_grayscale = QPushButton("转为灰度")
        self.btn_grayscale.clicked.connect(self._apply_grayscale)
        gray_layout.addWidget(self.btn_grayscale)
        right_layout.addWidget(grayscale_box)

        contrast_box = QGroupBox("对比度调整")
        contrast_layout = QFormLayout(contrast_box)
        self.contrast_slider = QSlider(Qt.Horizontal)
        self.contrast_slider.setRange(50, 200)
        self.contrast_slider.setValue(100)
        self.contrast_label = QLabel("100%")
        self.contrast_slider.valueChanged.connect(
            lambda v: self.contrast_label.setText(f"{v}%")
        )
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setRange(-100, 100)
        self.brightness_slider.setValue(0)
        self.brightness_label = QLabel("0")
        self.brightness_slider.valueChanged.connect(
            lambda v: self.brightness_label.setText(str(v))
        )
        contrast_layout.addRow("对比度:", self.contrast_slider)
        contrast_layout.addRow("", self.contrast_label)
        contrast_layout.addRow("亮度:", self.brightness_slider)
        contrast_layout.addRow("", self.brightness_label)
        self.btn_contrast = QPushButton("应用对比度")
        self.btn_contrast.clicked.connect(self._apply_contrast)
        contrast_layout.addRow(self.btn_contrast)
        right_layout.addWidget(contrast_box)

        right_layout.addStretch()

        action_row = QHBoxLayout()
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save = QPushButton("保存并应用")
        self.btn_save.clicked.connect(self._save)
        self.btn_save.setStyleSheet("background: #4a90d9; color: white; padding: 6px 12px;")
        action_row.addWidget(self.btn_cancel)
        action_row.addWidget(self.btn_save)
        right_layout.addLayout(action_row)

        main_layout.addWidget(right_panel, 1)

    def _update_display(self):
        self.image_label.setImage(self._current_img)
        h, w = self._current_img.shape[:2]
        self.image_label.setOriginalSize(w, h)

    def _push_history(self):
        self._history = self._history[:self._history_idx + 1]
        self._history.append(self._current_img.copy())
        self._history_idx = len(self._history) - 1

    def _undo(self):
        if self._history_idx > 0:
            self._history_idx -= 1
            self._current_img = self._history[self._history_idx].copy()
            self._update_display()

    def _redo(self):
        if self._history_idx < len(self._history) - 1:
            self._history_idx += 1
            self._current_img = self._history[self._history_idx].copy()
            self._update_display()

    def _reset(self):
        self._current_img = self._original_img.copy()
        self._history = [self._original_img.copy()]
        self._history_idx = 0
        self._update_display()

    def _apply_rotate(self):
        angle = self.angle_spin.value()
        if angle == 0:
            return
        self._current_img = rotate_image(self._current_img, angle)
        self._push_history()
        self._update_display()

    def _quick_rotate(self, angle: float):
        self._current_img = rotate_image(self._current_img, angle)
        self._push_history()
        self._update_display()

    def _toggle_crop_mode(self, checked: bool):
        self.image_label.setCropping(checked)
        if checked:
            self.btn_crop_mode.setText("关闭裁剪模式")
        else:
            self.btn_crop_mode.setText("开启裁剪模式")

    def _on_crop_selected(self, x: int, y: int, w: int, h: int):
        if w > 0 and h > 0:
            self._current_img = crop_image(self._current_img, x, y, w, h)
            self._push_history()
            self._update_display()
            self.btn_crop_mode.setChecked(False)
            self._toggle_crop_mode(False)

    def _apply_grayscale(self):
        self._current_img = to_grayscale(self._current_img)
        self._push_history()
        self._update_display()

    def _apply_contrast(self):
        alpha = self.contrast_slider.value() / 100.0
        beta = self.brightness_slider.value()
        self._current_img = adjust_contrast(self._current_img, alpha=alpha, beta=beta)
        self._push_history()
        self._update_display()

    def _save(self):
        import uuid
        from pathlib import Path
        from ..db.database import get_processed_dir
        from ..core.image_processor import save_image

        code = Path(self._image_path).stem.split("_")[0]
        suffix = Path(self._image_path).suffix
        if not suffix:
            suffix = ".png"
        new_filename = f"{code}_edited_{uuid.uuid4().hex[:6]}{suffix}"
        new_path = str(get_processed_dir() / new_filename)
        save_image(self._current_img, new_path)
        self.imageSaved.emit(new_path)
        self.accept()
