from pathlib import Path
import base64

import streamlit as st


APP_TITLE = "小溯医生"
APP_SLOGAN = "TraceDoc - Where Every Diagnosis Has a Source"
APP_DESCRIPTION = "三级溯源临床问答助手"
BASE_DIR = Path(__file__).resolve().parent
IMAGE_CANDIDATES = [
    # 优先使用当前项目目录下的头像图
    BASE_DIR / "_cgi-bin_mmwebwx-bin_webwxgetmsgimg__&MsgID=6996380859071659907&skey=@crypt_5ce87db8_57372616d04a4041226c1716fae5867e&mmweb_appid=wx_webfilehelper.jpg",
    BASE_DIR / "doctor_cartoon_avatar.png",
    BASE_DIR / "Gemini_Generated_Image_izh55aizh55aizh5.png",
    Path(
        r"C:\Users\86138\.cursor\projects\e-dinghuiyu-c4\assets\c__Users_86138_AppData_Roaming_Cursor_User_workspaceStorage_f46c69c76c0458fdc0b6ff9d350b2279_images__1650384C-010F-45D1-85D8-26C28F1D2DE2_-18c7af20-42a4-44c1-b8af-13d3a79d3a71.png"
    ),
]


def _resolve_image() -> str | None:
    for path in IMAGE_CANDIDATES:
        if path.exists():
            return str(path)
    return None


def _image_data_uri(image_path: str | None) -> str | None:
    if not image_path:
        return None
    try:
        p = Path(image_path)
        raw = p.read_bytes()
    except OSError:
        return None
    suffix = p.suffix.lower()
    mime = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
    encoded = base64.b64encode(raw).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


