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
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM rubbings WHERE 1=1"
        params: List[Any] = []
        if era:
            query += " AND era = ?"
            params.append(era)
        if keyword:
            query += " AND (code LIKE ? OR inscription LIKE ? OR excavation_site LIKE ?)"
            params.extend([f"%{keyword}%"] * 3)
        if has_contour_only:
            query += " AND has_valid_contour = 1"
        query += " ORDER BY created_at DESC"
        with get_db_connection() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
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
