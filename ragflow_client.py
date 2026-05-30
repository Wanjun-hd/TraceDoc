import json
import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests

from fs_trace_rag import prepare_rag_form


def build_prompt(form_data: Dict[str, Any], *, few_shot_block: str = "") -> str:
    fs = f"\n\n{few_shot_block.strip()}\n\n" if few_shot_block and few_shot_block.strip() else "\n"
    return f"""
你是“小溯医生”，一个用于基层临床辅助的可溯源医疗助手。
请基于患者信息进行分析，并严格输出 JSON（不要输出任何额外文字）。
在 RAGFlow 已检索到的知识片段范围内组织证据；traceability 三条链须与 report 结论一一对应、不得虚构不存在的文献或指南文号。
{fs}
患者个人信息：
- 姓名：{form_data["name"]}
- 性别：{form_data["gender"]}
- 年龄：{form_data["age"]}
- 联系方式：{form_data["phone"]}

患者病情信息：
- 主诉：{form_data["complaint"]}
- 现病史：{form_data["history"]}
- 过敏史：{form_data["allergy"]}
- 既往史：{form_data["past_history"]}

用户提问：
{form_data["question"]}

输出 JSON 结构如下：
{{
  "report": {{
    "primary_diagnosis": "初步诊断",
    "differential_diagnosis": "鉴别诊断",
    "risk_alert": "风险提示",
    "recommended_tests": "建议检查",
    "treatment_plan": "诊疗建议"
  }},
  "traceability": {{
    "guideline_level": [
      {{
        "title": "证据标题",
        "source": "来源（指南/机构）",
        "snippet": "关键证据内容",
        "support_point": "如何支撑结论"
      }}
    ],
    "literature_level": [
      {{
        "title": "文献标题",
        "source": "期刊/数据库",
        "snippet": "摘要或关键片段",
        "support_point": "如何支撑结论"
      }}
    ],
    "case_level": [
      {{
        "title": "病历标签",
        "source": "脱敏病历来源",
        "snippet": "病例关键特征",
        "support_point": "如何支撑结论"
      }}
    ]
  }}
}}
""".strip()


def _with_inference(payload: Dict[str, Any], temperature: Optional[float]) -> Dict[str, Any]:
    if temperature is None:
        return payload
    merged = dict(payload)
    merged["temperature"] = float(temperature)
    return merged


def parse_ragflow_stream_response(response: requests.Response) -> str:
    answer_parts = []

    def _extract_content(chunk: Dict[str, Any]) -> str:
        data = chunk.get("data", {}) if isinstance(chunk.get("data", {}), dict) else {}
        candidates = [
            data.get("content"),
            data.get("answer"),
            data.get("response"),
            chunk.get("content"),
            chunk.get("answer"),
            chunk.get("response"),
        ]
        choices = chunk.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0] if isinstance(choices[0], dict) else {}
            delta = first.get("delta", {}) if isinstance(first.get("delta", {}), dict) else {}
            message = first.get("message", {}) if isinstance(first.get("message", {}), dict) else {}
            candidates.extend([delta.get("content"), message.get("content"), first.get("text")])

        for item in candidates:
            if isinstance(item, str) and item.strip():
                return item
        return ""

    for line in response.iter_lines():
        if not line:
            continue
        text = line.decode("utf-8", errors="ignore")
        payload = text[5:].strip() if text.startswith("data:") else text.strip()
        if not payload:
            continue
        if payload == "[DONE]":
            break
        try:
            chunk = json.loads(payload)
        except json.JSONDecodeError:
            continue

        if chunk.get("code") not in (None, 0):
            raise RuntimeError(chunk.get("message", "RAGFlow 返回错误"))

        content = _extract_content(chunk)
        if content:
            answer_parts.append(content)
        data = chunk.get("data", {}) if isinstance(chunk.get("data", {}), dict) else {}
        finish_reason = data.get("finish_reason")
        if finish_reason is None:
            choices = chunk.get("choices")
            if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                finish_reason = choices[0].get("finish_reason")
        if finish_reason is not None:
            break

    final_text = "".join(answer_parts).strip()
    return final_text.replace("```json", "").replace("```", "").strip()


def parse_ragflow_non_stream_response(response: requests.Response) -> str:
    try:
        obj = response.json()
    except Exception as exc:
        raise RuntimeError(f"非流式响应不是 JSON：{str(exc)}")

    if isinstance(obj, dict):
        if obj.get("code") not in (None, 0):
            raise RuntimeError(f"RAGFlow 错误：{obj.get('message', 'unknown error')}")
        data = obj.get("data", {}) if isinstance(obj.get("data", {}), dict) else {}
        direct = data.get("content") or data.get("answer") or data.get("response")
        if isinstance(direct, str) and direct.strip():
            return direct.strip().replace("```json", "").replace("```", "").strip()

        choices = obj.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            first = choices[0]
            message = first.get("message", {}) if isinstance(first.get("message", {}), dict) else {}
            text = message.get("content") or first.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip().replace("```json", "").replace("```", "").strip()

    raise RuntimeError("非流式响应中未找到可解析文本内容。")


