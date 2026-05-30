from __future__ import annotations

import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


BASE_URL = "http://127.0.0.1:8000"


def request_json(method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(BASE_URL + path, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body)
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        return exc.code, json.loads(body)
    except URLError as exc:
        raise RuntimeError(f"无法连接后端 {BASE_URL}: {exc}") from exc


def assert_true(name: str, value: bool, detail: object = "") -> None:
    if not value:
        raise AssertionError(f"{name} failed: {detail}")
    print(f"[OK] {name}")


def main() -> None:
    status, body = request_json("GET", "/health")
    assert_true("health", status == 200 and body.get("status") == "ok", body)

    status, body = request_json("GET", "/api/self-test")
    assert_true("self-test", status == 200 and bool(body.get("ok")), body)

    status, body = request_json("GET", "/api/knowledge/stats")
    assert_true("knowledge-stats", status == 200 and body.get("chunk_count", 0) > 0, body)

    status, body = request_json("GET", "/api/dataset/stats")
    rows = body.get("files", {}).get("dataset_samples.jsonl", {}).get("rows", 0)
    assert_true("dataset-stats", status == 200 and rows >= 100, body)

    q = quote("胸前区疼出汗")
    status, body = request_json("GET", f"/api/search?q={q}&top_k=3")
    assert_true("search", status == 200 and len(body.get("results", [])) > 0, body)

    status, body = request_json(
        "POST",
        "/api/analyze",
        {
            "complaint": "活动后胸前区疼还出汗",
            "history": "每次持续十分钟，休息缓解，既往高血压",
            "question": "要不要去急诊",
            "top_k": 6,
        },
    )
    report = body.get("report", {})
    assert_true("analyze", status == 200 and "心血管" in report.get("primary_diagnosis", ""), body)

    status, body = request_json("GET", "/api/inferences?limit=1")
    assert_true("inferences", status == 200 and len(body.get("inferences", [])) >= 1, body)

    status, body = request_json("POST", "/api/admin/backup", {})
    assert_true("backup", status == 200 and body.get("backup_path"), body)

    print("[OK] backend smoke test passed")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        sys.exit(1)
