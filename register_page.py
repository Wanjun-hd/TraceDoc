import os

import streamlit as st

from audit_logger import write_audit

DEFAULT_LOGIN_USER = os.getenv("APP_LOGIN_USER", "admin")
DEFAULT_LOGIN_PASS = os.getenv("APP_LOGIN_PASS", "123456")


def render_register_page() -> None:
    st.markdown(
        """
        <style>
        :root { --primary-color: #2E77E8; }
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        [data-testid="stToolbar"] {display: none;}
        .stApp {
            background:
              radial-gradient(circle at 12% 16%, rgba(90, 150, 230, 0.16), transparent 36%),
              radial-gradient(circle at 86% 22%, rgba(26, 90, 199, 0.10), transparent 38%),
              linear-gradient(120deg, #edf3ff 0%, #f8fbff 52%, #eef6ff 100%);
        }
        .stApp::before {
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            opacity: 0.05;
            background:
              linear-gradient(115deg, rgba(26, 90, 199, 0.34) 1px, transparent 1px) 0 0 / 36px 36px,
              linear-gradient(-115deg, rgba(26, 90, 199, 0.24) 1px, transparent 1px) 0 0 / 36px 36px;
        }
        .register-wrap {
            max-width: 980px;
            margin: 0 auto;
            padding-top: 64px;
        }
        .register-head {
            text-align: center;
            margin-bottom: 18px;
        }
        .register-title {
            font-size: 52px;
            font-weight: 800;
            color: #1A3E8E;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }
        .register-sub {
            font-size: 20px;
            color: #596984;
        }
        .field-label {
            color: #2f4e79;
            font-size: 15px;
            margin-bottom: 6px;
            font-weight: 600;
        }
        .field-gap {
            height: 10px;
        }
        .stTextInput > div > div > input {
            border-radius: 13px;
            border: 1px solid rgba(101, 178, 229, 0.72);
            background: linear-gradient(180deg, rgba(255,255,255,0.84) 0%, rgba(239,246,255,0.78) 100%);
            box-shadow: inset 0 1px 3px rgba(96, 128, 180, 0.16);
            color: #1f3658;
        }
        .stTextInput > div > div > input:focus {
            border-color: #67b8ea;
            box-shadow: 0 0 0 2px rgba(103, 184, 234, 0.20);
        }
        div[data-testid="stForm"] {
            border-radius: 28px;
            border: 1px solid rgba(255,255,255,0.92);
            background: rgba(255,255,255,0.46);
            backdrop-filter: blur(14px);
            -webkit-backdrop-filter: blur(14px);
            box-shadow:
              inset 0 1px 0 rgba(255,255,255,0.72),
              0 16px 34px rgba(20, 64, 132, 0.13);
            padding: 30px 34px 22px 34px;
        }
        .stForm [data-testid="stFormSubmitButton"] button,
        .nav-wrap .stButton > button[kind="primary"] {
            border-radius: 999px;
            height: 56px;
            font-size: 20px;
            font-weight: 700;
            border: none !important;
            color: #fff !important;
            background: linear-gradient(90deg, #1A4FB0 0%, #2E77E8 100%) !important;
            box-shadow: 0 10px 24px rgba(26, 90, 199, 0.34) !important;
            transition: transform 0.2s ease, box-shadow 0.2s ease, filter 0.2s ease;
        }
        .stForm [data-testid="stFormSubmitButton"] button:hover,
        .nav-wrap .stButton > button[kind="primary"]:hover {
            transform: translateY(-1px);
            filter: brightness(1.03);
            box-shadow: 0 14px 30px rgba(26, 90, 199, 0.40) !important;
        }
        .tip {
            margin-top: 12px;
            color: #73809a;
            font-size: 13px;
            text-align: center;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="register-wrap">', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="register-head">
          <div class="register-title">账号注册</div>
          <div class="register-sub">创建新账号后即可返回登录页面进行验证</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, center_col, _ = st.columns([1.1, 2.1, 1.1])
    with center_col:
        with st.form("register_form"):
            st.markdown('<div class="field-label">用户名</div>', unsafe_allow_html=True)
            username = st.text_input("注册用户名", placeholder="请输入注册用户名", label_visibility="collapsed")
            st.markdown('<div class="field-gap"></div>', unsafe_allow_html=True)
            st.markdown('<div class="field-label">密码</div>', unsafe_allow_html=True)
            password = st.text_input("注册密码", type="password", placeholder="请输入密码", label_visibility="collapsed")
            st.markdown('<div class="field-gap"></div>', unsafe_allow_html=True)
            st.markdown('<div class="field-label">确认密码</div>', unsafe_allow_html=True)
            confirm_password = st.text_input("确认密码", type="password", placeholder="请再次输入密码", label_visibility="collapsed")
            st.markdown('<div class="field-gap"></div>', unsafe_allow_html=True)
            submitted = st.form_submit_button("注册", use_container_width=True)

    st.markdown('<div class="nav-wrap">', unsafe_allow_html=True)
    _, back_col, _ = st.columns([1.1, 1.2, 1.1])
    with back_col:
        if st.button("← 返回登录", type="secondary", use_container_width=True):
            st.session_state.current_page = "login"
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    if submitted:
        username = username.strip()
        if not username or not password:
            st.error("用户名和密码不能为空。")
        elif password != confirm_password:
            st.error("两次输入的密码不一致。")
        elif len(password) < 6:
            st.error("密码长度至少 6 位。")
        elif username == DEFAULT_LOGIN_USER:
            st.error("该用户名已存在，请更换用户名。")
        elif username in st.session_state.registered_users:
            st.error("该用户名已存在，请更换用户名。")
        else:
            st.session_state.registered_users[username] = password
            write_audit("register_success", {"user": username})
            st.success("注册成功，正在跳转到登录页...")
            st.session_state.current_page = "login"
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
