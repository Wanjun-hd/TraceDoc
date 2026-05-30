import os
from pathlib import Path

import streamlit as st

from chat_page import render_chat_page
from home_page import render_home_page
from login_page import render_login_page
from register_page import render_register_page


DEFAULT_BASE_URL = os.getenv("RAGFLOW_BASE_URL", "http://localhost")
DEFAULT_CHAT_ID = os.getenv("RAGFLOW_CHAT_ID", "cff5fda242c311f1bb62da9e0d80549b")
DEFAULT_API_KEY = os.getenv("RAGFLOW_API_KEY", "")
_DEFAULT_KB_PATH = str((Path(__file__).resolve().parent / "核心三库").as_posix())
DEFAULT_LOCAL_KB_DIR = os.getenv("LOCAL_RAG_KB_DIR", _DEFAULT_KB_PATH)
DEFAULT_LOCAL_LLM_BASE_URL = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
DEFAULT_LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "qwen2.5:7b")
DEFAULT_LOCAL_LLM_API_KEY = os.getenv("LOCAL_LLM_API_KEY", "")


def init_state() -> None:
    if "current_page" not in st.session_state:
        st.session_state.current_page = "home"
    if "result" not in st.session_state:
        st.session_state.result = None
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "login_user" not in st.session_state:
        st.session_state.login_user = ""
    if "registered_users" not in st.session_state:
        st.session_state.registered_users = {}
    if "backend_mode" not in st.session_state:
        st.session_state.backend_mode = "本地RAG（无RAGFlow）"
    if "fs_temp_mode" not in st.session_state:
        st.session_state.fs_temp_mode = "在侧栏覆盖"


def render_sidebar() -> None:
    # //AI辅助生成：豆包，2026-04-23
    with st.sidebar:
        st.markdown("### 后端选择")
        st.radio("模型后端", ["RAGFlow", "本地RAG（无RAGFlow）"], key="backend_mode")

        if st.session_state.backend_mode == "RAGFlow":
            st.markdown("### RAGFlow 连接配置")
            st.text_input("Base URL", value=DEFAULT_BASE_URL, key="ragflow_base_url")
            st.text_input(
                "Chat ID",
                value=DEFAULT_CHAT_ID,
                placeholder="在 RAGFlow 中创建助手后复制",
                key="ragflow_chat_id",
            )
            st.text_input(
                "API Key",
                value=DEFAULT_API_KEY,
                type="password",
                placeholder="在 RAGFlow 中生成",
                key="ragflow_api_key",
            )
            st.caption("建议通过环境变量配置：RAGFLOW_BASE_URL / RAGFLOW_CHAT_ID / RAGFLOW_API_KEY")
            st.caption("Docker 启动与对接步骤见项目根目录 RAGFLOW_SETUP.txt")
        else:
            st.markdown("### 本地RAG配置")
            st.text_input("知识库目录", value=DEFAULT_LOCAL_KB_DIR, key="local_kb_dir")
            st.text_input(
                "LLM Base URL(OpenAI兼容)",
                value=DEFAULT_LOCAL_LLM_BASE_URL,
                key="local_llm_base_url",
            )
            st.text_input("LLM Model", value=DEFAULT_LOCAL_LLM_MODEL, key="local_llm_model")
            st.text_input(
                "LLM API Key（可空）",
                value=DEFAULT_LOCAL_LLM_API_KEY,
                type="password",
                key="local_llm_api_key",
            )
            st.number_input("本地检索TopK", min_value=1, max_value=20, value=6, step=1, key="local_top_k")
            st.caption("建议用 Ollama 或其他 OpenAI 兼容接口；知识库目录可放 txt/md/csv/json/pdf。")

        st.markdown("### FS-TraceRAG 参数")
        st.checkbox("医疗术语归一化（应用层）", value=True, key="fs_normalize")
        st.number_input(
            "少样本示例条数（0 关闭）",
            min_value=0,
            max_value=10,
            value=2,
            step=1,
            key="fs_few_shot_k",
        )
        st.radio(
            "生成温度 temperature",
            ["由 RAGFlow 助手配置决定", "在侧栏覆盖"],
            key="fs_temp_mode",
        )
        if st.session_state.fs_temp_mode == "在侧栏覆盖":
            st.slider(
                "temperature",
                min_value=0.0,
                max_value=1.5,
                value=0.2,
                step=0.05,
                key="fs_temperature_val",
            )


def main() -> None:
    st.set_page_config(page_title="小溯医生", page_icon="🩺", layout="wide")
    init_state()
    render_sidebar()
    if st.session_state.current_page == "home":
        render_home_page()
    elif st.session_state.current_page == "login":
        render_login_page()
    elif st.session_state.current_page == "register":
        render_register_page()
    else:
        render_chat_page()


if __name__ == "__main__":
    main()
