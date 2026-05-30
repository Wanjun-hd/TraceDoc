import os

import streamlit as st

from audit_logger import write_audit

DEFAULT_LOGIN_USER = os.getenv("APP_LOGIN_USER", "admin")
DEFAULT_LOGIN_PASS = os.getenv("APP_LOGIN_PASS", "123456")


def render_login_page() -> None:
    st.markdown(
        """
        <style>
        :root {
            --primary-color: #2E77E8;
        }
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
        .login-wrap {
            max-width: 980px;
            margin: 0 auto;
            padding-top: 64px;
        }
        .login-head {
            text-align: center;
            margin-bottom: 18px;
        }
        .login-title {
            font-size: 52px;
            font-weight: 800;
            color: #1A3E8E;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }
        .login-sub {
            font-size: 20px;
            color: #596984;
        }
        .field-label {
            color: #2f4e79;
            font-size: 15px;
            margin-bottom: 6px;
            font-weight: 600;
        }
        .login-divider {
            height: 10px;
        }
        .tip {
            margin-top: 14px;
            color: #73809a;
            font-size: 13px;
            text-align: center;
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
        .stForm [data-testid="stFormSubmitButton"] button {
            border-radius: 999px;
            height: 50px;
            font-size: 19px;
            font-weight: 700;
            border: none !important;
            color: #fff !important;
            background: linear-gradient(90deg, #1A4FB0 0%, #2E77E8 55%, #53b8cf 100%) !important;
            box-shadow: 0 9px 18px rgba(26, 90, 199, 0.28) !important;
        }
        .stForm [data-testid="stFormSubmitButton"] button:hover {
            filter: brightness(1.04);
        }
        .back-wrap .stButton > button[kind="primary"] {
            border-radius: 999px;
            border: none !important;
            color: #fff !important;
            height: 56px;
            font-size: 20px;
            font-weight: 700;
            background: linear-gradient(90deg, #1A4FB0 0%, #2E77E8 100%) !important;
            box-shadow: 0 10px 24px rgba(26, 90, 199, 0.34) !important;
            max-width: 340px;
            margin: 22px auto 0 auto;
            display: block;
            transition: transform 0.2s ease, box-shadow 0.2s ease, filter 0.2s ease;
        }
        .back-wrap .stButton > button[kind="primary"]:hover {
            transform: translateY(-1px);
            filter: brightness(1.03);
            box-shadow: 0 14px 30px rgba(26, 90, 199, 0.40);
        }
        .register-note {
            margin-top: 10px;
            text-align: center;
            color: #8a96a9;
            font-size: 14px;
        }
        .register-link-wrap .stButton > button[kind="secondary"] {
            border: none;
            background: transparent;
            box-shadow: none;
            color: #8a96a9;
            font-size: 15px;
            text-decoration: underline;
            min-height: 30px;
            height: 30px;
            padding: 0;
        }
        .register-link-wrap .stButton > button[kind="secondary"]:hover {
            color: #5f6f89;
            background: transparent;
            border: none;
        }
        .stForm [data-testid="stFormSubmitButton"] button:focus,
        .stForm [data-testid="stFormSubmitButton"] button:focus-visible,
        .back-wrap .stButton > button[kind="primary"]:focus,
        .back-wrap .stButton > button[kind="primary"]:focus-visible {
            outline: 2px solid rgba(102, 164, 255, 0.60) !important;
            box-shadow: 0 0 0 2px rgba(102, 164, 255, 0.20) !important;
        }
        .login-card .stTextInput {
            margin-bottom: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="login-wrap">', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="login-head">
          <div class="login-title">账号登录</div>
          <div class="login-sub">登录后可进入小溯医生问诊与溯源分析</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, center_col, _ = st.columns([1.1, 2.1, 1.1])
    with center_col:
        with st.form("login_form"):
            st.markdown('<div class="field-label">用户名</div>', unsafe_allow_html=True)
            username = st.text_input("用户名", placeholder="请输入用户名", label_visibility="collapsed")
            st.markdown('<div class="login-divider"></div>', unsafe_allow_html=True)
            st.markdown('<div class="field-label">密码</div>', unsafe_allow_html=True)
            password = st.text_input("密码", type="password", placeholder="请输入密码", label_visibility="collapsed")
            st.markdown('<div class="login-divider"></div>', unsafe_allow_html=True)
            submitted = st.form_submit_button("登录", use_container_width=True)

    if submitted:
        valid_builtin = username == DEFAULT_LOGIN_USER and password == DEFAULT_LOGIN_PASS
        valid_registered = st.session_state.registered_users.get(username) == password
        if valid_builtin or valid_registered:
            st.session_state.logged_in = True
            st.session_state.login_user = username
            write_audit("login_success", {"user": username})
            st.success("登录成功，正在返回首页...")
            st.session_state.current_page = "home"
            st.rerun()
        else:
            write_audit("login_failed", {"user": username})
            st.error("用户名或密码错误，请重试。")

    st.markdown('<div class="back-wrap">', unsafe_allow_html=True)
    _, nav_c, _ = st.columns([1.1, 1.2, 1.1])
    with nav_c:
        if st.button("← 返回首页", type="secondary", use_container_width=True, key="back_home_btn"):
            st.session_state.current_page = "home"
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown('<div class="register-note">还没有账号？</div>', unsafe_allow_html=True)
    st.markdown('<div class="register-link-wrap">', unsafe_allow_html=True)
    _, reg_col, _ = st.columns([2.3, 1, 2.3])
    with reg_col:
        if st.button("注册", type="secondary", use_container_width=True, key="go_register_text_link"):
            st.session_state.current_page = "register"
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
