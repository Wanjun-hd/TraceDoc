"""申请书「医疗术语归一化」对应的应用层轻量实现：不替代 RAGFlow 内部分词/向量，仅统一常见口语写法。"""

from __future__ import annotations

import re
from typing import Any, Dict

# 可随项目扩充：左侧为归一化后的规范写法，右侧为常见变体（含错别字、缩写）
_TERM_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("发热", "发烧"),
    ("咳嗽", "咳"),
    ("呼吸困难", "气短"),
    ("呼吸困难", "气促"),
    ("恶心", "想吐"),
    ("呕吐", "吐"),
    ("腹泻", "拉肚子"),
    ("腹痛", "肚子疼"),
    ("头痛", "头疼"),
    ("胸闷", "胸部闷"),
    ("乏力", "没力气"),
    ("食欲不振", "不想吃饭"),
    ("高血压", "血压高"),
    ("糖尿病", "血糖高"),
)


def normalize_medical_terms(text: str) -> str:
    if not text or not isinstance(text, str):
        return text
    s = text.strip()
    for canonical, variant in _TERM_REPLACEMENTS:
        if variant in s and canonical not in s:
            s = s.replace(variant, canonical)
    s = re.sub(r"\s+", " ", s)
    return s


def normalize_form_fields(form_data: Dict[str, Any]) -> Dict[str, Any]:
    """对主诉、病史、提问等文本字段做术语归一化，姓名/性别/年龄等不修改。"""
    keys = ("complaint", "history", "question", "allergy", "past_history")
    out = dict(form_data)
    for k in keys:
        v = out.get(k)
        if isinstance(v, str):
            out[k] = normalize_medical_terms(v)
    return out
