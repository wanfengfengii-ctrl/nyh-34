from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt
import cv2
import numpy as np


def cvimg_to_qpixmap(img: np.ndarray, max_width: int = 400, max_height: int = 400) -> QPixmap:
    if len(img.shape) == 2:
        rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    else:
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    qimg = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888).copy()
    pixmap = QPixmap.fromImage(qimg)
    return pixmap.scaled(
        max_width, max_height,
        Qt.KeepAspectRatio,
        Qt.SmoothTransformation
    )


def load_pixmap_from_path(file_path: str, max_width: int = 400, max_height: int = 400) -> QPixmap:
    pixmap = QPixmap(file_path)
    if pixmap.isNull():
        return QPixmap()
    return pixmap.scaled(
        max_width, max_height,
        Qt.KeepAspectRatio,
        Qt.SmoothTransformation
    )
