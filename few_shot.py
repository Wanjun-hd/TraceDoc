"""申请书「10–100 条少样本」在应用层的落点：通过 JSON 配置示例，在 Prompt 中做 ICL，约束 JSON 与三级证据结构。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_DEFAULT_PATH = Path(__file__).resolve().parent / "data" / "few_shot_examples.json"


def load_examples(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    p = path or _DEFAULT_PATH
    if not p.is_file():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    ex = raw.get("examples")
    return ex if isinstance(ex, list) else []


def build_few_shot_block(max_examples: int, path: Optional[Path] = None) -> str:
    if max_examples <= 0:
        return ""
    examples = load_examples(path)[:max_examples]
    if not examples:
        return ""
    lines = [
        "## 少样本示范（请模仿下列 JSON 的字段名与层级结构；证据内容须与当前真实患者信息相符，勿照抄示例文字）",
        "",
    ]
    for i, ex in enumerate(examples, start=1):
        summary = ex.get("input_summary", "")
        out_obj = ex.get("output_json")
        if not isinstance(out_obj, dict):
            continue
        lines.append(f"### 示例 {i}")
        lines.append(f"输入摘要：{summary}")
        lines.append("输出 JSON：")
        lines.append(json.dumps(out_obj, ensure_ascii=False, indent=2))
        lines.append("")
    if len(lines) <= 2:
        return ""
    return "\n".join(lines).strip()