def render_home_page() -> None:
    st.markdown(
        """
        <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        [data-testid="stToolbar"] {display: none;}
        section[data-testid="stSidebar"] {display: none;}
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
            opacity: 0.05;
            background:
              linear-gradient(115deg, rgba(26, 90, 199, 0.34) 1px, transparent 1px) 0 0 / 36px 36px,
              linear-gradient(-115deg, rgba(26, 90, 199, 0.24) 1px, transparent 1px) 0 0 / 36px 36px;
        }
        .page-wrap {
            max-width: 1200px;
            margin: 0 auto;
            padding-top: 24px;
        }
        .top-actions {
            display: flex;
            justify-content: flex-end;
            align-items: center;
            gap: 10px;
            margin: 8px 0 18px 0;
        }
        .stButton > button[kind="secondary"] {
            min-height: 38px;
            height: 38px;
            min-width: 38px;
            width: 38px;
            padding: 0;
            border-radius: 999px;
            border: 1px solid rgba(255, 255, 255, 0.28);
            background: linear-gradient(180deg, #1a4fb0 0%, #18439a 100%);
            color: #f5f5f5;
            font-size: 16px;
            box-shadow:
                inset 0 1px 2px rgba(255,255,255,0.22),
                0 6px 12px rgba(23, 63, 132, 0.24);
            text-shadow: 0 0 5px rgba(255,255,255,0.20);
        }
        .stButton > button[kind="secondary"]:hover {
            border-color: rgba(144, 188, 255, 0.92);
            filter: brightness(1.06);
            box-shadow:
                inset 0 1px 2px rgba(255,255,255,0.22),
                0 8px 16px rgba(24, 67, 154, 0.34);
        }
        .stButton > button[kind="secondary"]:focus,
        .stButton > button[kind="secondary"]:focus-visible {
            outline: 2px solid rgba(110, 170, 255, 0.7) !important;
            box-shadow:
                inset 0 1px 2px rgba(255,255,255,0.22),
                0 8px 16px rgba(24, 67, 154, 0.34) !important;
        }
        .login-chip {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            color: #355886;
            font-size: 14px;
            border: 1px solid rgba(53, 88, 134, 0.24);
            background: rgba(255,255,255,0.44);
            border-radius: 999px;
            padding: 6px 14px;
        }
        .login-text {
            color: #7b8799;
            font-size: 14px;
            letter-spacing: 0.2px;
            margin-top: 10px;
        }
        .top-brand-band {
            text-align: center;
            margin: 26px auto 24px auto;
        }
        .top-slogan {
            font-size: 52px;
            font-weight: 700;
            line-height: 1.15;
            letter-spacing: 0.6px;
            font-family: Georgia, "Times New Roman", "STSong", serif;
            background: linear-gradient(90deg, #516178 0%, #425874 42%, #5f7188 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 0 8px 20px rgba(66, 88, 116, 0.10);
        }
        .top-desc {
            margin-top: 6px;
            color: #6d7b92;
            font-size: 36px;
            font-weight: 500;
            letter-spacing: 1px;
        }
        .left-panel {
            text-align: center;
            padding-top: 22px;
            padding-left: 0;
        }
        .doctor-avatar {
            width: 500px;
            height: 500px;
            margin: 0 auto 24px auto;
            margin-top:-30px;
        }
        .doctor-avatar img {
            width: 100%;
            height: 100%;
            object-fit: contain;
            border-radius: 22px;
            filter: drop-shadow(0 7px 14px rgba(18, 56, 122, 0.18));
        }
        .brand-title {
            font-size: 56px;
            line-height: 1.1;
            font-weight: 900;
            letter-spacing: 2px;
            color: #1A3E8E;
            margin-left: 150px;
            margin-top: -120px;
            margin-bottom: 14px;
        }
        .glass-card {
            margin-top: 24px;
            padding: 30px 34px 34px 34px;
            border-radius: 22px;
            border: 1px solid rgba(255,255,255,0.92);
            background: rgba(255,255,255,0.46);
            backdrop-filter: blur(14px);
            -webkit-backdrop-filter: blur(14px);
            box-shadow:
                inset 0 1px 0 rgba(255,255,255,0.72),
                0 16px 34px rgba(20, 64, 132, 0.13);
            text-align: center;
        }
        .right-panel {
            padding-top: 22px;
        }
        .fake-input {
            width: 96%;
            margin: 0 auto 34px auto;
            height: 50px;
            border-radius: 28px;
            border: 1px solid rgba(38, 88, 170, 0.23);
            background: linear-gradient(180deg, rgba(255,255,255,0.89) 0%, rgba(241,246,255,0.76) 100%);
            box-shadow: inset 0 2px 5px rgba(68, 102, 160, 0.18);
            display: flex;
            align-items: center;
            padding: 0 20px;
            color: #9AA7BA;
            font-size: 16px;
            text-align: left;
        }
        .dialog-title {
            font-size: 44px;
            font-weight: 800;
            color: #1A3E8E;
            margin-bottom: 14px;
        }
        .dialog-sub {
            font-size: 20px;
            line-height: 1.7;
            color: #4f5c72;
            margin-bottom: 18px;
            font-weight: 400;
        }
        .stButton > button[kind="primary"] {
            max-width: 340px;
            margin: 22px auto 0 auto;
            display: block;
            border: none;
            border-radius: 999px;
            height: 56px;
            font-size: 20px;
            font-weight: 700;
            color: #ffffff;
            background: linear-gradient(90deg, #1A4FB0 0%, #2E77E8 100%);
            box-shadow: 0 10px 24px rgba(26, 90, 199, 0.34);
            transition: transform 0.2s ease, box-shadow 0.2s ease, filter 0.2s ease;
        }
        .stButton > button[kind="primary"]:hover {
            transform: translateY(-1px);
            filter: brightness(1.03);
            box-shadow: 0 14px 30px rgba(26, 90, 199, 0.40);
        }
        .legal-tip {
            text-align: center;
            color: #8B97AB;
            font-size: 13px;
            margin-top: 26px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    image_path = _resolve_image()
    image_uri = _image_data_uri(image_path)

    st.markdown('<div class="page-wrap">', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="top-brand-band">
          <div class="top-slogan">{APP_SLOGAN}</div>
          <div class="top-desc">{APP_DESCRIPTION}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    a1, a2, a3 = st.columns([7.2, 0.45, 1.35])
    with a2:
        if st.session_state.get("logged_in"):
            pass
        elif st.button("👤", key="goto_login", help="登录"):
            st.session_state.current_page = "login"
            st.rerun()
    with a3:
        if st.session_state.get("logged_in"):
            user = st.session_state.get("login_user", "用户")
            st.markdown(f'<div class="login-chip">已登录 · {user}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="login-text">登录/注册</div>', unsafe_allow_html=True)
    left, right = st.columns([1.05, 1.55], gap="large")

    with left:
        st.markdown('<div class="left-panel">', unsafe_allow_html=True)
        if image_uri:
            st.markdown(
                f'<div class="doctor-avatar"><img src="{image_uri}" alt="doctor avatar" /></div>',
                unsafe_allow_html=True,
            )
        st.markdown(f'<div class="brand-title">{APP_TITLE}</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="right-panel">', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="glass-card">
              <div class="fake-input">请输入您的问诊要点...</div>
              <div class="dialog-title">开启溯源诊疗对话</div>
              <div class="dialog-sub">请描述患者核心症状与就诊诉求，系统将基于三级证据链进行临床溯源分析，<br/>为您生成可解释的辅助诊疗建议。</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown('<div class="cta-wrap">', unsafe_allow_html=True)
        if st.button("立即开始问诊", type="primary", use_container_width=True):
            st.session_state.current_page = "chat"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        '<div class="legal-tip">本系统仅提供辅助参考，不替代专业医疗诊断</div>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)
