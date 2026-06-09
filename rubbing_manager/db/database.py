import sqlite3
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager
import json
import numpy as np


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS rubbings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    era TEXT,
    inscription TEXT,
    material TEXT,
    excavation_site TEXT,
    original_path TEXT NOT NULL,
    processed_path TEXT,
    file_hash TEXT NOT NULL,
    has_valid_contour INTEGER DEFAULT 0,
    contour_feature BLOB,
    texture_feature BLOB,
    width INTEGER,
    height INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_rubbings_code ON rubbings(code);
CREATE INDEX IF NOT EXISTS idx_rubbings_era ON rubbings(era);
CREATE INDEX IF NOT EXISTS idx_rubbings_hash ON rubbings(file_hash);
CREATE INDEX IF NOT EXISTS idx_rubbings_inscription ON rubbings(inscription);
CREATE INDEX IF NOT EXISTS idx_rubbings_material ON rubbings(material);
CREATE INDEX IF NOT EXISTS idx_rubbings_excavation ON rubbings(excavation_site);

CREATE TABLE IF NOT EXISTS comparisons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rubbing_a_id INTEGER NOT NULL,
    rubbing_b_id INTEGER NOT NULL,
    similarity_score REAL NOT NULL,
    contour_similarity REAL,
    texture_similarity REAL,
    conclusion TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (rubbing_a_id) REFERENCES rubbings(id) ON DELETE CASCADE,
    FOREIGN KEY (rubbing_b_id) REFERENCES rubbings(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_comparisons_a ON comparisons(rubbing_a_id);
CREATE INDEX IF NOT EXISTS idx_comparisons_b ON comparisons(rubbing_b_id);

CREATE TABLE IF NOT EXISTS import_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT,
    file_hash TEXT,
    duplicate_of TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    batch_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_import_status ON import_records(status);
CREATE INDEX IF NOT EXISTS idx_import_batch ON import_records(batch_id);

CREATE TABLE IF NOT EXISTS similarity_feedbacks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_rubbing_id INTEGER NOT NULL,
    target_rubbing_id INTEGER NOT NULL,
    feedback_type TEXT NOT NULL,
    contour_similarity REAL,
    texture_similarity REAL,
    overall_similarity REAL,
    contour_weight_at_time REAL,
    texture_weight_at_time REAL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_rubbing_id) REFERENCES rubbings(id) ON DELETE CASCADE,
    FOREIGN KEY (target_rubbing_id) REFERENCES rubbings(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_feedback_source ON similarity_feedbacks(source_rubbing_id);
CREATE INDEX IF NOT EXISTS idx_feedback_target ON similarity_feedbacks(target_rubbing_id);
CREATE INDEX IF NOT EXISTS idx_feedback_type ON similarity_feedbacks(feedback_type);

CREATE TABLE IF NOT EXISTS weight_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contour_weight REAL NOT NULL,
    texture_weight REAL NOT NULL,
    adjustment_reason TEXT,
    feedback_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_weight_history_time ON weight_history(created_at);

CREATE TABLE IF NOT EXISTS system_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    setting_key TEXT UNIQUE NOT NULL,
    setting_value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_settings_key ON system_settings(setting_key);
"""


def get_db_path() -> Path:
    app_dir = Path.home() / ".rubbing_manager"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir / "rubbings.db"


def get_data_dir() -> Path:
    app_dir = Path.home() / ".rubbing_manager"
    data_dir = app_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_processed_dir() -> Path:
    proc_dir = get_data_dir() / "processed"
    proc_dir.mkdir(parents=True, exist_ok=True)
    return proc_dir


@contextmanager
def get_db_connection():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db_connection() as conn:
        conn.executescript(SCHEMA_SQL)


def compute_file_hash(file_path: str) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def array_to_blob(arr: np.ndarray) -> bytes:
    return arr.tobytes()


def blob_to_array(blob: bytes, dtype=np.float32) -> Optional[np.ndarray]:
    if blob is None:
        return None
    return np.frombuffer(blob, dtype=dtype)


class RubbingDAO:
    @staticmethod
    def create(data: Dict[str, Any]) -> int:
        with get_db_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO rubbings 
                   (code, era, inscription, material, excavation_site, 
                    original_path, processed_path, file_hash, 
                    has_valid_contour, contour_feature, texture_feature,
                    width, height, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    data.get("code"),
                    data.get("era"),
                    data.get("inscription"),
                    data.get("material"),
                    data.get("excavation_site"),
                    data.get("original_path"),
                    data.get("processed_path"),
                    data.get("file_hash"),
                    1 if data.get("has_valid_contour") else 0,
                    data.get("contour_feature"),
                    data.get("texture_feature"),
                    data.get("width"),
                    data.get("height"),
                    data.get("notes"),
                ),
            )
            return cursor.lastrowid

    @staticmethod
    def update(rubbing_id: int, data: Dict[str, Any]) -> None:
        fields = []
        values = []
        for key, val in data.items():
            if key == "id":
                continue
            fields.append(f"{key} = ?")
            values.append(val)
        if not fields:
            return
        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.append(rubbing_id)
        with get_db_connection() as conn:
            conn.execute(
                f"UPDATE rubbings SET {', '.join(fields)} WHERE id = ?",
                tuple(values),
            )

    @staticmethod
    def delete(rubbing_id: int) -> None:
        with get_db_connection() as conn:
            conn.execute("DELETE FROM rubbings WHERE id = ?", (rubbing_id,))

    @staticmethod
    def get_by_id(rubbing_id: int) -> Optional[Dict[str, Any]]:
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT * FROM rubbings WHERE id = ?", (rubbing_id,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_by_code(code: str) -> Optional[Dict[str, Any]]:
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT * FROM rubbings WHERE code = ?", (code,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_by_hash(file_hash: str) -> Optional[Dict[str, Any]]:
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT * FROM rubbings WHERE file_hash = ?", (file_hash,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def list_all(
        era: Optional[str] = None,
        keyword: Optional[str] = None,
        has_contour_only: bool = False,
        material: Optional[str] = None,
        inscription: Optional[str] = None,
        excavation_site: Optional[str] = None,
        min_similarity: Optional[float] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM rubbings WHERE 1=1"
        params: List[Any] = []
        if era:
            query += " AND era = ?"
            params.append(era)
        if keyword:
            query += " AND (code LIKE ? OR inscription LIKE ? OR excavation_site LIKE ? OR material LIKE ? OR notes LIKE ?)"
            params.extend([f"%{keyword}%"] * 5)
        if material:
            query += " AND material LIKE ?"
            params.append(f"%{material}%")
        if inscription:
            query += " AND inscription LIKE ?"
            params.append(f"%{inscription}%")
        if excavation_site:
            query += " AND excavation_site LIKE ?"
            params.append(f"%{excavation_site}%")
        if has_contour_only:
            query += " AND has_valid_contour = 1"

        sort_column = "created_at"
        if sort_by in ["code", "era", "inscription", "material", "excavation_site", "created_at", "updated_at"]:
            sort_column = sort_by
        sort_dir = "DESC" if sort_order.lower() == "desc" else "ASC"
        query += f" ORDER BY {sort_column} {sort_dir}"

        with get_db_connection() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_all_materials() -> List[str]:
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT material FROM rubbings WHERE material IS NOT NULL AND material != '' ORDER BY material"
            ).fetchall()
            return [r["material"] for r in rows]

    @staticmethod
    def get_all_excavation_sites() -> List[str]:
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT excavation_site FROM rubbings WHERE excavation_site IS NOT NULL AND excavation_site != '' ORDER BY excavation_site"
            ).fetchall()
            return [r["excavation_site"] for r in rows]

    @staticmethod
    def get_all_inscriptions() -> List[str]:
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT inscription FROM rubbings WHERE inscription IS NOT NULL AND inscription != '' ORDER BY inscription"
            ).fetchall()
            return [r["inscription"] for r in rows]

    @staticmethod
    def fuzzy_search_inscription(partial_text: str) -> List[Dict[str, Any]]:
        if not partial_text:
            return []
        with get_db_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM rubbings 
                   WHERE inscription LIKE ? 
                   ORDER BY 
                       CASE WHEN inscription = ? THEN 0
                            WHEN inscription LIKE ? THEN 1
                            WHEN inscription LIKE ? THEN 2
                            ELSE 3 END,
                       inscription
                   LIMIT 50""",
                (f"%{partial_text}%", partial_text, f"{partial_text}%", f"%{partial_text}%"),
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_all_with_features() -> List[Dict[str, Any]]:
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT id, code, contour_feature, texture_feature "
                "FROM rubbings WHERE has_valid_contour = 1"
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def count() -> int:
        with get_db_connection() as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM rubbings").fetchone()
            return row["cnt"]


class ComparisonDAO:
    CONCLUSION_SAME_EDITION = "same_edition"
    CONCLUSION_SUSPECTED_FORGERY = "suspected_forgery"
    CONCLUSION_DIFFERENT = "different"
    CONCLUSION_UNCONFIRMED = "unconfirmed"

    @staticmethod
    def create(data: Dict[str, Any]) -> int:
        with get_db_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO comparisons 
                   (rubbing_a_id, rubbing_b_id, similarity_score, 
                    contour_similarity, texture_similarity, conclusion, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    data.get("rubbing_a_id"),
                    data.get("rubbing_b_id"),
                    data.get("similarity_score"),
                    data.get("contour_similarity"),
                    data.get("texture_similarity"),
                    data.get("conclusion", ComparisonDAO.CONCLUSION_UNCONFIRMED),
                    data.get("notes"),
                ),
            )
            return cursor.lastrowid

    @staticmethod
    def update(comparison_id: int, data: Dict[str, Any]) -> None:
        fields = []
        values = []
        for key, val in data.items():
            if key == "id":
                continue
            fields.append(f"{key} = ?")
            values.append(val)
        if not fields:
            return
        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.append(comparison_id)
        with get_db_connection() as conn:
            conn.execute(
                f"UPDATE comparisons SET {', '.join(fields)} WHERE id = ?",
                tuple(values),
            )

    @staticmethod
    def get_by_rubbing(rubbing_id: int) -> List[Dict[str, Any]]:
        with get_db_connection() as conn:
            rows = conn.execute(
                """SELECT c.*, 
                          ra.code as code_a, rb.code as code_b
                   FROM comparisons c
                   JOIN rubbings ra ON c.rubbing_a_id = ra.id
                   JOIN rubbings rb ON c.rubbing_b_id = rb.id
                   WHERE c.rubbing_a_id = ? OR c.rubbing_b_id = ?
                   ORDER BY c.similarity_score DESC""",
                (rubbing_id, rubbing_id),
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def has_any_conclusion(rubbing_id: int) -> bool:
        with get_db_connection() as conn:
            row = conn.execute(
                """SELECT COUNT(*) as cnt FROM comparisons
                   WHERE (rubbing_a_id = ? OR rubbing_b_id = ?)
                   AND conclusion != ?""",
                (rubbing_id, rubbing_id, ComparisonDAO.CONCLUSION_UNCONFIRMED),
            ).fetchone()
            return row["cnt"] > 0

    @staticmethod
    def list_all() -> List[Dict[str, Any]]:
        with get_db_connection() as conn:
            rows = conn.execute(
                """SELECT c.*,
                          ra.code as code_a, rb.code as code_b
                   FROM comparisons c
                   JOIN rubbings ra ON c.rubbing_a_id = ra.id
                   JOIN rubbings rb ON c.rubbing_b_id = rb.id
                   ORDER BY c.created_at DESC"""
            ).fetchall()
            return [dict(r) for r in rows]


class ImportRecordDAO:
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_DUPLICATE = "duplicate"

    @staticmethod
    def create(data: Dict[str, Any]) -> int:
        with get_db_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO import_records
                   (file_path, status, error_message, file_hash, duplicate_of, batch_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    data.get("file_path"),
                    data.get("status"),
                    data.get("error_message"),
                    data.get("file_hash"),
                    data.get("duplicate_of"),
                    data.get("batch_id"),
                ),
            )
            return cursor.lastrowid

    @staticmethod
    def get_by_batch(batch_id: str) -> List[Dict[str, Any]]:
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM import_records WHERE batch_id = ? ORDER BY status",
                (batch_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_failed_by_batch(batch_id: str) -> List[Dict[str, Any]]:
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM import_records WHERE batch_id = ? AND status != ?",
                (batch_id, ImportRecordDAO.STATUS_SUCCESS),
            ).fetchall()
            return [dict(r) for r in rows]


