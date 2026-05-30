import json
import math
import pickle
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from fs_trace_rag import prepare_rag_form
from ragflow_client import normalize_answer

SUPPORTED_SUFFIXES = {".txt", ".md", ".csv", ".json", ".pdf"}
INDEX_FILE_NAME = ".local_rag_index.pkl"
INDEX_SCHEMA_VERSION = 3
ROUTES_JSON_PATH = Path(__file__).resolve().parent / "data" / "symptom_routes.json"
LEVEL_CREDIBILITY = {"guideline": 1.0, "literature": 0.7, "case": 0.5, "unknown": 0.3}


def _looks_binary(data: bytes) -> bool:
    if not data:
        return False
    if b"\x00" in data[:4096]:
        return True
    head = data[:8192]
    if head.startswith(b"PK") and (b"[Content_Types].xml" in head or b"word/" in head):
        return True
    printable = sum(1 for b in data[:4096] if b in b"\n\r\t" or 32 <= b <= 126 or b >= 0x80)
    return printable / max(1, len(data[:4096])) < 0.75


def _decode_text_bytes(data: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "gb18030", "gbk", "big5"):
        try:
            text = data.decode(enc)
            if text.strip():
                return text
        except Exception:
            continue
    return data.decode("latin-1", errors="ignore")


def _load_symptom_routes() -> List[Dict[str, Any]]:
    """
    从 JSON 加载“症状 -> 诊疗路径”配置，便于后续仅改配置文件。
    """
    try:
        if ROUTES_JSON_PATH.is_file():
            obj = json.loads(ROUTES_JSON_PATH.read_text(encoding="utf-8"))
            routes = obj.get("routes") if isinstance(obj, dict) else None
            if isinstance(routes, list):
                valid = []
                for r in routes:
                    if not isinstance(r, dict):
                        continue
                    if not isinstance(r.get("keywords"), list):
                        continue
                    valid.append(r)
                if valid:
                    return valid
    except Exception:
        pass
    return []


def _clean_text(text: str) -> str:
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def _read_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".csv", ".json"}:
        try:
            raw = path.read_bytes()
        except Exception:
            return ""
        if _looks_binary(raw):
            return ""
        return _clean_text(_decode_text_bytes(raw))
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader  # type: ignore
        except Exception:
            PdfReader = None  # type: ignore
        if PdfReader is not None:
            try:
                reader = PdfReader(str(path))
                text = _clean_text("\n".join((p.extract_text() or "") for p in reader.pages))
                if text:
                    return text
            except Exception:
                pass
        try:
            import fitz  # type: ignore

            doc = fitz.open(str(path))
            text = _clean_text("\n".join((p.get_text("text") or "") for p in doc))
            doc.close()
            if text:
                return text
        except Exception:
            return ""
    return ""


def _chunk_text(text: str, chunk_size: int = 360, overlap: int = 60) -> List[str]:
    if not text:
        return []
    chunks: List[str] = []
    step = max(1, chunk_size - overlap)
    for i in range(0, len(text), step):
        part = text[i : i + chunk_size]
        if part.strip():
            chunks.append(part.strip())
    return chunks


def _tokenize(text: str) -> List[str]:
    s = text.lower()
    words = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]", s)
    # 增加中文双字 token，提升短语检索稳定性
    han = [w for w in words if re.fullmatch(r"[\u4e00-\u9fff]", w)]
    bigrams = [han[i] + han[i + 1] for i in range(len(han) - 1)]
    return words + bigrams


