import os
import uuid
import shutil
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..db.database import (
    RubbingDAO,
    ComparisonDAO,
    ImportRecordDAO,
    compute_file_hash,
    get_processed_dir,
    get_data_dir,
    array_to_blob,
)
from .image_processor import (
    load_image,
    save_image,
    to_grayscale,
    rotate_image,
    crop_image,
    adjust_contrast,
    get_image_size,
)
from .feature_extractor import (
    extract_all_features,
    SimilarityMatcher,
    compute_similarity,
)


class ImportResult:
    def __init__(self):
        self.success: List[Dict[str, Any]] = []
        self.failed: List[Dict[str, str]] = []
        self.duplicates: List[Dict[str, str]] = []


class RubbingService:
    def __init__(self):
        self.matcher = SimilarityMatcher(threshold=0.2)

    def import_single_image(
        self, file_path: str, batch_id: Optional[str] = None
    ) -> Dict[str, Any]:
        result = {"success": False, "error": None, "rubbing": None}
        try:
            file_hash = compute_file_hash(file_path)
            existing = RubbingDAO.get_by_hash(file_hash)
            if existing:
                ImportRecordDAO.create({
                    "file_path": file_path,
                    "status": ImportRecordDAO.STATUS_DUPLICATE,
                    "file_hash": file_hash,
                    "duplicate_of": existing["code"],
                    "batch_id": batch_id,
                })
                result["error"] = f"文件重复，已存在编号: {existing['code']}"
                return result

            img = load_image(file_path)
            width, height = get_image_size(img)
            contour_feat, texture_feat, has_valid = extract_all_features(img)

            code = f"RB-{uuid.uuid4().hex[:8].upper()}"
            proc_filename = f"{code}_original{Path(file_path).suffix}"
            proc_path = str(get_processed_dir() / proc_filename)
            shutil.copy2(file_path, proc_path)

            rubbing_id = RubbingDAO.create({
                "code": code,
                "era": "",
                "inscription": "",
                "material": "",
                "excavation_site": "",
                "original_path": file_path,
                "processed_path": proc_path,
                "file_hash": file_hash,
                "has_valid_contour": has_valid,
                "contour_feature": array_to_blob(contour_feat) if contour_feat is not None else None,
                "texture_feature": array_to_blob(texture_feat) if texture_feat is not None else None,
                "width": width,
                "height": height,
                "notes": "",
            })
            ImportRecordDAO.create({
                "file_path": file_path,
                "status": ImportRecordDAO.STATUS_SUCCESS,
                "file_hash": file_hash,
                "batch_id": batch_id,
            })
            result["success"] = True
            result["rubbing"] = RubbingDAO.get_by_id(rubbing_id)
            return result
        except Exception as e:
            ImportRecordDAO.create({
                "file_path": file_path,
                "status": ImportRecordDAO.STATUS_FAILED,
                "error_message": str(e),
                "batch_id": batch_id,
            })
            result["error"] = str(e)
            return result

    def batch_import(
        self, file_paths: List[str], progress_callback=None
    ) -> ImportResult:
        batch_id = uuid.uuid4().hex
        result = ImportResult()
        total = len(file_paths)
        for i, path in enumerate(file_paths):
            import_res = self.import_single_image(path, batch_id)
            if import_res["success"] and import_res["rubbing"]:
                result.success.append(import_res["rubbing"])
            elif import_res["error"]:
                existing = RubbingDAO.get_by_hash(compute_file_hash(path))
                if existing:
                    result.duplicates.append({
                        "file_path": path,
                        "reason": f"文件重复，已存在: {existing['code']}",
                    })
                else:
                    result.failed.append({
                        "file_path": path,
                        "reason": import_res["error"],
                    })
            if progress_callback:
                progress_callback(i + 1, total)
        return result

    def list_rubbings(
        self,
        era: Optional[str] = None,
        keyword: Optional[str] = None,
        has_contour_only: bool = False,
    ) -> List[Dict[str, Any]]:
        return RubbingDAO.list_all(era=era, keyword=keyword, has_contour_only=has_contour_only)

    def get_rubbing(self, rubbing_id: int) -> Optional[Dict[str, Any]]:
        return RubbingDAO.get_by_id(rubbing_id)

    def update_rubbing(self, rubbing_id: int, data: Dict[str, Any]) -> None:
        RubbingDAO.update(rubbing_id, data)

    def delete_rubbing(self, rubbing_id: int) -> Tuple[bool, str]:
        if ComparisonDAO.has_any_conclusion(rubbing_id):
            return False, "该拓片已有对比结论，无法直接删除。请先处理相关对比记录。"
        rubbing = RubbingDAO.get_by_id(rubbing_id)
        if rubbing and rubbing.get("processed_path"):
            try:
                proc_path = Path(rubbing["processed_path"])
                if proc_path.exists() and str(get_processed_dir()) in str(proc_path):
                    proc_path.unlink()
            except Exception:
                pass
        RubbingDAO.delete(rubbing_id)
        return True, "删除成功"

    def _refresh_features(self, rubbing_id: int) -> None:
        rubbing = RubbingDAO.get_by_id(rubbing_id)
        if not rubbing:
            return
        img_path = rubbing.get("processed_path") or rubbing.get("original_path")
        if not img_path:
            return
        img = load_image(img_path)
        contour_feat, texture_feat, has_valid = extract_all_features(img)
        RubbingDAO.update(rubbing_id, {
            "has_valid_contour": has_valid,
            "contour_feature": array_to_blob(contour_feat) if contour_feat is not None else None,
            "texture_feature": array_to_blob(texture_feat) if texture_feat is not None else None,
        })

    def edit_image(
        self,
        rubbing_id: int,
        operation: str,
        params: Dict[str, Any],
    ) -> Optional[str]:
        rubbing = RubbingDAO.get_by_id(rubbing_id)
        if not rubbing:
            return None
        img_path = rubbing.get("processed_path") or rubbing.get("original_path")
        img = load_image(img_path)

        if operation == "rotate":
            angle = params.get("angle", 90)
            img = rotate_image(img, angle)
        elif operation == "crop":
            x = int(params.get("x", 0))
            y = int(params.get("y", 0))
            w = int(params.get("width", 0))
            h = int(params.get("height", 0))
            if w > 0 and h > 0:
                img = crop_image(img, x, y, w, h)
        elif operation == "grayscale":
            img = to_grayscale(img)
        elif operation == "contrast":
            alpha = float(params.get("alpha", 1.0))
            beta = int(params.get("beta", 0))
            img = adjust_contrast(img, alpha=alpha, beta=beta)
        else:
            return None

        code = rubbing["code"]
        suffix = Path(img_path).suffix
        new_filename = f"{code}_edited_{uuid.uuid4().hex[:6]}{suffix}"
        new_path = str(get_processed_dir() / new_filename)
        save_image(img, new_path)

        width, height = get_image_size(img)
        RubbingDAO.update(rubbing_id, {
            "processed_path": new_path,
            "width": width,
            "height": height,
        })
        self._refresh_features(rubbing_id)
        return new_path

    def find_similar(
        self, rubbing_id: int, top_k: int = 10
    ) -> List[Dict[str, Any]]:
        target = RubbingDAO.get_by_id(rubbing_id)
        if not target or not target.get("has_valid_contour"):
            return []
        all_items = RubbingDAO.get_all_with_features()
        return self.matcher.find_similar(rubbing_id, all_items, top_k=top_k)

    def compare_two(
        self, rubbing_a_id: int, rubbing_b_id: int
    ) -> Dict[str, Any]:
        a = RubbingDAO.get_by_id(rubbing_a_id)
        b = RubbingDAO.get_by_id(rubbing_b_id)
        if not a or not b:
            return {}
        overall, contour_sim, texture_sim = compute_similarity(
            a.get("contour_feature"),
            a.get("texture_feature"),
            b.get("contour_feature"),
            b.get("texture_feature"),
        )
        return {
            "rubbing_a_id": rubbing_a_id,
            "rubbing_b_id": rubbing_b_id,
            "code_a": a.get("code", ""),
            "code_b": b.get("code", ""),
            "similarity_score": round(overall * 100, 2),
            "contour_similarity": round(contour_sim * 100, 2),
            "texture_similarity": round(texture_sim * 100, 2),
        }

    def save_comparison(self, data: Dict[str, Any]) -> int:
        return ComparisonDAO.create(data)

    def update_comparison(self, comparison_id: int, data: Dict[str, Any]) -> None:
        ComparisonDAO.update(comparison_id, data)

    def get_comparisons_for_rubbing(self, rubbing_id: int) -> List[Dict[str, Any]]:
        return ComparisonDAO.get_by_rubbing(rubbing_id)

    def can_delete_rubbing(self, rubbing_id: int) -> Tuple[bool, str]:
        if ComparisonDAO.has_any_conclusion(rubbing_id):
            return False, "该拓片已有对比结论，删除前请先处理相关对比记录。"
        return True, ""

    def get_all_eras(self) -> List[str]:
        rubbings = RubbingDAO.list_all()
        eras = set()
        for r in rubbings:
            if r.get("era"):
                eras.add(r["era"])
        return sorted(list(eras))
