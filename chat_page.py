import html
from pathlib import Path
from typing import Any

import streamlit as st

from audit_logger import write_audit
from local_rag_client import call_local_rag
from ragflow_client import call_ragflow


DEMO_RESULT = {
    "report": {
        "primary_diagnosis": "社区获得性肺炎（初步考虑）",
        "differential_diagnosis": "流感相关下呼吸道感染、急性支气管炎、支原体肺炎",
        "risk_alert": "若持续高热>3天、呼吸频率增快或血氧下降，需警惕重症化风险并及时转诊。",
        "recommended_tests": "血常规、CRP/PCT、胸部影像（X线或CT）、病原学检测（流感/支原体）。",
        "treatment_plan": "建议先行对症治疗（退热、补液），结合检验结果评估是否启动经验性抗感染方案，并48小时复评。"
    },
    "traceability": {
        "guideline_level": [
            {
                "title": "《社区获得性肺炎诊疗规范》",
                "source": "国家卫健委临床规范",
                "snippet": "发热、咳嗽、影像学提示肺部浸润是CAP初筛关键线索。",
                "support_point": "与患者主诉的发热+咳嗽高度匹配，支持初步诊断方向。"
            }
        ],
        "literature_level": [
            {
                "title": "CAP早期分层管理研究",
                "source": "PubMed 临床研究",
                "snippet": "炎症指标与影像联合判读可提高早期风险分层准确率。",
                "support_point": "支持“检验+影像”作为下一步检查建议。"
            }
        ],
        "case_level": [
            {
                "title": "基层门诊相似病例（脱敏）",
                "source": "院内脱敏病历库",
                "snippet": "患者以发热、咳嗽起病，经规范抗感染和随访后改善。",
                "support_point": "提示当前处置路径在基层场景中具备可执行性。"
            }
        ]
    }
}


DEFAULT_LOCAL_KB_DIR = str(Path(__file__).resolve().parent / "核心三库")


def call_local_rag_from_session(form_data: dict, temperature: float = 0.2) -> dict:
    return call_local_rag(
        form_data=form_data,
        kb_dir=st.session_state.get("local_kb_dir") or DEFAULT_LOCAL_KB_DIR,
        llm_base_url=st.session_state.get("local_llm_base_url", "http://localhost:11434/v1"),
        llm_model=st.session_state.get("local_llm_model", "qwen2.5:7b"),
        llm_api_key=st.session_state.get("local_llm_api_key", ""),
        normalize_terms=bool(st.session_state.get("fs_normalize", True)),
        few_shot_max=int(st.session_state.get("fs_few_shot_k", 2)),
        top_k=int(st.session_state.get("local_top_k", 6)),
        temperature=float(temperature),
    )


def render_evidence_items(items: Any) -> None:
    if not isinstance(items, list) or len(items) == 0:
        st.info("暂无该层级证据。")
        return
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        title = item.get("title", f"证据 {idx}")
        with st.expander(f"{idx}. {title}", expanded=(idx == 1)):
            st.markdown(f"**来源：** {item.get('source', '未知来源')}")
            st.markdown(f"**证据片段：** {item.get('snippet', '无')}")
            st.markdown(f"**支撑点：** {item.get('support_point', '无')}")


