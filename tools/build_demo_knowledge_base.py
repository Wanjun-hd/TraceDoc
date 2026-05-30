"""
Build an expanded demo knowledge base from data/symptom_routes.json.

The generated files are intentionally marked as demo/de-identified material.
They make the project runnable and testable without claiming to be a real
clinical database.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[1]
ROUTES_PATH = ROOT / "data" / "symptom_routes.json"
KB_DIR = ROOT / "核心三库"
DATA_DIR = ROOT / "data"


def load_routes() -> List[Dict[str, Any]]:
    raw = json.loads(ROUTES_PATH.read_text(encoding="utf-8"))
    routes = raw.get("routes", [])
    return [r for r in routes if isinstance(r, dict) and isinstance(r.get("keywords"), list)]


def first_keywords(route: Dict[str, Any], n: int = 3) -> str:
    return "、".join(str(k) for k in route.get("keywords", [])[:n])


def write_text(path: Path, blocks: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n\n".join(blocks).strip() + "\n", encoding="utf-8")


def build_guidelines(routes: List[Dict[str, Any]]) -> None:
    blocks = [
        "# 扩展临床指南库（脱敏演示版）",
        "说明：本文件由项目脚本根据症状路由生成，用于本地 RAG 演示、检索测试和答辩展示；不可替代真实指南原文。",
    ]
    for idx, route in enumerate(routes, start=1):
        kws = first_keywords(route)
        blocks.append(
            f"""# G{idx:03d} {kws} 处理路径
## 适用主诉
{kws} 等相关表达。
## 初步方向
{route.get("primary_diagnosis", "需结合病史进一步判断")}
## 鉴别诊断
{route.get("differential_diagnosis", "需结合专科评估")}
## 建议检查
{route.get("recommended_tests", "完善病史、查体和基础检查")}
## 危险信号
{route.get("risk_alert", "症状加重或出现急危重信号时及时就医")}
## 基层处理原则
{route.get("treatment_plan", "先分层评估，再进行对症处理和复评")}。记录起病时间、诱因、变化趋势和既往病史，必要时转诊。"""
        )
        blocks.append(
            f"""# G{idx:03d}-A {kws} 初诊问诊清单
1. 起病时间：记录从首次出现 {kws} 到就诊的间隔。
2. 严重程度：询问是否影响进食、睡眠、活动或排尿排便。
3. 伴随症状：围绕发热、疼痛、出血、呼吸困难、意识改变等危险信号追问。
4. 基础情况：补充年龄、妊娠可能、慢病史、用药史和过敏史。
5. 分层结论：符合危险信号者优先转诊；轻症可先对症处理并短期复评。"""
        )
        blocks.append(
            f"""# G{idx:03d}-B {kws} 检查选择原则
首轮检查不追求一次性覆盖全部项目，应根据主诉和风险分层选择。
推荐组合：{route.get("recommended_tests", "基础检查")}。
若检查结果与症状不一致，应复核病史、查体和标本质量，必要时升级影像或专科评估。"""
        )
        blocks.append(
            f"""# G{idx:03d}-C {kws} 随访与转诊建议
短期随访重点观察症状是否加重、是否出现新危险信号、治疗后是否改善。
转诊触发：{route.get("risk_alert", "出现急危重信号")}。
随访记录应包含主诉变化、体征变化、检查结果和处理调整。"""
        )
    write_text(KB_DIR / "扩展临床指南库.txt", blocks)


def build_literature(routes: List[Dict[str, Any]]) -> None:
    blocks = [
        "# 扩展医学文献摘要库（演示版）",
        "说明：以下为用于系统检索演示的结构化文献摘要，采用论文摘要格式组织；不声明来自真实论文，正式版本应替换为真实文献题录。",
    ]
    for idx, route in enumerate(routes, start=1):
        kws = first_keywords(route)
        year = 2020 + (idx % 5)
        authors = f"TraceDoc Research Group; Community Care Evidence Lab; Li et al."
        blocks.append(
            f"""# L{idx:03d} {kws} 风险分层与初诊策略研究
题名：{kws} 在基层首诊场景中的风险分层与检查路径研究
作者：{authors}
年份：{year}
来源：Chinese Journal of Primary Care Informatics（模拟期刊），{year}，{8 + idx % 6}(2): {20 + idx}-{28 + idx}
研究类型：回顾性病例摘要 + 指南一致性分析（演示数据）
研究问题：基层问诊中，如何根据 {kws} 进行初步分层。
摘要：主诉关键词、持续时间、严重程度和伴随症状共同决定初步风险层级；{route.get("recommended_tests", "基础检查")} 可作为首轮评估依据；出现 {route.get("risk_alert", "危险信号")} 时，应提高处置等级或转诊。
结论：{route.get("primary_diagnosis", "需要进一步评估")}，但仍需医生结合查体和检查结果确认。"""
        )
        blocks.append(
            f"""# L{idx:03d}-R {kws} 检索增强问答可解释性研究
