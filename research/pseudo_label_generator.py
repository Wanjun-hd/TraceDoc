"""
最小可交付科研版：伪标签生成脚本

输入:  data/unlabeled_queries.jsonl  (每行 {"query": "..."} )
输出:  data/pseudo_labeled_pairs.jsonl

用途:
- 为后续对比学习构造 (query, positive, negative) 训练对
- 先用本地检索打分挑选高置信正样本，再采样负样本
"""

import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from local_rag_client import (
    SUPPORTED_SUFFIXES,
    _build_or_load_index,
    _score_fused,
)

UNLABELED_PATH = ROOT / "data" / "unlabeled_queries.jsonl"
OUTPUT_PATH = ROOT / "data" / "pseudo_labeled_pairs.jsonl"


def load_unlabeled() -> List[str]:
    if not UNLABELED_PATH.is_file():
        return []
    rows = []
    with UNLABELED_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                q = str(obj.get("query", "")).strip()
                if q:
                    rows.append(q)
            except Exception:
                continue
    return rows


def generate() -> int:
    # //AI辅助生成：豆包，2026-04-25
    kb_dir = ROOT / "核心三库"
    if not kb_dir.is_dir():
        raise RuntimeError(f"知识库目录不存在: {kb_dir}")

    files = [p for p in kb_dir.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES]
    if not files:
        raise RuntimeError("知识库为空。")

    index = _build_or_load_index(kb_dir)
    chunks: List[Dict[str, Any]] = index.get("chunks", [])
    if not chunks:
        raise RuntimeError("索引为空。")

    queries = load_unlabeled()
    if not queries:
        raise RuntimeError(f"未发现未标注查询文件或内容为空: {UNLABELED_PATH}")

    out = []
    for q in queries:
        scored = _score_fused(q, index, top_k=8)
        if not scored:
            continue
        best_score, best_item = scored[0]
        # 高置信阈值（经验值，可按实验调整）
        if best_score < 0.18:
            continue
        # 从低分池中随机选负样本
        tail = scored[-3:] if len(scored) >= 3 else scored
        neg_item = random.choice(tail)[1]
        row = {
            "query": q,
            "positive_text": best_item["text"],
            "negative_text": neg_item["text"],
            "positive_source": best_item["source"],
            "negative_source": neg_item["source"],
            "confidence": round(float(best_score), 4),
        }
        out.append(row)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for row in out:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(out)


def main() -> None:
    count = generate()
    print(f"[OK] 生成伪标签对: {count} -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
