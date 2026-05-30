import os
import json
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Tuple

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from few_shot import load_examples
from local_rag_client import (
    SUPPORTED_SUFFIXES,
    _build_or_load_index,
    _load_symptom_routes,
    _score_fused,
    call_local_rag,
)
from research.pseudo_label_generator import generate as generate_pseudo_labels
from storage import (
    backup_db,
    create_patient,
    counts as db_counts,
    export_all,
    init_db,
    list_events,
    list_inferences,
    list_patients,
    record_event,
    save_inference,
)
from tools.build_demo_knowledge_base import main as build_demo_knowledge_base


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_KB_DIR = os.getenv("LOCAL_RAG_KB_DIR", str(BASE_DIR / "核心三库"))
DEFAULT_LLM_BASE_URL = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
DEFAULT_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "qwen2.5:7b")
DEFAULT_LLM_API_KEY = os.getenv("LOCAL_LLM_API_KEY", "")
init_db()


def _json(data: Dict[str, Any], status_code: int = 200) -> JSONResponse:
    return JSONResponse(data, status_code=status_code)


def _error(message: str, status_code: int = 400, *, detail: Any = None) -> JSONResponse:
    payload: Dict[str, Any] = {"ok": False, "error": message}
    if detail is not None:
        payload["detail"] = detail
    return _json(payload, status_code=status_code)