题名：面向 {kws} 问诊的证据感知 RAG 输出一致性评估
作者：TraceDoc RAG Evaluation Team; Wang et al.
年份：{year}
来源：Journal of Medical AI Evaluation（模拟期刊），{year}，{5 + idx % 4}(1): {11 + idx}-{16 + idx}
研究类型：系统评估 / RAG 消融实验（演示数据）
研究问题：RAG 系统如何避免在 {kws} 场景下编造证据。
摘要：回答必须绑定证据来源、证据片段和支撑点；缺少本地证据时，应明确提示证据不足，不输出伪造文献编号；三层证据可按指南、文献、病例分别展示，便于人工复核。
结论：证据感知输出能提高临床辅助系统的可解释性和可审核性。"""
        )
        blocks.append(
            f"""# L{idx:03d}-F {kws} 少样本场景泛化研究
题名：低资源中文医疗问答中 {kws} 相关问法的少样本泛化方法
作者：TraceDoc Few-shot Study Group; Zhang et al.
年份：{year}
来源：Proceedings of Clinical NLP Applications（模拟会议），{year}: {101 + idx}-{108 + idx}
研究类型：少样本学习 / 伪标签扩充实验（演示数据）
研究问题：低资源标注下如何覆盖 {kws} 的多种自然语言问法。
摘要：同义词扩展和伪标签查询可提高召回；对比学习可缩短相似症状表达的向量距离；负样本应覆盖相近但不同系统的主诉，降低误检索。
结论：少样本示范、伪标签和检索融合适合本项目的轻量化方案。"""
        )
    write_text(KB_DIR / "扩展医学文献摘要库.txt", blocks)


def build_cases(routes: List[Dict[str, Any]]) -> None:
    blocks = [
        "# 扩展脱敏病例库（演示版）",
        "说明：以下为合成脱敏病例，用于本地 RAG 检索、证据链展示和功能测试。",
    ]
    ages = [23, 31, 42, 56, 68]
    genders = ["男", "女"]
    for idx, route in enumerate(routes, start=1):
        kws = [str(k) for k in route.get("keywords", [])[:3]]
        complaint = "、".join(kws)
        for variant in range(1, 4):
            age = ages[(idx + variant) % len(ages)]
            gender = genders[(idx + variant) % len(genders)]
            course = idx % 5 + variant
            blocks.append(
                f"""# C{idx:03d}-{variant} {complaint} 相似病例
基本信息：{age}岁，{gender}，脱敏演示病例。
主诉：{complaint}，持续约{course}天。
现病史：症状逐渐出现，患者希望明确可能原因及下一步处理；未记录真实身份信息。
初步判断：{route.get("primary_diagnosis", "需进一步评估")}
鉴别方向：{route.get("differential_diagnosis", "结合临床进一步鉴别")}
建议检查：{route.get("recommended_tests", "完善基础检查")}
风险提示：{route.get("risk_alert", "症状加重需及时就医")}
处置经过：{route.get("treatment_plan", "对症处理并复评")}，后续按检查结果调整方案。"""
            )
    write_text(KB_DIR / "扩展脱敏病例库.txt", blocks)


def build_dataset(routes: List[Dict[str, Any]]) -> None:
    rows = []
    templates = [
        "{kw}怎么办，需要做什么检查",
        "{kw}{days}天可能是什么原因",
        "出现{kw}要不要去医院",
        "{kw}伴随不舒服下一步怎么处理",
        "基层门诊遇到{kw}如何分诊",
    ]
    for idx, route in enumerate(routes, start=1):
        kws = [str(k) for k in route.get("keywords", []) if str(k).strip()]
        for j, kw in enumerate(kws[:6], start=1):
            for t_idx, tmpl in enumerate(templates, start=1):
                rows.append(
                    {
                        "id": f"route-{idx:03d}-{j:02d}-{t_idx:02d}",
                        "query": tmpl.format(kw=kw, days=(j + t_idx) % 7 + 1),
                        "complaint": f"{kw}{(j + t_idx) % 7 + 1}天",
                        "history": f"围绕{kw}出现相关不适，病程短，需结合体征判断严重程度。",
                        "label": route.get("primary_diagnosis", ""),
                        "differential_diagnosis": route.get("differential_diagnosis", ""),
                        "recommended_tests": route.get("recommended_tests", ""),
                        "risk_alert": route.get("risk_alert", ""),
                        "source_type": "synthetic_deidentified_demo",
                    }
                )
    out = DATA_DIR / "dataset_samples.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    unlabeled = DATA_DIR / "unlabeled_queries.jsonl"
    with unlabeled.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps({"query": row["query"]}, ensure_ascii=False) + "\n")


def main() -> None:
    routes = load_routes()
    build_guidelines(routes)
    build_literature(routes)
    build_cases(routes)
    build_dataset(routes)
    print(f"[OK] routes={len(routes)}")
    print(f"[OK] wrote {KB_DIR / '扩展临床指南库.txt'}")
    print(f"[OK] wrote {KB_DIR / '扩展医学文献摘要库.txt'}")
    print(f"[OK] wrote {KB_DIR / '扩展脱敏病例库.txt'}")
    print(f"[OK] wrote {DATA_DIR / 'dataset_samples.jsonl'}")
    print(f"[OK] wrote {DATA_DIR / 'unlabeled_queries.jsonl'}")


if __name__ == "__main__":
    main()
