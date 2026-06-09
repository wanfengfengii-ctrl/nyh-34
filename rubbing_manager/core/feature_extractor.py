import cv2
import numpy as np
from typing import Tuple, List, Dict, Any, Optional

from .image_processor import (
    to_grayscale,
    find_main_contour,
    normalize_image,
    load_image,
)
from ..db.database import blob_to_array, array_to_blob


CONTOUR_SAMPLE_POINTS = 256
TEXTURE_FEATURE_SIZE = 256


def extract_contour_features(gray_img: np.ndarray) -> Tuple[Optional[np.ndarray], bool]:
    contour, valid = find_main_contour(gray_img)
    if not valid or contour is None:
        return None, False
    contour = cv2.approxPolyDP(contour, 0.001 * cv2.arcLength(contour, True), True)
    if len(contour) < 10:
        return None, False
    features = _contour_to_fft_descriptor(contour, CONTOUR_SAMPLE_POINTS)
    return features, True


def _contour_to_fft_descriptor(contour: np.ndarray, n_points: int) -> np.ndarray:
    contour_2d = contour.reshape(-1, 2)
    complex_points = contour_2d[:, 0] + 1j * contour_2d[:, 1]
    original_len = len(complex_points)
    indices = np.linspace(0, original_len - 1, n_points).astype(int)
    sampled = complex_points[indices]
    fft_result = np.fft.fft(sampled)
    magnitude = np.abs(fft_result)
    magnitude = magnitude / (magnitude[0] if magnitude[0] != 0 else 1.0)
    return magnitude[1:65].astype(np.float32)


def extract_texture_features(gray_img: np.ndarray) -> np.ndarray:
    normalized = normalize_image(gray_img)
    h, w = normalized.shape[:2]
    if h < 64 or w < 64:
        resized = cv2.resize(normalized, (128, 128), interpolation=cv2.INTER_AREA)
    else:
        resized = cv2.resize(normalized, (256, 256), interpolation=cv2.INTER_AREA)
    features = _lbp_features(resized)
    features = features / (np.sum(features) + 1e-8)
    return features.astype(np.float32)


def _lbp_features(img: np.ndarray, num_points: int = 24, radius: int = 8) -> np.ndarray:
    gray = img if len(img.shape) == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    lbp = np.zeros_like(gray, dtype=np.uint8)
    h, w = gray.shape
    for i in range(num_points):
        theta = 2 * np.pi * i / num_points
        rx = radius * np.cos(theta)
        ry = -radius * np.sin(theta)
        x1 = int(np.floor(rx))
        y1 = int(np.floor(ry))
        x2 = int(np.ceil(rx))
        y2 = int(np.ceil(ry))
        fx = rx - x1
        fy = ry - y1
        src_x = np.clip(np.arange(w) + x1, 0, w - 1)
        src_y = np.clip(np.arange(h) + y1, 0, h - 1)
        src_x2 = np.clip(np.arange(w) + x2, 0, w - 1)
        src_y2 = np.clip(np.arange(h) + y2, 0, h - 1)
        p11 = gray[np.ix_(src_y, src_x)]
        p12 = gray[np.ix_(src_y, src_x2)]
        p21 = gray[np.ix_(src_y2, src_x)]
        p22 = gray[np.ix_(src_y2, src_x2)]
        value = (p11 * (1 - fx) * (1 - fy) +
                 p12 * fx * (1 - fy) +
                 p21 * (1 - fx) * fy +
                 p22 * fx * fy)
        threshold = gray
        lbp |= ((value >= threshold).astype(np.uint8) << i)
    hist, _ = np.histogram(lbp.ravel(), bins=np.arange(0, 2 ** num_points + 1))
    if num_points > 10:
        hist = np.zeros(TEXTURE_FEATURE_SIZE, dtype=np.float32)
        bins = np.linspace(0, 2 ** num_points, TEXTURE_FEATURE_SIZE + 1).astype(int)
        for i in range(TEXTURE_FEATURE_SIZE):
            hist[i] = np.sum(
                (lbp.ravel() >= bins[i]) & (lbp.ravel() < bins[i + 1])
            )
    return hist.astype(np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    if a is None or b is None:
        return 0.0
    a_flat = a.flatten().astype(np.float64)
    b_flat = b.flatten().astype(np.float64)
    if a_flat.shape != b_flat.shape:
        min_len = min(len(a_flat), len(b_flat))
        a_flat = a_flat[:min_len]
        b_flat = b_flat[:min_len]
    norm_a = np.linalg.norm(a_flat)
    norm_b = np.linalg.norm(b_flat)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a_flat, b_flat) / (norm_a * norm_b))


