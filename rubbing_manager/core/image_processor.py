import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Optional


def load_image(file_path: str) -> np.ndarray:
    img = cv2.imread(file_path, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"无法读取图片: {file_path}")
    return img


def save_image(img: np.ndarray, file_path: str) -> None:
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(file_path, img)


def to_grayscale(img: np.ndarray) -> np.ndarray:
    if len(img.shape) == 2:
        return img
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def to_color(img: np.ndarray) -> np.ndarray:
    if len(img.shape) == 3:
        return img
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)


def adjust_contrast(img: np.ndarray, alpha: float = 1.0, beta: int = 0) -> np.ndarray:
    result = cv2.convertScaleAbs(img, alpha=alpha, beta=beta)
    return result


def rotate_image(img: np.ndarray, angle: float) -> np.ndarray:
    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    cos = np.abs(M[0, 0])
    sin = np.abs(M[0, 1])
    new_w = int(h * sin + w * cos)
    new_h = int(h * cos + w * sin)
    M[0, 2] += (new_w / 2) - center[0]
    M[1, 2] += (new_h / 2) - center[1]
    rotated = cv2.warpAffine(
        img, M, (new_w, new_h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255)
    )
    return rotated


def crop_image(img: np.ndarray, x: int, y: int, w: int, h: int) -> np.ndarray:
    x = max(0, x)
    y = max(0, y)
    h_img, w_img = img.shape[:2]
    w = min(w, w_img - x)
    h = min(h, h_img - y)
    return img[y:y + h, x:x + w]


def resize_image(img: np.ndarray, max_width: int = 800) -> np.ndarray:
    h, w = img.shape[:2]
    if w <= max_width:
        return img
    ratio = max_width / w
    new_h = int(h * ratio)
    return cv2.resize(img, (max_width, new_h), interpolation=cv2.INTER_AREA)


def find_main_contour(gray_img: np.ndarray) -> Tuple[Optional[np.ndarray], bool]:
    blurred = cv2.GaussianBlur(gray_img, (5, 5), 0)
    _, thresh = cv2.threshold(
        blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    contours, _ = cv2.findContours(
        thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if not contours:
        return None, False
    h_img, w_img = gray_img.shape[:2]
    img_area = h_img * w_img
    valid_contours = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > img_area * 0.05:
            valid_contours.append((area, cnt))
    if not valid_contours:
        return None, False
    valid_contours.sort(key=lambda x: x[0], reverse=True)
    return valid_contours[0][1], True


def get_image_size(img: np.ndarray) -> Tuple[int, int]:
    h, w = img.shape[:2]
    return w, h


def normalize_image(img: np.ndarray) -> np.ndarray:
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    return enhanced


def draw_contour_on_image(img: np.ndarray, contour: np.ndarray,
                          color: Tuple[int, int, int] = (0, 255, 0),
                          thickness: int = 2) -> np.ndarray:
    result = img.copy()
    if len(result.shape) == 2:
        result = cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)
    cv2.drawContours(result, [contour], -1, color, thickness)
    return result


def ndarray_to_qimage_bytes(img: np.ndarray, quality: int = 95) -> bytes:
    if len(img.shape) == 2:
        img_color = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    else:
        img_color = img
    rgb = cv2.cvtColor(img_color, cv2.COLOR_BGR2RGB)
    success, encoded = cv2.imencode(
        ".jpg", rgb, [cv2.IMWRITE_JPEG_QUALITY, quality]
    )
    if not success:
        raise RuntimeError("图像编码失败")
    return encoded.tobytes()