def _extract_symptom_terms(query: str) -> List[str]:
    """
    从用户问题中抽取症状词，作为证据片段硬过滤条件。
    先用内置症状词表，再回退到中文双字词。
    """
    # 词表越靠前优先级越高（越具体的症状放前面）
    symptom_lexicon = [
        "吐血", "呕血", "鲜红色血液", "黑便", "消化道出血",
        "跌倒", "头部出血", "嗜睡", "头部外伤", "颅内出血",
        "烫伤", "烧伤", "水泡", "灼痛", "冻伤", "低温暴露", "麻痹",
        "伤口流脓", "流脓", "化脓", "黑色分泌物", "破溃", "伤口感染", "蜂窝织炎",
        "鼻流血", "鼻出血", "耳痛流脓", "耳道流脓",
        "低血糖", "空腹", "心悸",
        "咳嗽", "咳痰", "黄痰", "痰黄", "咳黄痰", "咯血",
        "呼吸困难", "气短", "胸闷", "胸痛",
        "海鲜", "啤酒", "饮食不洁", "食物中毒", "腹痛", "肚子疼", "肚子痛", "胃痛", "腹泻", "便秘", "恶心", "呕吐",
        "皮疹", "风疹", "发疹", "皮肤痒", "瘙痒", "痒", "脸痒", "面部瘙痒", "红肿", "脸肿", "面部红肿", "荨麻疹", "食物过敏", "过敏",
        "尿频", "尿急", "尿痛", "血尿",
        "头痛", "头晕", "意识障碍", "晕厥",
        "崴脚", "脚崴", "脚踝痛", "脚踝肿", "踝关节痛", "踝关节肿", "踝关节扭伤", "扭伤", "不能负重", "外伤",
        "肘部疼痛", "肘关节痛", "关节炎", "关节痛", "关节肿",
        "黄疸",
        "发热", "发烧", "寒战",
        "乏力", "食欲下降",
    ]
    q = query.lower()
    hits = [w for w in symptom_lexicon if w in q]
    if hits:
        return hits
    han = re.findall(r"[\u4e00-\u9fff]", q)
    # 回退为中文双字词，过滤过短噪声
    pairs = [han[i] + han[i + 1] for i in range(len(han) - 1)]
    return list(dict.fromkeys([p for p in pairs if len(p) >= 2]))[:12]


def _extract_relevant_snippet(text: str, terms: List[str], max_len: int = 90) -> str:
    """
    从证据片段中抽取与当前症状词直接相关的短句，减少跨病种混入。
    """
    if not text:
        return ""
    pieces = re.split(r"[。；;！!？?\n]", text)
    for p in pieces:
        s = p.strip()
        if not s:
            continue
        if terms and any(t in s for t in terms):
            return s[:max_len]
    return text[:max_len]


def _is_negated(text: str, term: str) -> bool:
    """
    判断 term 是否出现在否定语境中，例如“无发热/否认发热/未见发热/不发热”。
    只做轻量启发式：term 前 1-3 个字内出现否定词则认为否定。
    """
    if not text or not term:
        return False
    idx = text.find(term)
    if idx < 0:
        return False
    window = text[max(0, idx - 6) : idx]
    # “不”本身容易误伤（如“不适”），只识别更明确的否定模式
    return any(neg in window for neg in ["无", "没有", "未见", "否认", "不伴", "未", "不出现", "不再"])


def _level_by_path(path: Path, text_sample: str = "") -> str:
    # 先看文件名（最可靠），再看目录名，最后才看正文片段，避免“病例文本中出现指南词”导致误分层。
    file_name = path.name.lower()
    dir_part = path.parent.as_posix().lower()
    sample = text_sample[:120].lower()

    guideline_keys = ("指南", "共识", "规范", "诊疗", "guideline", "consensus")
    literature_keys = ("文献", "论文", "研究", "随机", "meta", "paper", "journal", "pubmed")
    case_keys = ("病例", "病案", "个案", "住院", "门诊", "脱敏", "case", "record")

    def has_any(s: str, keys: Tuple[str, ...]) -> bool:
        return any(k in s for k in keys)

    # 1) 文件名强优先
    if has_any(file_name, case_keys):
        return "case"
    if has_any(file_name, literature_keys):
        return "literature"
    if has_any(file_name, guideline_keys):
        return "guideline"

    # 2) 目录名次优先
    if has_any(dir_part, case_keys):
        return "case"
    if has_any(dir_part, literature_keys):
        return "literature"
    if has_any(dir_part, guideline_keys):
        return "guideline"

    # 3) 正文弱信号（打分）
    g = sum(1 for k in guideline_keys if k in sample)
    l = sum(1 for k in literature_keys if k in sample)
    c = sum(1 for k in case_keys if k in sample)
    if c > max(g, l):
        return "case"
    if l > max(g, c):
        return "literature"
    if g > 0:
        return "guideline"
    return "unknown"


