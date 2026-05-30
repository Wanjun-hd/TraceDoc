"""
FS-TraceRAG 应用层流水线（与申请书「检索—生成—溯源」对齐的工程落点）。

- 检索与向量库：由 RAGFlow 服务在 Docker 内完成；
- 本仓库负责：术语归一化、少样本 ICL、结构化 JSON 提示与结果解析展示。

后续若开展对比学习 / 伪标签扩充训练，可在独立脚本中使用 PyTorch + 自建向量索引，
与当前 RAGFlow 编排并行，而不必改写本模块的调用接口。
"""

from __future__ import annotations

from typing import Any, Dict

from few_shot import build_few_shot_block
from medical_preprocess import normalize_form_fields


def prepare_rag_form(
    form_data: Dict[str, Any],
    *,
    normalize_terms: bool = True,
    few_shot_max: int = 2,
) -> tuple[Dict[str, Any], str]:
    """
    返回 (送入模型的 form_data, few_shot 文本块)。
    """
    fd: Dict[str, Any] = normalize_form_fields(form_data) if normalize_terms else dict(form_data)
    block = build_few_shot_block(few_shot_max)
    return fd, block
