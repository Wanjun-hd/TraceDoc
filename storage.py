import json
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "tracedoc_backend.sqlite3"


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                gender TEXT,
                age TEXT,
                phone TEXT,
                allergy TEXT,
                past_history TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS inferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER,
                complaint TEXT NOT NULL,
                history TEXT,
                question TEXT,
                backend_mode TEXT,
                report_json TEXT NOT NULL,
                trace_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(patient_id) REFERENCES patients(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                detail_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def create_patient(data: Dict[str, Any]) -> int:
    init_db()
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO patients (name, gender, age, phone, allergy, past_history)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(data.get("name") or "匿名患者"),
                str(data.get("gender") or ""),
                str(data.get("age") or ""),
                str(data.get("phone") or ""),
                str(data.get("allergy") or ""),
                str(data.get("past_history") or ""),
            ),
        )
        return int(cur.lastrowid)


def list_patients(limit: int = 50) -> List[Dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM patients ORDER BY id DESC LIMIT ?",
            (max(1, min(int(limit), 500)),),
        ).fetchall()
    return [dict(row) for row in rows]


def save_inference(
    *,
    form_data: Dict[str, Any],
    result: Dict[str, Any],
    backend_mode: str = "local_rag",
    patient_id: Optional[int] = None,
) -> int:
    init_db()
    report = result.get("report", {}) if isinstance(result, dict) else {}
    trace = result.get("traceability", {}) if isinstance(result, dict) else {}
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO inferences
              (patient_id, complaint, history, question, backend_mode, report_json, trace_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                patient_id,
                str(form_data.get("complaint") or ""),
                str(form_data.get("history") or ""),
                str(form_data.get("question") or ""),
                backend_mode,
                json.dumps(report, ensure_ascii=False),
                json.dumps(trace, ensure_ascii=False),
            ),
        )
        return int(cur.lastrowid)


def list_inferences(limit: int = 50) -> List[Dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM inferences ORDER BY id DESC LIMIT ?",
            (max(1, min(int(limit), 500)),),
        ).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        for key in ("report_json", "trace_json"):
            try:
                item[key] = json.loads(item[key])
            except Exception:
                pass
        out.append(item)
    return out


def record_event(event_type: str, detail: Dict[str, Any]) -> int:
    init_db()
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO knowledge_events (event_type, detail_json) VALUES (?, ?)",
            (event_type, json.dumps(detail, ensure_ascii=False)),
        )
        return int(cur.lastrowid)


def list_events(limit: int = 50) -> List[Dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM knowledge_events ORDER BY id DESC LIMIT ?",
            (max(1, min(int(limit), 500)),),
        ).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        try:
            item["detail_json"] = json.loads(item["detail_json"])
        except Exception:
            pass
        out.append(item)
    return out


def counts() -> Dict[str, int]:
    init_db()
    with connect() as conn:
        return {
            "patients": int(conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]),
            "inferences": int(conn.execute("SELECT COUNT(*) FROM inferences").fetchone()[0]),
            "knowledge_events": int(conn.execute("SELECT COUNT(*) FROM knowledge_events").fetchone()[0]),
        }


def export_all() -> Dict[str, Any]:
    return {
        "patients": list_patients(limit=500),
        "inferences": list_inferences(limit=500),
        "events": list_events(limit=500),
        "counts": counts(),
    }


def backup_db() -> str:
    init_db()
    backup_dir = BASE_DIR / "data" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"tracedoc_backend_{time.strftime('%Y%m%d_%H%M%S')}.sqlite3"
    shutil.copy2(DB_PATH, target)
    return str(target)