class SimilarityFeedbackDAO:
    FEEDBACK_CORRECT = "correct"
    FEEDBACK_WRONG = "wrong"

    @staticmethod
    def create(data: Dict[str, Any]) -> int:
        with get_db_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO similarity_feedbacks
                   (source_rubbing_id, target_rubbing_id, feedback_type,
                    contour_similarity, texture_similarity, overall_similarity,
                    contour_weight_at_time, texture_weight_at_time, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    data.get("source_rubbing_id"),
                    data.get("target_rubbing_id"),
                    data.get("feedback_type"),
                    data.get("contour_similarity"),
                    data.get("texture_similarity"),
                    data.get("overall_similarity"),
                    data.get("contour_weight_at_time"),
                    data.get("texture_weight_at_time"),
                    data.get("notes", ""),
                ),
            )
            return cursor.lastrowid

    @staticmethod
    def get_by_id(feedback_id: int) -> Optional[Dict[str, Any]]:
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT * FROM similarity_feedbacks WHERE id = ?", (feedback_id,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_by_rubbing(rubbing_id: int) -> List[Dict[str, Any]]:
        with get_db_connection() as conn:
            rows = conn.execute(
                """SELECT f.*,
                          rs.code as source_code,
                          rt.code as target_code
                   FROM similarity_feedbacks f
                   JOIN rubbings rs ON f.source_rubbing_id = rs.id
                   JOIN rubbings rt ON f.target_rubbing_id = rt.id
                   WHERE f.source_rubbing_id = ? OR f.target_rubbing_id = ?
                   ORDER BY f.created_at DESC""",
                (rubbing_id, rubbing_id),
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def list_all(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        with get_db_connection() as conn:
            rows = conn.execute(
                """SELECT f.*,
                          rs.code as source_code,
                          rt.code as target_code
                   FROM similarity_feedbacks f
                   JOIN rubbings rs ON f.source_rubbing_id = rs.id
                   JOIN rubbings rt ON f.target_rubbing_id = rt.id
                   ORDER BY f.created_at DESC
                   LIMIT ? OFFSET ?""",
                (limit, offset),
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def count_by_type(feedback_type: Optional[str] = None) -> int:
        with get_db_connection() as conn:
            if feedback_type:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM similarity_feedbacks WHERE feedback_type = ?",
                    (feedback_type,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM similarity_feedbacks"
                ).fetchone()
            return row["cnt"]

    @staticmethod
    def get_statistics() -> Dict[str, Any]:
        with get_db_connection() as conn:
            total = conn.execute(
                "SELECT COUNT(*) as cnt FROM similarity_feedbacks"
            ).fetchone()["cnt"]
            correct = conn.execute(
                "SELECT COUNT(*) as cnt FROM similarity_feedbacks WHERE feedback_type = ?",
                (SimilarityFeedbackDAO.FEEDBACK_CORRECT,),
            ).fetchone()["cnt"]
            wrong = conn.execute(
                "SELECT COUNT(*) as cnt FROM similarity_feedbacks WHERE feedback_type = ?",
                (SimilarityFeedbackDAO.FEEDBACK_WRONG,),
            ).fetchone()["cnt"]
            return {
                "total": total,
                "correct": correct,
                "wrong": wrong,
                "accuracy": round(correct / total * 100, 2) if total > 0 else 0,
            }


class WeightHistoryDAO:
    @staticmethod
    def create(data: Dict[str, Any]) -> int:
        with get_db_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO weight_history
                   (contour_weight, texture_weight, adjustment_reason, feedback_count)
                   VALUES (?, ?, ?, ?)""",
                (
                    data.get("contour_weight"),
                    data.get("texture_weight"),
                    data.get("adjustment_reason", ""),
                    data.get("feedback_count", 0),
                ),
            )
            return cursor.lastrowid

    @staticmethod
    def get_latest() -> Optional[Dict[str, Any]]:
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT * FROM weight_history ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def list_all(limit: int = 100) -> List[Dict[str, Any]]:
        with get_db_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM weight_history ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_current_weights() -> Tuple[float, float]:
        latest = WeightHistoryDAO.get_latest()
        if latest:
            return latest["contour_weight"], latest["texture_weight"]
        return 0.4, 0.6


class SystemSettingDAO:
    KEY_CONTOUR_WEIGHT = "contour_weight"
    KEY_TEXTURE_WEIGHT = "texture_weight"
    KEY_WEIGHT_ADJUSTMENT_ENABLED = "weight_adjustment_enabled"
    KEY_FEEDBACKS_SINCE_ADJUSTMENT = "feedbacks_since_adjustment"

    @staticmethod
    def get(key: str, default: Optional[str] = None) -> Optional[str]:
        with get_db_connection() as conn:
            row = conn.execute(
                "SELECT setting_value FROM system_settings WHERE setting_key = ?",
                (key,),
            ).fetchone()
            return row["setting_value"] if row else default

    @staticmethod
    def set(key: str, value: str) -> None:
        with get_db_connection() as conn:
            conn.execute(
                """INSERT INTO system_settings (setting_key, setting_value, updated_at)
                   VALUES (?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(setting_key) DO UPDATE SET
                       setting_value = excluded.setting_value,
                       updated_at = CURRENT_TIMESTAMP""",
                (key, value),
            )

    @staticmethod
    def get_float(key: str, default: float = 0.0) -> float:
        val = SystemSettingDAO.get(key)
        if val is None:
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def set_float(key: str, value: float) -> None:
        SystemSettingDAO.set(key, str(value))

    @staticmethod
    def get_int(key: str, default: int = 0) -> int:
        val = SystemSettingDAO.get(key)
        if val is None:
            return default
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def set_int(key: str, value: int) -> None:
        SystemSettingDAO.set(key, str(value))

    @staticmethod
    def get_bool(key: str, default: bool = False) -> bool:
        val = SystemSettingDAO.get(key)
        if val is None:
            return default
        return val.lower() in ("true", "1", "yes")

    @staticmethod
    def set_bool(key: str, value: bool) -> None:
        SystemSettingDAO.set(key, "true" if value else "false")