def _build_signature(files: List[Path], chunk_size: int, overlap: int) -> List[Tuple[str, int, int]]:
    sig = []
    for p in files:
        st = p.stat()
        sig.append((str(p), int(st.st_mtime), int(st.st_size)))
    sig.sort()
    sig.append((f"chunk:{chunk_size}", overlap, len(files)))
    sig.append((f"schema:{INDEX_SCHEMA_VERSION}", 0, 0))
    return sig


def _safe_load_index(index_path: Path) -> Optional[Dict[str, Any]]:
    if not index_path.is_file():
        return None
    try:
        with index_path.open("rb") as f:
            obj = pickle.load(f)
        if isinstance(obj, dict) and "chunks" in obj and "signature" in obj:
            return obj
    except Exception:
        return None
    return None


def _build_or_load_index(kb_path: Path, chunk_size: int = 700, overlap: int = 120) -> Dict[str, Any]:
    # //AI辅助生成：DeepSeek，2026-04-21
    files = [p for p in kb_path.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES]
    signature = _build_signature(files, chunk_size, overlap)
    index_path = kb_path / INDEX_FILE_NAME
    cached = _safe_load_index(index_path)
    if cached and cached.get("signature") == signature:
        return cached

    chunks: List[Dict[str, Any]] = []
    df: Dict[str, int] = {}
    evidence_idx = 0
    for p in files:
        raw_text = _read_text(p)
        if not raw_text:
            continue
        level = _level_by_path(p, raw_text)
        for piece in _chunk_text(raw_text, chunk_size=chunk_size, overlap=overlap):
            toks = _tokenize(piece)
            if not toks:
                continue
            tf = Counter(toks)
            for t in tf.keys():
                df[t] = df.get(t, 0) + 1
            chunks.append(
                {
                    "evidence_id": f"E{evidence_idx:06d}",
                    "source": p.name,
                    "source_path": str(p),
                    "level": level,
                    "text": piece,
                    "tf": dict(tf),
                    "doc_len": sum(tf.values()),
                }
            )
            evidence_idx += 1

    n_docs = len(chunks)
    avgdl = (sum(c["doc_len"] for c in chunks) / n_docs) if n_docs > 0 else 0.0
    idf = {t: math.log((n_docs - d + 0.5) / (d + 0.5) + 1) for t, d in df.items()}

    # 为向量检索准备稀疏 TF-IDF + 范数
    for c in chunks:
        vec = {}
        for t, cnt in c["tf"].items():
            if t in idf:
                vec[t] = (1.0 + math.log(cnt)) * idf[t]
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        c["tfidf_vec"] = vec
        c["vec_norm"] = norm

    index = {
        "signature": signature,
        "chunks": chunks,
        "idf": idf,
        "avgdl": avgdl,
        "n_docs": n_docs,
    }
    try:
        with index_path.open("wb") as f:
            pickle.dump(index, f)
    except Exception:
        pass
    return index