def normalize_answer(raw_text: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    candidate = raw_text.strip()
    codeblock_match = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", candidate, flags=re.IGNORECASE)
    if codeblock_match:
        candidate = codeblock_match.group(1).strip()
    else:
        brace_match = re.search(r"(\{[\s\S]*\})", candidate)
        if brace_match:
            candidate = brace_match.group(1).strip()

    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    return {
        "report": {
            "primary_diagnosis": "模型未按 JSON 输出，以下为原始回答摘要",
            "differential_diagnosis": "请结合临床进一步判断",
            "risk_alert": "当前回答缺少结构化字段，需人工复核",
            "recommended_tests": "建议补充核心检查后再次提问",
            "treatment_plan": candidate[:1200] if candidate else "暂无可用文本",
        },
        "traceability": {
            "guideline_level": [],
            "literature_level": [],
            "case_level": [],
        },
    }


def call_ragflow(
    *,
    api_key: str,
    base_url: str,
    chat_id: str,
    form_data: Dict[str, Any],
    normalize_terms: bool = True,
    few_shot_max: int = 2,
    temperature: Optional[float] = None,
) -> Dict[str, Any]:
    # //AI辅助生成：豆包，2026-04-20
    if not api_key or not chat_id:
        raise ValueError("请先在左侧配置 RAGFlow API Key 与 Chat ID。")
    if not base_url or not urlparse(base_url).scheme:
        raise ValueError("RAGFlow Base URL 必须包含协议，例如 http://127.0.0.1:9380。")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    fd, few_block = prepare_rag_form(
        form_data,
        normalize_terms=normalize_terms,
        few_shot_max=few_shot_max,
    )
    prompt = build_prompt(fd, few_shot_block=few_block)
    endpoints = [
        {
            "name": "chats_question",
            "url": f"{base_url.rstrip('/')}/api/v1/chats/{chat_id}/completions",
            "stream_payload": _with_inference({"question": prompt, "stream": True}, temperature),
            "non_stream_payload": _with_inference({"question": prompt, "stream": False}, temperature),
        },
        {
            "name": "chats_query",
            "url": f"{base_url.rstrip('/')}/api/v1/chats/{chat_id}/completions",
            "stream_payload": _with_inference({"query": prompt, "stream": True}, temperature),
            "non_stream_payload": _with_inference({"query": prompt, "stream": False}, temperature),
        },
        {
            "name": "legacy_messages",
            "url": f"{base_url.rstrip('/')}/api/v1/chat/completions",
            "stream_payload": _with_inference(
                {
                    "chat_id": chat_id,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": True,
                },
                temperature,
            ),
            "non_stream_payload": _with_inference(
                {
                    "chat_id": chat_id,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
                temperature,
            ),
        },
    ]

    raw_text = ""
    errors = []
    for endpoint in endpoints:
        try:
            stream_resp = requests.post(
                endpoint["url"],
                headers=headers,
                json=endpoint["stream_payload"],
                stream=True,
                timeout=(8, 120),
            )
            if stream_resp.status_code != 200:
                errors.append(
                    f"{endpoint['name']} HTTP {stream_resp.status_code}: "
                    f"{stream_resp.text[:180].replace(chr(10), ' ')}"
                )
                continue

            raw_text = parse_ragflow_stream_response(stream_resp)
            if raw_text:
                break

            fallback_resp = requests.post(
                endpoint["url"],
                headers=headers,
                json=endpoint["non_stream_payload"],
                timeout=(8, 120),
            )
            if fallback_resp.status_code != 200:
                errors.append(
                    f"{endpoint['name']} 非流式 HTTP {fallback_resp.status_code}: "
                    f"{fallback_resp.text[:180].replace(chr(10), ' ')}"
                )
                continue

            raw_text = parse_ragflow_non_stream_response(fallback_resp)
            if raw_text:
                break
        except Exception as exc:
            errors.append(f"{endpoint['name']} 异常: {str(exc)}")

    if not raw_text:
        detail = " | ".join(errors[:5]) if errors else "未收到 RAGFlow 响应"
        raise RuntimeError(
            "RAGFlow 调用失败。请检查 Base URL、Chat ID、API Key、RAGFlow 服务状态和知识库是否完成解析。"
            f"详情：{detail}"
        )

    return normalize_answer(raw_text)