def compute_overall_similarity(
    contour_sim: float, texture_sim: float,
    contour_weight: float = 0.4, texture_weight: float = 0.6
) -> float:
    return contour_sim * contour_weight + texture_sim * texture_weight


def extract_all_features(
    img: np.ndarray
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], bool]:
    gray = to_grayscale(img)
    contour_feat, valid = extract_contour_features(gray)
    texture_feat = extract_texture_features(gray)
    return contour_feat, texture_feat, valid


def compute_similarity(
    feat_a_contour: Optional[bytes],
    feat_a_texture: Optional[bytes],
    feat_b_contour: Optional[bytes],
    feat_b_texture: Optional[bytes],
) -> Tuple[float, float, float]:
    contour_a = blob_to_array(feat_a_contour) if feat_a_contour else None
    contour_b = blob_to_array(feat_b_contour) if feat_b_contour else None
    texture_a = blob_to_array(feat_a_texture) if feat_a_texture else None
    texture_b = blob_to_array(feat_b_texture) if feat_b_texture else None

    contour_sim = cosine_similarity(contour_a, contour_b)
    texture_sim = cosine_similarity(texture_a, texture_b)
    overall = compute_overall_similarity(contour_sim, texture_sim)
    return overall, contour_sim, texture_sim


class SimilarityMatcher:
    def __init__(
        self,
        threshold: float = 0.3,
        contour_weight: float = 0.4,
        texture_weight: float = 0.6,
    ):
        self.threshold = threshold
        self.contour_weight = contour_weight
        self.texture_weight = texture_weight

    def set_weights(self, contour_weight: float, texture_weight: float) -> None:
        self.contour_weight = contour_weight
        self.texture_weight = texture_weight

    def get_weights(self) -> Tuple[float, float]:
        return self.contour_weight, self.texture_weight

    def compute_weighted_similarity(
        self,
        feat_a_contour: Optional[bytes],
        feat_a_texture: Optional[bytes],
        feat_b_contour: Optional[bytes],
        feat_b_texture: Optional[bytes],
    ) -> Tuple[float, float, float]:
        contour_a = blob_to_array(feat_a_contour) if feat_a_contour else None
        contour_b = blob_to_array(feat_b_contour) if feat_b_contour else None
        texture_a = blob_to_array(feat_a_texture) if feat_a_texture else None
        texture_b = blob_to_array(feat_b_texture) if feat_b_texture else None

        contour_sim = cosine_similarity(contour_a, contour_b)
        texture_sim = cosine_similarity(texture_a, texture_b)
        overall = compute_overall_similarity(
            contour_sim, texture_sim,
            self.contour_weight, self.texture_weight
        )
        return overall, contour_sim, texture_sim

    def find_similar(
        self,
        target_id: int,
        all_items: List[Dict[str, Any]],
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        target = None
        for item in all_items:
            if item["id"] == target_id:
                target = item
                break
        if target is None:
            return []
        results = []
        for item in all_items:
            if item["id"] == target_id:
                continue
            overall, contour_sim, texture_sim = self.compute_weighted_similarity(
                target.get("contour_feature"),
                target.get("texture_feature"),
                item.get("contour_feature"),
                item.get("texture_feature"),
            )
            if overall >= self.threshold:
                results.append({
                    "id": item["id"],
                    "code": item.get("code", ""),
                    "similarity_score": round(overall * 100, 2),
                    "contour_similarity": round(contour_sim * 100, 2),
                    "texture_similarity": round(texture_sim * 100, 2),
                    "contour_weight": self.contour_weight,
                    "texture_weight": self.texture_weight,
                })
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:top_k]