def _score_fused(query: str, index: Dict[str, Any], top_k: int) -> List[Tuple[float, Dict[str, Any]]]:
    chunks: List[Dict[str, Any]] = index.get("chunks", [])
    idf: Dict[str, float] = index.get("idf", {})
    avgdl = float(index.get("avgdl", 0.0)) or 1.0
    if not chunks:
        return []

    q_toks = _tokenize(query)
    q_tf = Counter(q_toks)
    k1, b = 1.5, 0.75

    # 查询向量
    q_vec = {}
    for t, cnt in q_tf.items():
        if t in idf:
            q_vec[t] = (1.0 + math.log(cnt)) * idf[t]
    q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0

    scored = []
    for c in chunks:
        # BM25
        bm25 = 0.0
        doc_len = max(1, int(c["doc_len"]))
        tf_doc = c["tf"]
        for t, qf in q_tf.items():
            f = tf_doc.get(t, 0)
            if f <= 0:
                continue
            term_idf = idf.get(t, 0.0)
            bm25 += term_idf * (f * (k1 + 1.0)) / (f + k1 * (1.0 - b + b * doc_len / avgdl))

        # 向量相似度
        dot = 0.0
        c_vec = c["tfidf_vec"]
        for t, v in q_vec.items():
            dot += v * c_vec.get(t, 0.0)
        cos = dot / (q_norm * float(c["vec_norm"]))

        # 融合分数：BM25 + 向量 + 证据可信度权重
        fused = 0.65 * bm25 + 0.35 * cos
        fused += 0.05 * LEVEL_CREDIBILITY.get(c["level"], 0.3)
        scored.append((fused, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[: max(1, top_k * 3)]


def _filter_by_symptom_terms(
    scored: List[Tuple[float, Dict[str, Any]]],
    symptom_terms: List[str],
    min_score: float = 0.08,
    query: str = "",
    gender: str = "",
) -> List[Tuple[float, Dict[str, Any]]]:
    """
    仅保留与症状词有直接命中的证据；并做最低相关性阈值过滤，
    避免“把整份不相关指南塞进来”。
    """
    if not scored:
        return []
    out: List[Tuple[float, Dict[str, Any]]] = []
    # 如果主诉中包含更具体的核心呼吸道症状，则强制至少命中其一，避免因“无发热”等否定词误入。
    core_terms = [t for t in symptom_terms if t in ["咳嗽", "咳痰", "黄痰", "痰黄", "咳黄痰", "咯血"]]
    gender_text = str(gender).strip().lower()
    gynecology_terms = ["月经", "阴道", "妊娠", "孕", "盆腔", "妇科", "宫", "下腹坠痛"]
    query_has_gynecology = any(t in query for t in gynecology_terms)
    male_gender = gender_text in {"男", "男性", "male", "m"}
    for score, item in scored:
        if score < min_score:
            continue
        text = item["text"]
        if any(t in text for t in gynecology_terms):
            if male_gender or not query_has_gynecology:
                continue
        if symptom_terms:
            hits = [t for t in symptom_terms if (t in text and not _is_negated(text, t))]
            if not hits:
                continue
            if core_terms and not any(t in hits for t in core_terms):
                continue
            out.append((score, item))
        else:
            out.append((score, item))
    return out


def _rebalance_levels(scored: List[Tuple[float, Dict[str, Any]]], top_k: int) -> List[Tuple[float, Dict[str, Any]]]:
    level_need = {"guideline": 1, "literature": 1, "case": 1}
    picked: List[Tuple[float, Dict[str, Any]]] = []
    used = set()
    # 先保证三层尽量都有
    for lvl in ("guideline", "literature", "case"):
        for i, item in enumerate(scored):
            if i in used:
                continue
            if item[1]["level"] == lvl:
                picked.append(item)
                used.add(i)
                break
    # 再按总分补齐
    for i, item in enumerate(scored):
        if len(picked) >= top_k:
            break
        if i in used:
            continue
        picked.append(item)
        used.add(i)
    return picked


def _select_focus_by_level(
    scored: List[Tuple[float, Dict[str, Any]]],
    *,
    per_level: int = 1,
    max_total: int = 4,
) -> List[Tuple[float, Dict[str, Any]]]:
    """
    证据精选：每层最多 N 条，且总量受限，避免“证据原文”过载。
    """
    buckets = {"guideline": [], "literature": [], "case": [], "unknown": []}
    for item in scored:
        buckets.get(item[1]["level"], buckets["unknown"]).append(item)

    if buckets["literature"]:
        buckets["literature"].sort(
            key=lambda x: (
                0 if "PubMed" in str(x[1].get("source", "")) else 1,
                -float(x[0]),
            )
        )

    picked: List[Tuple[float, Dict[str, Any]]] = []
    for lvl in ("guideline", "literature", "case"):
        picked.extend(buckets[lvl][:per_level])

    # 不足时由高分补齐
    if len(picked) < max_total:
        pool = []
        used_ids = {id(x[1]) for x in picked}
        for item in scored:
            if id(item[1]) not in used_ids:
                pool.append(item)
        picked.extend(pool[: max_total - len(picked)])

    return picked[:max_total]


def _build_evidence_blocks(top: List[Tuple[float, Dict[str, Any]]]) -> str:
    rows = []
    for i, (score, item) in enumerate(top, start=1):
        snippet = item["text"][:240].replace("\n", " ")
        rows.append(
            f"[{item.get('evidence_id', f'E{i}')}] level={item['level']} score={score:.4f} source={item['source']} snippet={snippet}"
        )
    return "\n".join(rows)


def _extract_heading(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return re.sub(r"^#+\s*", "", line).strip()
    m = re.search(r"#\s*([^#\n]{6,80})", text)
    return m.group(1).strip() if m else ""


def _extract_field(text: str, field: str) -> str:
    known_fields = [
        "主题",
        "中文关键词",
        "题名",
        "作者",
        "年份",
        "期刊",
        "文献类型",
        "DOI",
        "PubMed链接",
        "摘要",
    ]
    next_fields = [f for f in known_fields if f != field]
    boundary = "|".join(re.escape(f) for f in next_fields)
    m = re.search(rf"(?:^|\s){re.escape(field)}[:：]\s*(.*?)(?=\s+(?:{boundary})[:：]|\s+#\s*PMID[:：]|$)", text, flags=re.S)
    if not m:
        return ""
    return re.sub(r"\s+", " ", m.group(1)).strip()


def _compact_snippet(text: str, terms: List[str], max_len: int = 170) -> str:
    snippet = _extract_relevant_snippet(text, terms, max_len=max_len)
    snippet = re.sub(r"#+\s*", "", snippet)
    snippet = re.sub(r"\s+", " ", snippet).strip(" ：:;；")
    return snippet[:max_len] if snippet else text[:max_len]


def _format_evidence_record(score: float, item: Dict[str, Any], symptom_terms: List[str]) -> Dict[str, Any]:
    level = item.get("level", "unknown")
    text = str(item.get("text", ""))
    source_file = str(item.get("source", "本地知识库"))
    heading = _extract_heading(text)
    snippet = _compact_snippet(text, symptom_terms, max_len=180)
    evidence_id = item.get("evidence_id", "")

    if level == "guideline":
        clean_title = heading or "基层临床诊疗路径条目"
        title = f"临床指南条目：{clean_title}"
        source = f"指南库 | {source_file} | 本地整理版"
        support = (
            f"证据ID={evidence_id}，检索分数={float(score):.4f}。"
            "该条目属于指南/路径类知识，主要用于支持风险分层、检查选择和转诊判断。"
        )
        evidence_type = "guideline"
    elif level == "literature":
        pmid = ""
        if "PubMed" in source_file:
            pmid_match = re.search(r"PMID[:：]\s*(\d+)", text)
            pmid = pmid_match.group(1) if pmid_match else ""
            paper_title = _extract_field(text, "题名") or heading or "PubMed 文献记录"
            journal = _extract_field(text, "期刊") or "PubMed indexed journal"
            year = _extract_field(text, "年份") or "年份未标注"
            doi = _extract_field(text, "DOI") or "未提供"
            pub_type = _extract_field(text, "文献类型") or "Journal Article"
            abstract = _extract_field(text, "摘要")
            title = f"PubMed文献：{paper_title}"
            source = f"PubMed | PMID:{pmid or '未知'} | {journal} | {year} | DOI:{doi} | {pub_type}"
            snippet = (abstract or snippet)[:220]
            support = (
                f"证据ID={evidence_id}，检索分数={float(score):.4f}。"
                "该条目来自 PubMed 题录/摘要，包含 PMID、期刊、年份和文献类型，可作为文献级证据参考。"
            )
        else:
            clean_title = heading or "基层临床风险分层研究摘要"
            title = f"文献摘要：{clean_title}"
            source = f"文献库 | 模拟期刊摘要 | 2024 | {source_file}"
            support = (
                f"证据ID={evidence_id}，检索分数={float(score):.4f}。"
                "该条目为研究摘要/综述类证据，用于支持检查组合、风险因素和分层依据。"
            )
        evidence_type = "literature"
    elif level == "case":
        clean_title = heading or "相似脱敏病例"
        title = f"脱敏病例：{clean_title}"
        source = f"病例库 | 脱敏病例摘要 | {source_file}"
        support = (
            f"证据ID={evidence_id}，检索分数={float(score):.4f}。"
            "该条目为相似病例证据，用于对照症状组合、检查结果和处置路径。"
        )
        evidence_type = "case"
    else:
        title = f"本地证据：{heading or source_file}"
        source = f"本地知识库 | {source_file}"
        support = f"证据ID={evidence_id}，检索分数={float(score):.4f}。该片段与当前问题存在文本匹配。"
        evidence_type = "unknown"

    return {
        "title": title,
        "source": source,
        "snippet": snippet,
        "support_point": support,
        "evidence_type": evidence_type,
        "evidence_id": evidence_id,
        "score": round(float(score), 4),
    }


def _fallback_from_retrieval(top: List[Tuple[float, Dict[str, Any]]], symptom_terms: Optional[List[str]] = None) -> Dict[str, Any]:
    trace = {"guideline_level": [], "literature_level": [], "case_level": []}
    top_focus = _select_focus_by_level(top, per_level=1, max_total=4)
    key_points: List[str] = []
    for score, item in top_focus:
        rec = _format_evidence_record(score, item, symptom_terms or [])
        key_points.append(_extract_relevant_snippet(item["text"], symptom_terms or [], max_len=60))
        if item["level"] == "guideline":
            trace["guideline_level"].append(rec)
        elif item["level"] == "literature":
            trace["literature_level"].append(rec)
        else:
            trace["case_level"].append(rec)

    # 具体 report 由上层根据症状生成（避免不合理推理）
    return {"report": {}, "traceability": trace, "_key_points": key_points}


def _matched_route_keywords(symptom_terms: List[str]) -> List[str]:
    """
    找到命中的症状路由关键词，用于二次过滤证据，避免跨病种片段进入方案摘要。
    """
    s = " ".join(symptom_terms)
    routes = _load_symptom_routes()
    for route in routes:
        kws = route.get("keywords", [])
        if isinstance(kws, list) and any(str(k) in s for k in kws):
            return [str(k) for k in kws]
    return symptom_terms[:]


def _match_symptom_route(query: str, symptom_terms: List[str]) -> Optional[Dict[str, Any]]:
    """
    从完整问诊文本中匹配症状路由。

    早期版本只看 _extract_symptom_terms 的结果，导致用户换一种说法时容易
    回到通用兜底。这里直接对主诉/现病史/问题全文匹配，并按命中数择优。
    """
    text = f"{query} {' '.join(symptom_terms)}".lower()
    best: Optional[Dict[str, Any]] = None
    best_score = 0
    for route in _load_symptom_routes():
        keywords = route.get("keywords", [])
        if not isinstance(keywords, list):
            continue
        hits = 0
        for kw in keywords:
            k = str(kw).strip().lower()
            if k and k in text and not _is_negated(text, k):
                hits += 1
        if not hits:
            continue
        # 高风险场景必须优先于伴随症状。例如跌倒后嗜睡伴恶心，不能被“恶心”路由带到胃肠道。
        priority = int(route.get("priority", 0) or 0)
        score = priority * 100 + hits
        if score > best_score:
            best = route
            best_score = score
    return best


def _extract_clinical_gaps(query: str) -> List[str]:
    gaps = []
    checks = [
        ("体温/热峰", ["体温", "℃", "度", "热峰"]),
        ("症状持续时间", ["天", "小时", "周", "月", "年"]),
        ("严重程度或变化趋势", ["加重", "缓解", "反复", "持续", "阵发"]),
        ("伴随症状", ["伴", "同时", "没有", "无"]),
        ("既往病史/用药史", ["既往", "高血压", "糖尿病", "用药", "服药", "过敏"]),
    ]
    for label, terms in checks:
        if not any(t in query for t in terms):
            gaps.append(label)
    return gaps[:4]


def _build_reasonable_report_from_symptoms(
    symptom_terms: List[str],
    key_points: List[str],
    query: str = "",
) -> Dict[str, str]:
    """
    让本地兜底的 Level1/2 更“像临床推理”，避免出现明显不匹配的检查/处置。
    这里只做轻量规则，不伪造证据来源。
    """
    s = " ".join(symptom_terms)
    points = "；".join(p for p in key_points[:2] if p) or "当前证据提示存在相关临床线索。"
    gaps = _extract_clinical_gaps(query)
    gap_text = f"；建议补充：{'、'.join(gaps)}" if gaps else ""

    route = _match_symptom_route(query or s, symptom_terms)
    if route:
        primary = str(route.get("primary_diagnosis", "")).strip()
        diff = str(route.get("differential_diagnosis", "")).strip()
        risk = str(route.get("risk_alert", "")).strip()
        tests = str(route.get("recommended_tests", "")).strip()
        plan = str(route.get("treatment_plan", "")).strip()
        if primary and diff and risk and tests and plan:
            return {
                "primary_diagnosis": primary,
                "differential_diagnosis": diff,
                "risk_alert": f"{risk}{gap_text}",
                "recommended_tests": tests,
                "treatment_plan": f"{plan}；关键线索：{points}",
            }

    # 默认通用（JSON 未命中时）
    return {
        "primary_diagnosis": "初步判断：需结合更多病史与体征进一步明确诊断方向",
        "differential_diagnosis": "建议从感染/过敏/系统性疾病等方向做鉴别，优先排除高风险项",
        "risk_alert": f"若症状快速进展或出现危险信号，建议及时就医{gap_text}",
        "recommended_tests": "建议完善病史与查体，必要时做基础检查并结合专科评估",
        "treatment_plan": f"依据主要症状先对症处理并复评；关键线索：{points}",
    }


def _fallback_no_parse(files: List[Path]) -> Dict[str, Any]:
    hint = "；".join([f.name for f in files[:6]]) if files else "无"
    return {
        "report": {
            "primary_diagnosis": "已读取知识库文件并完成初步校验",
            "differential_diagnosis": "当前未提取到可用正文，请补充文本后重试",
            "risk_alert": "当前结果为提示信息，需人工复核",
            "recommended_tests": "建议将资料转为可解析 UTF-8 文本",
            "treatment_plan": f"已检测文件：{hint}",
        },
        "traceability": {"guideline_level": [], "literature_level": [], "case_level": []},
    }


def _fallback_no_evidence(symptom_terms: List[str]) -> Dict[str, Any]:
    symptom_text = "、".join(symptom_terms[:6]) if symptom_terms else "当前主诉"
    return {
        "report": {
            "primary_diagnosis": "未检索到与当前症状直接匹配的本地证据（以下为基于症状的推理建议）",
            "differential_diagnosis": "请补充症状细节或扩充知识库后再次分析",
            "risk_alert": "当前建议缺少本地证据支撑，需人工复核",
            "recommended_tests": "建议完善病史与查体，按症状选择必要检查",
            "treatment_plan": f"建议围绕“{symptom_text}”补充相关指南、文献与病例资料；当前证据链为空",
        },
        "traceability": {"guideline_level": [], "literature_level": [], "case_level": []},
    }


def _merge_with_fallback_if_sparse(
    model_obj: Dict[str, Any],
    fallback_obj: Dict[str, Any],
) -> Dict[str, Any]:
    """
    当模型虽返回 JSON 但 report 关键字段过空时，用本地检索摘要补全，
    避免页面“诊断推理基本无内容”。
    """
    out = dict(model_obj) if isinstance(model_obj, dict) else {}
    rep = out.get("report", {}) if isinstance(out.get("report", {}), dict) else {}
    fb_rep = fallback_obj.get("report", {}) if isinstance(fallback_obj.get("report", {}), dict) else {}
    keys = [
        "primary_diagnosis",
        "differential_diagnosis",
        "risk_alert",
        "recommended_tests",
        "treatment_plan",
    ]
    for k in keys:
        v = rep.get(k)
        if not isinstance(v, str) or len(v.strip()) < 6:
            rep[k] = fb_rep.get(k, "")
    out["report"] = rep

    # 若模型给出的 traceability 过多或为空，统一用精选证据，保持前端简洁稳定
    out["traceability"] = fallback_obj.get("traceability", out.get("traceability", {}))
    return out


def call_local_rag(
    *,
    form_data: Dict[str, Any],
    kb_dir: str,
    llm_base_url: str,
    llm_model: str,
    llm_api_key: str = "",
    normalize_terms: bool = True,
    few_shot_max: int = 2,
    top_k: int = 6,
    temperature: float = 0.2,
) -> Dict[str, Any]:
    fd, few_block = prepare_rag_form(
        form_data,
        normalize_terms=normalize_terms,
        few_shot_max=few_shot_max,
    )

    kb_path = Path(kb_dir).expanduser()
    if not kb_path.exists() or not kb_path.is_dir():
        raise ValueError(f"本地知识库目录不存在：{kb_dir}")

    files = [p for p in kb_path.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES]
    if not files:
        raise ValueError("本地知识库目录下没有可用文件（支持 txt/md/csv/json/pdf）。")

    index = _build_or_load_index(kb_path)
    if not index.get("chunks"):
        return _fallback_no_parse(files)

    query = " ".join(
        [
            str(fd.get("complaint", "")),
            str(fd.get("history", "")),
            str(fd.get("question", "")),
        ]
    )
    symptom_terms = _extract_symptom_terms(query)
    scored = _score_fused(query, index, top_k=top_k)
    scored = _filter_by_symptom_terms(
        scored,
        symptom_terms,
        min_score=0.08,
        query=query,
        gender=str(fd.get("gender", "")),
    )
    if not scored:
        # 即使无证据，也给出“按症状路由”的可读推理内容（证据链为空）
        obj = _fallback_no_evidence(symptom_terms)
        obj["report"] = _build_reasonable_report_from_symptoms(symptom_terms, [], query=query)
        obj["report"]["risk_alert"] = obj["report"].get("risk_alert", "") + "（当前无本地证据支撑）"
        return obj
    top = _rebalance_levels(scored, top_k=top_k)
    matched_route = _match_symptom_route(query, symptom_terms)
    if matched_route and isinstance(matched_route.get("keywords"), list):
        matched_keywords = [str(k) for k in matched_route.get("keywords", [])]
        route_terms = [k for k in matched_keywords if k and k in query and not _is_negated(query, k)]
        if not route_terms:
            route_terms = matched_keywords
    else:
        route_terms = _matched_route_keywords(symptom_terms)
    generic_route_terms = {"腹痛", "肚子疼", "肚子痛", "胃痛", "疼", "痛", "扭伤", "外伤"}
    strict_route_terms = [t for t in route_terms if t not in generic_route_terms]
    route_filter_terms = strict_route_terms or route_terms
    route_top = []
    for s, it in top:
        if any(t in it["text"] for t in route_filter_terms):
            route_top.append((s, it))
    if route_top:
        top = route_top
    fallback_focus = _fallback_from_retrieval(top, symptom_terms=route_terms)
    key_points = fallback_focus.get("_key_points", []) if isinstance(fallback_focus, dict) else []
    fallback_focus["report"] = _build_reasonable_report_from_symptoms(symptom_terms, key_points, query=query)

    evidence_block = _build_evidence_blocks(top)
    prompt = f"""
你是“小溯医生”，请基于患者信息与本地检索证据进行分析。
严格只输出 JSON，不要输出任何额外文字。
证据必须按 guideline_level / literature_level / case_level 分层，缺失时返回空数组。
严禁编造不存在的指南、文献或病例来源；若证据不足，必须在 report 中明确“证据不足”并保持对应证据数组为空。

患者信息：
- 姓名：{fd.get("name")}
- 性别：{fd.get("gender")}
- 年龄：{fd.get("age")}
- 主诉：{fd.get("complaint")}
- 现病史：{fd.get("history")}
- 过敏史：{fd.get("allergy")}
- 既往史：{fd.get("past_history")}
- 用户问题：{fd.get("question")}

少样本示范：
{few_block if few_block else "（无）"}

本地检索证据：
{evidence_block if evidence_block else "（未命中显著证据）"}

输出结构：
{{
  "report": {{
    "primary_diagnosis": "",
    "differential_diagnosis": "",
    "risk_alert": "",
    "recommended_tests": "",
    "treatment_plan": ""
  }},
  "traceability": {{
    "guideline_level": [{{"title":"","source":"","snippet":"","support_point":""}}],
    "literature_level": [{{"title":"","source":"","snippet":"","support_point":""}}],
    "case_level": [{{"title":"","source":"","snippet":"","support_point":""}}]
  }}
}}
""".strip()

    base = llm_base_url.rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    url = f"{base}/chat/completions"
    headers = {"Content-Type": "application/json"}
    if llm_api_key.strip():
        headers["Authorization"] = f"Bearer {llm_api_key.strip()}"

    payload = {
        "model": llm_model,
        "temperature": float(temperature),
        "messages": [
            {"role": "system", "content": "你是临床可溯源助手，必须输出合法 JSON。"},
            {"role": "user", "content": prompt},
        ],
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        obj = resp.json()
        text = (
            ((obj.get("choices") or [{}])[0].get("message") or {}).get("content")
            or ((obj.get("choices") or [{}])[0].get("text"))
            or ""
        )
        if isinstance(text, str) and text.strip():
            normalized = normalize_answer(text.strip())
            return _merge_with_fallback_if_sparse(normalized, fallback_focus)
    except Exception:
        pass

    return fallback_focus