def _clamp_int(value: Any, default: int, min_value: int, max_value: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(min_value, min(max_value, parsed))


def _clamp_float(value: Any, default: float, min_value: float, max_value: float) -> float:
    try:
        parsed = float(value)
    except Exception:
        parsed = default
    return max(min_value, min(max_value, parsed))


async def _read_json_object(request: Request) -> Tuple[Dict[str, Any] | None, JSONResponse | None]:
    try:
        payload = await request.json()
    except Exception:
        return None, _error("请求体必须是 JSON。", status_code=400)
    if not isinstance(payload, dict):
        return None, _error("JSON 请求体必须是对象。", status_code=400)
    return payload, None


def _validate_form_data(form_data: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    complaint = str(form_data.get("complaint") or "").strip()
    question = str(form_data.get("question") or "").strip()
    if not complaint and not question:
        errors.append("请至少提供 complaint 或 question。")
    age = form_data.get("age")
    if str(age or "").strip() and str(age) != "未填写":
        try:
            age_i = int(age)
            if age_i < 0 or age_i > 120:
                errors.append("age 必须在 0-120 之间。")
        except Exception:
            errors.append("age 必须是数字。")
    for key in ["complaint", "history", "question"]:
        value = str(form_data.get(key) or "")
        if len(value) > 4000:
            errors.append(f"{key} 过长，最多 4000 字符。")
    return errors


def _default_form_data(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": str(payload.get("name") or "匿名患者"),
        "gender": str(payload.get("gender") or "未填写"),
        "age": str(payload.get("age") or "未填写"),
        "phone": str(payload.get("phone") or ""),
        "complaint": str(payload.get("complaint") or payload.get("question") or ""),
        "history": str(payload.get("history") or ""),
        "allergy": str(payload.get("allergy") or "未填写"),
        "past_history": str(payload.get("past_history") or "未填写"),
        "question": str(payload.get("question") or payload.get("complaint") or ""),
    }


async def health(_: Request) -> JSONResponse:
    kb_path = Path(DEFAULT_KB_DIR)
    db_ok = True
    db_error = ""
    try:
        db_state = db_counts()
    except Exception as exc:
        db_ok = False
        db_state = {}
        db_error = str(exc)
    return _json(
        {
            "ok": True,
            "status": "ok",
            "service": "TraceDoc backend",
            "kb_dir": str(kb_path),
            "kb_exists": kb_path.is_dir(),
            "db_ok": db_ok,
            "db_counts": db_state,
            "db_error": db_error,
            "time": int(time.time()),
        }
    )


async def knowledge_stats(request: Request) -> JSONResponse:
    kb_dir = request.query_params.get("kb_dir") or DEFAULT_KB_DIR
    kb_path = Path(kb_dir)
    if not kb_path.is_dir():
        return _error(f"知识库目录不存在：{kb_dir}", status_code=404)

    files = [p for p in kb_path.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES]
    index = _build_or_load_index(kb_path)
    chunks = index.get("chunks", []) if isinstance(index, dict) else []
    by_level: Dict[str, int] = {}
    for item in chunks:
        level = str(item.get("level", "unknown")) if isinstance(item, dict) else "unknown"
        by_level[level] = by_level.get(level, 0) + 1

    return _json(
        {
            "ok": True,
            "kb_dir": str(kb_path),
            "file_count": len(files),
            "chunk_count": len(chunks),
            "levels": by_level,
            "files": [{"name": p.name, "size": p.stat().st_size} for p in files],
        }
    )


async def root(_: Request) -> JSONResponse:
    return _json(
        {
            "ok": True,
            "service": "TraceDoc backend",
            "endpoints": [
                "GET /health",
                "POST /api/analyze",
                "GET /api/search?q=...",
                "GET /api/knowledge/stats",
                "GET /api/knowledge/preview",
                "GET /api/dataset/stats",
                "POST /api/pseudo-labels/generate",
                "POST /api/admin/rebuild-demo-data",
                "POST /api/admin/backup",
                "GET /api/export/all",
                "GET /api/self-test",
                "GET/POST /api/patients",
                "GET /api/inferences",
            ],
        }
    )


async def symptom_routes(_: Request) -> JSONResponse:
    return _json({"ok": True, "routes": _load_symptom_routes()})


async def examples(_: Request) -> JSONResponse:
    data_dir = BASE_DIR / "data"
    unlabeled = []
    path = data_dir / "unlabeled_queries.jsonl"
    if path.is_file():
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    unlabeled.append(obj)
    return _json({"ok": True, "few_shot_examples": load_examples(), "unlabeled_queries": unlabeled})


async def dataset_stats(_: Request) -> JSONResponse:
    files = {}
    for name in ["dataset_samples.jsonl", "unlabeled_queries.jsonl", "pseudo_labeled_pairs.jsonl"]:
        path = BASE_DIR / "data" / name
        count = 0
        if path.is_file():
            with path.open("r", encoding="utf-8") as f:
                count = sum(1 for line in f if line.strip())
        files[name] = {"exists": path.is_file(), "rows": count, "path": str(path)}
    return _json({"ok": True, "files": files, "few_shot_count": len(load_examples())})


async def search(request: Request) -> JSONResponse:
    q = (request.query_params.get("q") or "").strip()
    if not q:
        return _error("请提供查询参数 q。", status_code=400)
    top_k = _clamp_int(request.query_params.get("top_k"), 8, 1, 50)
    kb_dir = request.query_params.get("kb_dir") or DEFAULT_KB_DIR
    kb_path = Path(kb_dir)
    if not kb_path.is_dir():
        return _error(f"知识库目录不存在：{kb_dir}", status_code=404)
    index = _build_or_load_index(kb_path)
    rows = []
    for score, item in _score_fused(q, index, top_k=top_k):
        rows.append(
            {
                "score": round(float(score), 4),
                "evidence_id": item.get("evidence_id"),
                "level": item.get("level"),
                "source": item.get("source"),
                "snippet": str(item.get("text", ""))[:360],
            }
        )
    return _json({"ok": True, "query": q, "top_k": top_k, "results": rows})


async def knowledge_preview(request: Request) -> JSONResponse:
    kb_dir = request.query_params.get("kb_dir") or DEFAULT_KB_DIR
    limit = _clamp_int(request.query_params.get("limit"), 12, 1, 100)
    kb_path = Path(kb_dir)
    if not kb_path.is_dir():
        return _error(f"知识库目录不存在：{kb_dir}", status_code=404)
    files = [p for p in kb_path.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES]
    preview = []
    for p in files[:limit]:
        text = ""
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")[:600]
        except Exception:
            text = ""
        preview.append({"name": p.name, "size": p.stat().st_size, "preview": text})
    return _json({"ok": True, "kb_dir": str(kb_path), "files": preview})


async def patients(request: Request) -> JSONResponse:
    if request.method == "GET":
        limit = _clamp_int(request.query_params.get("limit"), 50, 1, 500)
        return _json({"ok": True, "patients": list_patients(limit=limit)})

    payload, err = await _read_json_object(request)
    if err:
        return err
    assert payload is not None
    if not str(payload.get("name") or "").strip():
        return _error("name 不能为空。", status_code=400)
    patient_id = create_patient(payload)
    record_event("patient_create", {"patient_id": patient_id})
    return _json({"ok": True, "id": patient_id})


async def inferences(request: Request) -> JSONResponse:
    limit = _clamp_int(request.query_params.get("limit"), 50, 1, 500)
    return _json({"ok": True, "inferences": list_inferences(limit=limit)})


async def events(request: Request) -> JSONResponse:
    limit = _clamp_int(request.query_params.get("limit"), 50, 1, 500)
    return _json({"ok": True, "events": list_events(limit=limit)})


async def pseudo_labels(_: Request) -> JSONResponse:
    try:
        rows = generate_pseudo_labels()
    except Exception as exc:
        return _error(str(exc), status_code=500)
    output = BASE_DIR / "data" / "pseudo_labeled_pairs.jsonl"
    record_event("pseudo_label_generate", {"rows": rows, "output": str(output)})
    return _json({"ok": True, "status": "ok", "rows": rows, "output": str(output)})


async def rebuild_demo_data(_: Request) -> JSONResponse:
    index_path = Path(DEFAULT_KB_DIR) / ".local_rag_index.pkl"
    try:
        if index_path.is_file():
            index_path.unlink()
        build_demo_knowledge_base()
        pseudo_rows = generate_pseudo_labels()
        _build_or_load_index(Path(DEFAULT_KB_DIR))
        record_event("rebuild_demo_data", {"pseudo_rows": pseudo_rows, "kb_dir": DEFAULT_KB_DIR})
    except Exception as exc:
        return _error(str(exc), status_code=500, detail=traceback.format_exc(limit=3))
    return _json({"ok": True, "status": "rebuilt", "pseudo_rows": pseudo_rows})


async def backup(_: Request) -> JSONResponse:
    try:
        path = backup_db()
        record_event("backup_db", {"path": path})
    except Exception as exc:
        return _error(str(exc), status_code=500)
    return _json({"ok": True, "backup_path": path})


async def export_all_data(_: Request) -> JSONResponse:
    return _json({"ok": True, "data": export_all()})


async def self_test(_: Request) -> JSONResponse:
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: bool, detail: Any = "") -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    kb_path = Path(DEFAULT_KB_DIR)
    add("knowledge_dir_exists", kb_path.is_dir(), str(kb_path))
    try:
        stats_files = [p for p in kb_path.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES]
        add("knowledge_files", len(stats_files) >= 3, len(stats_files))
    except Exception as exc:
        add("knowledge_files", False, str(exc))
    try:
        index = _build_or_load_index(kb_path)
        add("knowledge_index", int(index.get("n_docs", 0)) > 0, index.get("n_docs", 0))
    except Exception as exc:
        add("knowledge_index", False, str(exc))
    try:
        add("database", True, db_counts())
    except Exception as exc:
        add("database", False, str(exc))
    try:
        result = call_local_rag(
            form_data=_default_form_data(
                {
                    "complaint": "咳嗽发热三天",
                    "history": "咳黄痰，低热",
                    "question": "可能是什么病，下一步怎么办",
                }
            ),
            kb_dir=DEFAULT_KB_DIR,
            llm_base_url="http://127.0.0.1:1/v1",
            llm_model="none",
            top_k=3,
        )
        add("local_rag_fallback", bool(result.get("report")), result.get("report", {}).get("primary_diagnosis", ""))
    except Exception as exc:
        add("local_rag_fallback", False, str(exc))

    ok = all(c["ok"] for c in checks)
    return _json({"ok": ok, "checks": checks}, status_code=200 if ok else 500)


async def analyze(request: Request) -> JSONResponse:
    payload, err = await _read_json_object(request)
    if err:
        return err
    assert payload is not None

    form_data = payload.get("form_data")
    if not isinstance(form_data, dict):
        form_data = _default_form_data(payload)

    validation_errors = _validate_form_data(form_data)
    if validation_errors:
        return _error("请求参数校验失败。", status_code=400, detail=validation_errors)

    kb_dir = str(payload.get("kb_dir") or DEFAULT_KB_DIR)
    if not Path(kb_dir).is_dir():
        return _error(f"知识库目录不存在：{kb_dir}", status_code=404)

    try:
        result = call_local_rag(
            form_data=form_data,
            kb_dir=kb_dir,
            llm_base_url=str(payload.get("llm_base_url") or DEFAULT_LLM_BASE_URL),
            llm_model=str(payload.get("llm_model") or DEFAULT_LLM_MODEL),
            llm_api_key=str(payload.get("llm_api_key") or DEFAULT_LLM_API_KEY),
            normalize_terms=bool(payload.get("normalize_terms", True)),
            few_shot_max=_clamp_int(payload.get("few_shot_max"), 2, 0, 10),
            top_k=_clamp_int(payload.get("top_k"), 6, 1, 20),
            temperature=_clamp_float(payload.get("temperature"), 0.2, 0.0, 1.5),
        )
    except Exception as exc:
        record_event("inference_error", {"error": str(exc), "complaint": str(form_data.get("complaint", ""))[:120]})
        return _error(str(exc), status_code=500)

    patient_id = payload.get("patient_id")
    if patient_id is not None:
        try:
            patient_id = int(patient_id)
        except Exception:
            patient_id = None
    inference_id = save_inference(
        form_data=form_data,
        result=result,
        backend_mode="local_rag",
        patient_id=patient_id,
    )
    result["_backend"] = {"inference_id": inference_id, "persisted": True}
    return _json(result)


routes = [
    Route("/", root, methods=["GET"]),
    Route("/health", health, methods=["GET"]),
    Route("/api/knowledge/stats", knowledge_stats, methods=["GET"]),
    Route("/api/knowledge/preview", knowledge_preview, methods=["GET"]),
    Route("/api/dataset/stats", dataset_stats, methods=["GET"]),
    Route("/api/routes", symptom_routes, methods=["GET"]),
    Route("/api/examples", examples, methods=["GET"]),
    Route("/api/search", search, methods=["GET"]),
    Route("/api/patients", patients, methods=["GET", "POST"]),
    Route("/api/inferences", inferences, methods=["GET"]),
    Route("/api/events", events, methods=["GET"]),
    Route("/api/pseudo-labels/generate", pseudo_labels, methods=["POST"]),
    Route("/api/admin/rebuild-demo-data", rebuild_demo_data, methods=["POST"]),
    Route("/api/admin/backup", backup, methods=["POST"]),
    Route("/api/export/all", export_all_data, methods=["GET"]),
    Route("/api/self-test", self_test, methods=["GET"]),
    Route("/api/analyze", analyze, methods=["POST"]),
]

async def unhandled_exception(_: Request, exc: Exception) -> JSONResponse:
    try:
        record_event("unhandled_exception", {"error": str(exc), "trace": traceback.format_exc(limit=3)})
    except Exception:
        pass
    return _error("服务器内部错误。", status_code=500, detail=str(exc))


app = Starlette(debug=False, routes=routes, exception_handlers={Exception: unhandled_exception})
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