def compact_evidence_text(value: Any, limit: int = 118) -> str:
    text = " ".join(str(value or "无").split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip("，。；、 ") + "..."


def evidence_type_label(item: dict) -> str:
    evidence_type = str(item.get("evidence_type", "")).lower()
    source = str(item.get("source", ""))
    title = str(item.get("title", ""))
    if "guideline" in evidence_type or "指南" in source or "指南" in title:
        return "指南证据"
    if "literature" in evidence_type or "文献" in source or "文献" in title or "PubMed" in source:
        return "文献摘要"
    if "case" in evidence_type or "病例" in source or "病例" in title:
        return "相似病例"
    return "检索证据"


def extract_evidence_tags(item: dict) -> list[str]:
    text = " ".join(
        str(item.get(key, "")) for key in ("title", "snippet", "support_point", "source")
    )
    candidates = [
        "发热",
        "咳嗽",
        "胸闷",
        "气短",
        "腹痛",
        "腹泻",
        "皮疹",
        "瘙痒",
        "红肿",
        "荨麻疹",
        "初诊分层",
        "基层问诊",
        "风险分层",
        "检查建议",
    ]
    tags = [word for word in candidates if word in text]
    return tags[:4] or ["临床证据"]


def build_evidence_items_html(items: Any, empty_text: str) -> str:
    """生成证据 HTML。禁止行首缩进，否则 Streamlit 的 Markdown 会把整段当成代码块原样显示。"""
    if not isinstance(items, list) or len(items) == 0:
        return f'<div class="evidence-empty">{html.escape(empty_text)}</div>'
    blocks = []
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            continue
        title_raw = str(item.get("title", f"证据 {idx}"))
        source_raw = str(item.get("source", "未知来源"))
        snippet_raw = str(item.get("snippet", "无"))
        support_raw = str(item.get("support_point", "无"))
        evidence_id = str(item.get("evidence_id") or f"E{idx:03d}")
        label = evidence_type_label(item)
        tags = extract_evidence_tags(item)
        title = html.escape(title_raw)
        source = html.escape(source_raw)
        snippet = html.escape(compact_evidence_text(snippet_raw))
        support = html.escape(support_raw)
        full_snippet = html.escape(snippet_raw)
        evidence_id_html = html.escape(evidence_id)
        label_html = html.escape(label)
        tag_html = "".join(f'<span class="evidence-tag">{html.escape(tag)}</span>' for tag in tags)
        blocks.append(
            f'<div class="evidence-item">'
            f'<div class="evidence-card-top">'
            f'<span class="evidence-id">{evidence_id_html}</span>'
            f'<span class="evidence-type">{label_html}</span>'
            f"</div>"
            f'<div class="evidence-title">{title}</div>'
            f'<div class="evidence-tags">{tag_html}</div>'
            f'<div class="evidence-summary">{snippet}</div>'
            f'<div class="evidence-meta"><span>来源：{source}</span><span>可信度：中</span></div>'
            f'<details class="evidence-detail"><summary>展开详情</summary>'
            f'<div class="evidence-line"><b>证据原文</b>：{full_snippet}</div>'
            f'<div class="evidence-line"><b>支撑点</b>：{support}</div>'
            f"</details>"
            f"</div>"
        )
    return "".join(blocks) if blocks else f'<div class="evidence-empty">{html.escape(empty_text)}</div>'


def build_trace_graph_html(report: dict, trace: dict, form_data: dict) -> str:
    # //AI辅助生成：豆包，2026-04-20
    complaint = form_data.get("complaint", "主诉信息")
    history = form_data.get("history", "现病史信息")
    diagnosis = report.get("primary_diagnosis", "初步诊断")
    differential = report.get("differential_diagnosis", "鉴别诊断")
    treatment = report.get("treatment_plan", "诊疗建议")

    guide_count = len(trace.get("guideline_level", [])) if isinstance(trace.get("guideline_level", []), list) else 0
    lit_count = len(trace.get("literature_level", [])) if isinstance(trace.get("literature_level", []), list) else 0
    case_count = len(trace.get("case_level", [])) if isinstance(trace.get("case_level", []), list) else 0

    c42, h42 = html.escape(complaint[:42]), html.escape(history[:42])
    d42, diff42, t42 = html.escape(diagnosis[:42]), html.escape(differential[:42]), html.escape(treatment[:42])
    return (
        f'<div class="kg-wrap">'
        f'<div class="kg-row">'
        f'<div class="kg-node kg-input">主诉节点<br/><span>{c42}</span></div>'
        f'<div class="kg-arrow">→</div>'
        f'<div class="kg-node kg-mid">症状归因<br/><span>{h42}</span></div>'
        f"</div>"
        f'<div class="kg-row">'
        f'<div class="kg-node kg-core">诊断结论<br/><span>{d42}</span></div>'
        f"</div>"
        f'<div class="kg-row">'
        f'<div class="kg-node kg-mid">鉴别诊断<br/><span>{diff42}</span></div>'
        f'<div class="kg-arrow">→</div>'
        f'<div class="kg-node kg-mid">诊疗建议<br/><span>{t42}</span></div>'
        f"</div>"
        f'<div class="kg-row">'
        f'<div class="kg-node kg-evidence">指南证据 ({guide_count})</div>'
        f'<div class="kg-node kg-evidence">文献证据 ({lit_count})</div>'
        f'<div class="kg-node kg-evidence">病历证据 ({case_count})</div>'
        f"</div>"
        f"</div>"
    )


def render_level3_html(trace: dict, title: str) -> None:
    guide_html = build_evidence_items_html(trace.get("guideline_level", []), "暂无指南级证据。")
    lit_html = build_evidence_items_html(trace.get("literature_level", []), "暂无文献级证据。")
    case_html = build_evidence_items_html(trace.get("case_level", []), "暂无病历级证据。")
    title_esc = html.escape(title)
    st.markdown(
        f'<div class="level1-wrap">'
        f'<div class="level1-title">{title_esc}</div>'
        f'<div class="evidence-grid">'
        f'<div class="evidence-col"><div class="evidence-col-title">指南级</div>{guide_html}</div>'
        f'<div class="evidence-col"><div class="evidence-col-title">文献级</div>{lit_html}</div>'
        f'<div class="evidence-col"><div class="evidence-col-title">病历级</div>{case_html}</div>'
        f"</div></div>",
        unsafe_allow_html=True,
    )


def render_chat_page() -> None:
    if "trace_focus" not in st.session_state:
        st.session_state.trace_focus = ""
    if "result" not in st.session_state:
        st.session_state.result = None

    st.markdown(
        """
        <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        [data-testid="stToolbar"] {display: none;}
        .stApp {
            background:
              radial-gradient(circle at 8% 16%, rgba(90, 150, 230, 0.16), transparent 34%),
              radial-gradient(circle at 85% 18%, rgba(26, 90, 199, 0.10), transparent 36%),
              linear-gradient(120deg, #edf3ff 0%, #f8fbff 52%, #eef6ff 100%);
        }
        .stApp::before {
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            opacity: 0.045;
            background:
              linear-gradient(115deg, rgba(26, 90, 199, 0.30) 1px, transparent 1px) 0 0 / 36px 36px,
              linear-gradient(-115deg, rgba(26, 90, 199, 0.18) 1px, transparent 1px) 0 0 / 36px 36px;
        }
        .input-card, .result-card, .level-card {
            border: 1px solid rgba(255,255,255,0.92);
            background: rgba(255,255,255,0.52);
            border-radius: 20px;
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            box-shadow:
              inset 0 1px 0 rgba(255,255,255,0.72),
              0 14px 30px rgba(20, 64, 132, 0.12);
        }
        .input-card {
            padding: 16px 16px 8px 16px;
        }
        .result-card {
            padding: 10px 14px;
            min-height: 0;
            margin-bottom: 8px;
        }
        .section-title {
            color: #1A3E8E;
            font-size: 18px;
            font-weight: 700;
            margin: 6px 0 8px 0;
        }
        .empty-state {
            border: 1px dashed rgba(89, 126, 182, 0.42);
            border-radius: 14px;
            padding: 18px;
            text-align: center;
            color: #667690;
            background: rgba(246, 250, 255, 0.45);
            margin-top: 8px;
        }
        .level-card {
            padding: 14px;
            margin-bottom: 10px;
        }
        .level-title {
            color: #1A3E8E;
            font-weight: 700;
            margin-bottom: 8px;
        }
        .logic-arrow {
            color: #4f79b8;
            font-weight: 700;
            text-align: center;
            margin: 4px 0;
        }
        .focus-hint {
            margin: 4px 0 10px 0;
            padding: 6px 10px;
            border-radius: 10px;
            background: rgba(35, 111, 214, 0.10);
            border: 1px solid rgba(35, 111, 214, 0.26);
            color: #2458a0;
            font-size: 13px;
            font-weight: 600;
        }
        .connector-wrap {
            height: 100%;
            display: flex;
            justify-content: center;
            align-items: center;
            padding-top: 110px;
        }
        .connector-line {
            width: 2px;
            height: 72%;
            border-radius: 999px;
            background: linear-gradient(180deg, rgba(64,126,219,0.18), rgba(64,126,219,0.62), rgba(64,126,219,0.18));
            position: relative;
            overflow: hidden;
        }
        .connector-line::after {
            content: "";
            position: absolute;
            left: -3px;
            top: -20%;
            width: 8px;
            height: 42px;
            border-radius: 999px;
            background: rgba(126, 187, 255, 0.95);
            box-shadow: 0 0 14px rgba(126, 187, 255, 0.75);
            animation: flowDown 2.6s linear infinite;
        }
        @keyframes flowDown {
            0% { top: -20%; }
            100% { top: 105%; }
        }
        .stTextInput > div > div > input,
        .stTextArea textarea,
        .stNumberInput input,
        .stSelectbox [data-baseweb="select"] > div {
            background: #f5f7fa !important;
            border: 1px solid rgba(104, 126, 162, 0.22) !important;
            border-radius: 10px !important;
        }
        .stTextInput > div > div > input:focus,
        .stTextArea textarea:focus,
        .stNumberInput input:focus {
            border: 1px solid #1A5AC7 !important;
            box-shadow: 0 0 0 2px rgba(26, 90, 199, 0.14) !important;
        }
        .stButton > button[kind="primary"] {
            border-radius: 999px;
            border: none;
            color: #fff;
            background: linear-gradient(90deg, #1A4FB0 0%, #2E77E8 100%);
            box-shadow: 0 10px 24px rgba(26, 90, 199, 0.34);
        }
        .header-inline {
            margin-top: 2px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .header-inline-title {
            color: #1e2f49;
            font-size: 40px;
            font-weight: 800;
            line-height: 1.2;
        }
        .header-inline-sub {
            color: #6f7f98;
            font-size: 13px;
            margin-top: 4px;
        }
        .output-title {
            color: #1A3E8E;
            font-size: 28px;
            font-weight: 800;
            margin: 0 0 18px 0;
        }
        .diag-pill {
            margin: 0 0 10px 0;
            padding: 10px 12px;
            border-radius: 10px;
            border: 1px solid rgba(126, 201, 170, 0.45);
            background: rgba(203, 241, 224, 0.62);
            color: #1f6c4e;
            font-weight: 700;
            line-height: 1.45;
        }
        .level1-wrap {
            border: 1px solid rgba(255,255,255,0.92);
            background: rgba(255,255,255,0.52);
            border-radius: 20px;
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            box-shadow:
              inset 0 1px 0 rgba(255,255,255,0.72),
              0 14px 30px rgba(20, 64, 132, 0.12);
            padding: 14px;
            margin-bottom: 10px;
        }
        .level1-title {
            color: #1A3E8E;
            font-weight: 700;
            margin: 0 0 8px 0;
        }
        .level1-line {
            margin: 4px 0;
            color: #1f2d3f;
            font-size: 15px;
            line-height: 1.6;
        }
        .workbench-offset {
            height: 14px;
        }
        .kg-wrap {
            border: 1px solid rgba(98, 137, 194, 0.24);
            border-radius: 14px;
            background: rgba(244, 249, 255, 0.56);
            padding: 12px;
        }
        .kg-row {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 10px;
            margin: 8px 0;
            flex-wrap: wrap;
        }
        .kg-node {
            min-width: 170px;
            max-width: 240px;
            border-radius: 12px;
            padding: 10px 12px;
            text-align: center;
            font-size: 13px;
            font-weight: 700;
            border: 1px solid rgba(77, 124, 189, 0.28);
            color: #1e467f;
            background: #ffffff;
            box-shadow: 0 4px 12px rgba(36, 84, 154, 0.10);
        }
        .kg-node span {
            font-weight: 500;
            color: #4f6281;
        }
        .kg-core {
            background: linear-gradient(180deg, #eef5ff 0%, #dfefff 100%);
            border-color: rgba(40, 104, 190, 0.42);
            color: #1a3e8e;
        }
        .kg-evidence {
            min-width: 150px;
            background: rgba(238, 248, 255, 0.95);
        }
        .kg-arrow {
            color: #4a78b9;
            font-size: 20px;
            font-weight: 700;
        }
        .level2-flow {
            border: 1px solid rgba(111, 151, 206, 0.28);
            border-radius: 12px;
            background: rgba(246, 250, 255, 0.68);
            padding: 10px 12px;
            margin-bottom: 8px;
        }
        .level2-node-title {
            color: #1f4b88;
            font-weight: 700;
            margin-bottom: 4px;
        }
        .level2-node-body {
            color: #2c3c51;
            font-size: 14px;
            line-height: 1.6;
        }
        .evidence-item {
            border: 1px solid rgba(156, 176, 205, 0.22);
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.9);
            padding: 12px 12px 10px;
            margin-bottom: 10px;
            box-shadow: 0 8px 20px rgba(38, 76, 124, 0.05);
        }
        .evidence-empty {
            color: #6f819b;
            font-size: 13px;
            border: 1px dashed rgba(122, 160, 212, 0.32);
            border-radius: 10px;
            padding: 10px;
            background: rgba(248, 252, 255, 0.6);
        }
        .evidence-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 10px;
            align-items: start;
        }
        .evidence-col {
            border: 1px solid rgba(156, 176, 205, 0.18);
            border-radius: 12px;
            padding: 10px;
            background: rgba(248, 251, 255, 0.52);
            min-height: 120px;
        }
        .evidence-col-title {
            color: #1f4b88;
            font-weight: 700;
            margin-bottom: 8px;
            font-size: 14px;
        }
        .evidence-card-top {
            display: flex;
            align-items: center;
            gap: 6px;
            margin-bottom: 8px;
        }
        .evidence-id {
            color: #1f4b88;
            background: rgba(31, 75, 136, 0.08);
            border: 1px solid rgba(31, 75, 136, 0.12);
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            line-height: 1;
            padding: 5px 8px;
        }
        .evidence-type {
            color: #607086;
            font-size: 12px;
            font-weight: 600;
        }
        .evidence-title {
            color: #16283d;
            font-weight: 700;
            font-size: 14px;
            line-height: 1.45;
            margin-bottom: 8px;
        }
        .evidence-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
            margin-bottom: 8px;
        }
        .evidence-tag {
            color: #24605a;
            background: rgba(57, 169, 145, 0.1);
            border: 1px solid rgba(57, 169, 145, 0.16);
            border-radius: 999px;
            font-size: 12px;
            line-height: 1;
            padding: 5px 7px;
        }
        .evidence-summary {
            color: #2f4055;
            font-size: 13px;
            line-height: 1.65;
            margin-bottom: 8px;
        }
        .evidence-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 8px 12px;
            color: #77869a;
            border-top: 1px solid rgba(156, 176, 205, 0.16);
            padding-top: 8px;
            font-size: 12px;
            line-height: 1.45;
        }
        .evidence-detail {
            color: #52657d;
            font-size: 13px;
            margin-top: 8px;
        }
        .evidence-detail summary {
            color: #1f4b88;
            cursor: pointer;
            font-weight: 700;
            list-style-position: outside;
            margin-left: 14px;
        }
        .evidence-line {
            color: #3b4e64;
            font-size: 13px;
            line-height: 1.6;
            margin: 6px 0 0;
        }
        .graph-hint {
            color: #5f7392;
            font-size: 13px;
            margin-top: 4px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    top_l, top_r = st.columns([1, 5])
    with top_l:
        if st.button("返回主页", use_container_width=True):
            st.session_state.current_page = "home"
            st.rerun()
    with top_r:
        st.markdown(
            """
            <div class="header-inline">
              <div>
                <div class="header-inline-title">小溯医生 · 临床溯源工作台</div>
                <div class="header-inline-sub">左侧录入，右侧即时查看溯源结果。推荐展示：Level1 结论 / Level2 推理链 / Level3 证据原文。</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown('<div class="workbench-offset"></div>', unsafe_allow_html=True)
    left_col, mid_col, right_col = st.columns([1.02, 0.08, 1.9], gap="large")
    with left_col:
        with st.form("patient_form"):
            st.markdown('<div class="section-title">基本信息</div>', unsafe_allow_html=True)
            if st.session_state.trace_focus == "basic":
                st.markdown('<div class="focus-hint">当前推理节点关联：基本信息</div>', unsafe_allow_html=True)
            name = st.text_input("姓名*", placeholder="请输入姓名")
            gender = st.selectbox("性别*", options=["男", "女", "其他"])
            age = st.number_input("年龄*", min_value=0, max_value=120, value=30)
            phone = st.text_input("联系方式", placeholder="可选")

            st.markdown('<div class="section-title">主诉症状</div>', unsafe_allow_html=True)
            if st.session_state.trace_focus == "symptom":
                st.markdown('<div class="focus-hint">当前推理节点关联：主诉与现病史</div>', unsafe_allow_html=True)
            complaint = st.text_area("主诉*", placeholder="例如：发热三天，伴咳嗽", height=90)
            history = st.text_area("现病史*", placeholder="起病时间、变化、伴随症状、诱因等", height=120)

            st.markdown('<div class="section-title">既往史</div>', unsafe_allow_html=True)
            if st.session_state.trace_focus == "history":
                st.markdown('<div class="focus-hint">当前推理节点关联：既往史与过敏史</div>', unsafe_allow_html=True)
            allergy = st.text_input("过敏史", placeholder="如：青霉素过敏")
            past_history = st.text_area("既往史", placeholder="高血压/糖尿病/手术史等", height=90)
            question = st.text_area("诊疗核心问题*", placeholder="例如：可能是什么病？下一步如何处理？", height=90)

            submitted = st.form_submit_button("开始分析", type="primary", use_container_width=True)

    with mid_col:
        st.markdown(
            """
            <div class="connector-wrap">
              <div class="connector-line"></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if submitted:
        if not name.strip() or not complaint.strip() or not history.strip() or not question.strip():
            st.warning("请完整填写带 * 的必填信息。")
        else:
            form_data = {
                "name": name.strip(),
                "gender": gender,
                "age": int(age),
                "phone": phone.strip() or "未填写",
                "allergy": allergy.strip() or "无",
                "past_history": past_history.strip() or "无",
                "complaint": complaint.strip(),
                "history": history.strip(),
                "question": question.strip(),
            }
            with st.spinner("正在生成可溯源报告..."):
                try:
                    temp_override = None
                    if st.session_state.get("fs_temp_mode") == "在侧栏覆盖":
                        temp_override = float(st.session_state.get("fs_temperature_val", 0.2))
                    if st.session_state.get("backend_mode", "RAGFlow") == "RAGFlow":
                        try:
                            st.session_state.result = call_ragflow(
                                api_key=st.session_state.get("ragflow_api_key", ""),
                                base_url=st.session_state.get("ragflow_base_url", ""),
                                chat_id=st.session_state.get("ragflow_chat_id", ""),
                                form_data=form_data,
                                normalize_terms=bool(st.session_state.get("fs_normalize", True)),
                                few_shot_max=int(st.session_state.get("fs_few_shot_k", 2)),
                                temperature=temp_override,
                            )
                        except Exception as ragflow_exc:
                            local_temp = temp_override if temp_override is not None else 0.2
                            st.session_state.result = call_local_rag_from_session(form_data, temperature=local_temp)
                            st.session_state.result["_ragflow_fallback"] = str(ragflow_exc)
                            st.warning(
                                "RAGFlow 当前不可用，已自动回退到本地 RAG。"
                                f" RAGFlow 错误：{str(ragflow_exc)[:260]}"
                            )
                    else:
                        local_temp = temp_override if temp_override is not None else 0.2
                        st.session_state.result = call_local_rag_from_session(form_data, temperature=local_temp)
                    write_audit(
                        "inference_success",
                        {
                            "backend": st.session_state.get("backend_mode", "RAGFlow"),
                            "user": st.session_state.get("login_user", ""),
                            "complaint": form_data.get("complaint", "")[:80],
                        },
                    )
                    st.session_state.last_form = form_data
                except Exception as exc:
                    write_audit(
                        "inference_failed",
                        {
                            "backend": st.session_state.get("backend_mode", "RAGFlow"),
                            "user": st.session_state.get("login_user", ""),
                            "error": str(exc)[:200],
                        },
                    )
                    st.error(f"生成失败：{exc}")
                    st.session_state.result = None

    with right_col:
        st.markdown('<div class="output-title">溯源分析输出区</div>', unsafe_allow_html=True)
        result = st.session_state.get("result")

        # 未点击“开始分析”前：右侧保持空状态（引擎转动动画）
        if not result:
            st.markdown(
                """
                <style>
                .engine-wrap{
                  display:flex;align-items:center;justify-content:center;
                  height: 520px;
                  border: 1px dashed rgba(89, 126, 182, 0.45);
                  border-radius: 18px;
                  background: rgba(246, 250, 255, 0.38);
                  position: relative;
                  overflow:hidden;
                }
                .engine{
                  width: 118px;height: 118px;border-radius: 999px;
                  border: 10px solid rgba(26, 90, 199, 0.16);
                  border-top-color: rgba(26, 90, 199, 0.85);
                  animation: spin 1.05s linear infinite;
                  box-shadow: 0 10px 26px rgba(20, 64, 132, 0.10);
                }
                .engine-text{
                  position:absolute;bottom: 26px;
                  color:#5c6d86;font-size:14px;
                }
                @keyframes spin{to{transform: rotate(360deg);}}
                </style>
                <div class="engine-wrap">
                  <div class="engine"></div>
                  <div class="engine-text">等待输入信息并点击「开始分析」…</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            return

        report = result.get("report", {}) if isinstance(result, dict) else {}
        trace = result.get("traceability", {}) if isinstance(result, dict) else {}
        last_form = st.session_state.get("last_form", {})

        view_mode = st.radio(
            "显示模式",
            ["嵌套卡片", "知识图谱"],
            horizontal=True,
            key="trace_view_mode",
            label_visibility="collapsed",
        )

        if view_mode == "知识图谱":
            graph_html = build_trace_graph_html(report, trace, last_form)
            st.markdown(
                f'<div class="level-card">'
                f'<div class="level-title">图谱模式 · 可溯源关系图</div>'
                f"{graph_html}"
                f'<div class="graph-hint">图谱用于展示“症状-推理-结论-证据”关系，便于演示可解释链路。</div>'
                f"</div>",
                unsafe_allow_html=True,
            )

            render_level3_html(trace, "证据明细")
            return

        diagnosis = html.escape(str(report.get("primary_diagnosis", "暂无")))
        differential = html.escape(str(report.get("differential_diagnosis", "暂无")))
        risk_alert = html.escape(str(report.get("risk_alert", "暂无")))
        st.markdown(
            f'<div class="level1-wrap">'
            f'<div class="level1-title">Level 1 · 诊断结论</div>'
            f'<div class="diag-pill">{diagnosis}</div>'
            f'<div class="level1-line"><b>鉴别诊断</b>：{differential}</div>'
            f'<div class="level1-line"><b>风险提示</b>：{risk_alert}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )

        complaint_esc = html.escape(str(st.session_state.get("last_form", {}).get("complaint", "暂无")))
        diff_esc = html.escape(str(report.get("differential_diagnosis", "暂无")))
        tests_esc = html.escape(str(report.get("recommended_tests", "暂无")))
        risk_esc = html.escape(str(report.get("risk_alert", "暂无")))
        plan_esc = html.escape(str(report.get("treatment_plan", "暂无")))
        level2_html = (
            f'<div class="level1-wrap">'
            f'<div class="level1-title">Level 2 · 推理链条</div>'
            f'<div class="level2-flow">'
            f'<div class="level2-node-title">① 症状识别与主诉归因</div>'
            f'<div class="level2-node-body">{complaint_esc}</div>'
            f"</div>"
            f'<div class="logic-arrow">↓</div>'
            f'<div class="level2-flow">'
            f'<div class="level2-node-title">② 鉴别诊断推理</div>'
            f'<div class="level2-node-body">{diff_esc}</div>'
            f"</div>"
            f'<div class="logic-arrow">↓</div>'
            f'<div class="level2-flow">'
            f'<div class="level2-node-title">③ 检查建议与风险分层</div>'
            f'<div class="level2-node-body"><b>建议检查</b>：{tests_esc}</div>'
            f'<div class="level2-node-body"><b>风险提示</b>：{risk_esc}</div>'
            f"</div>"
            f'<div class="logic-arrow">↓</div>'
            f'<div class="level2-flow">'
            f'<div class="level2-node-title">④ 诊疗方案输出</div>'
            f'<div class="level2-node-body">{plan_esc}</div>'
            f"</div>"
            f"</div>"
        )
        st.markdown(level2_html, unsafe_allow_html=True)
        render_level3_html(trace, "Level 3 · 证据原文")
