import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

LOG_PATH = Path(__file__).resolve().parent / "data" / "audit_log.jsonl"


def write_audit(event: str, payload: Dict[str, Any]) -> None:
    """
    轻量审计日志：JSONL 持久化到 data/audit_log.jsonl。
    失败时静默，避免影响主流程。
    """
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        item = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "payload": payload,
        }
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    except Exception:
        pass
