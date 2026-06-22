"""
utils/styles.py — Single source of truth for CSS + logo + sidebar.
Both app.py and pages/crm.py import from here to guarantee 100% consistency.
"""
import os
import base64
from pathlib import Path
import streamlit as st

# ── Logo ──────────────────────────────────────────────────────
_BASE = Path(__file__).parent.parent          # project root

def _b64(p: Path) -> str:
    return base64.b64encode(p.read_bytes()).decode() if p.exists() else ""

_LOGO_B64 = _b64(_BASE / "kayfa_logo.png")
LOGO_SRC  = f"data:image/png;base64,{_LOGO_B64}" if _LOGO_B64 else ""

# chatbot avatar (Dynamic path for both local and server)
# chatbot avatar (Dynamic path for server)
_BOT_PATH = _BASE / "chatbot.png"
_BOT_B64  = _b64(_BOT_PATH) or _LOGO_B64
BOT_SRC   = f"data:image/png;base64,{_BOT_B64}" if _BOT_B64 else LOGO_SRC


# ── Master CSS ────────────────────────────────────────────────
DARK_CSS = """
<style>
/* ════════════════════════════════════════════════════════════
   FORCED DARK THEME — survives system light-mode preference
   ════════════════════════════════════════════════════════════ */
:root {
    --bg:          #111111;
    --bg-s:        #1a1a1a;   
    --bg-c:        #1e1e1e;   
    --border:      #2a2a2a;
    --border2:     #2e2e2e;
    --txt:         #e8e8e8;
    --txt-m:       #888888;
    --accent:      #4a7acf;
    --acc-bg:      #1e2a3e;
    --u-bub:       #1a3a6b;
    --u-brd:       #2a4a8a;
}


html, body, [data-testid="stApp"], [data-testid="stAppViewContainer"], 
[data-testid="stHeader"], header[data-testid="stHeader"], section.main {
    background-color: var(--bg) !important;
    background: var(--bg) !important;
    color: var(--txt) !important;
}

[data-testid="stSidebar"], [data-testid="stSidebar"] > div {
    background-color: var(--bg-s) !important;
    border-right: 1px solid var(--border);
}

[data-testid="stSidebarNav"], [data-testid="stDecoration"] { display:none !important; }

p, span, label, div, h1, h2, h3, h4, li, td, th {
    color: var(--txt) !important;
}

/* 🚀 تكبير اللوجو واسم كيفا في الـ Sidebar للضِعف */
.sb-logo {
    display: flex; align-items: center; gap: 16px;
    padding: 10px 0 24px 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: 22px;
}
.sb-logo img  { width: 110px !important; border-radius: 16px; flex-shrink: 0; }
.sb-logo .sb-name {
    font-size: 2.3rem !important; font-weight: 900 !important; 
    color: #ffffff !important; letter-spacing: .5px;
}

/* 🚀 تكبير القوائم (مساعد المبيعات ولوحة الإدارة) */
.nav-item {
    display: flex; align-items: center; gap: 12px;
    padding: 16px 18px !important; border-radius: 12px; margin-bottom: 8px;
    color: #bbb !important; font-size: 1.35rem !important; 
    font-weight: bold;
    text-decoration: none; border: 1px solid transparent;
    transition: all .18s;
}
.nav-item:hover {
    background: var(--acc-bg);
    border-color: var(--u-brd);
    color: #9ec4ff !important;
}
.nav-item.active {
    background: var(--acc-bg);
    border-color: var(--u-brd);
    color: #6ba3ff !important;
}

/* ── Main header ──────────────────────────────── */
.kayfa-header {
    display: flex; align-items: center; gap: 16px;
    padding: 14px 0 12px 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: 24px;
}
.kayfa-header img  { width: 60px; border-radius: 12px; }
.kayfa-header .hdr-title {
    font-size: 1.7rem; font-weight: 800;
    color: #ffffff !important;
}

/* ── Welcome banner ───────────────────────────── */
.welcome-banner {
    background: linear-gradient(135deg, #1a2a4a 0%, #141414 100%);
    border: 1px solid #2a3a5a; border-radius: 16px;
    padding: 28px 24px; text-align: center; margin-bottom: 24px;
}
.welcome-banner h2 { color: #ffffff !important; font-size: 1.4rem; margin: 0; }
.welcome-banner p  { color: #ccc !important; font-size: 1.0rem; margin: 8px 0 0; }

/* ── Chat bubbles ─────────────────────────────── */
.chat-wrap { display: flex; flex-direction: column; gap: 40px; padding: 10px 0 40px 0; }

.brow       { display: flex; align-items: flex-end; gap: 15px; max-width: 84%; margin-bottom: 15px; }
.brow.agent { margin-right: auto; }
.brow.user  { margin-left: auto; flex-direction: row-reverse; }

.av {
    width: 38px; height: 38px; border-radius: 50%;
    flex-shrink: 0; overflow: hidden;
    display: flex; align-items: center; justify-content: center;
    font-size: 17px;
}
.av img { width: 100%; height: 100%; object-fit: cover; border-radius: 50%; }
.av.uav { background: var(--u-bub); }

.bbl {
    padding: 13px 18px; border-radius: 18px;
    line-height: 1.7; font-size: 1.05rem;
    word-break: break-word; white-space: pre-wrap;
    color: var(--txt) !important;
}
.bbl.ab {
    background: var(--bg-c);
    border: 1px solid var(--border2);
    border-bottom-left-radius: 4px;
}
.bbl.ub {
    background: var(--u-bub);
    border: 1px solid var(--u-brd);
    border-bottom-right-radius: 4px;
    color: #e8f0ff !important;
}
.bbl.rtl { direction: rtl; text-align: right; }
.bbl.ltr { direction: ltr; text-align: left;  }

/* ── Chat input — RTL + dark ─────────────────── */
[data-testid="stChatInput"] textarea {
    direction: rtl !important;
    text-align: right !important;
    background: var(--bg-s) !important;
    color: var(--txt)        !important;
    border: 1px solid var(--border2) !important;
    border-radius: 14px !important;
    font-size: 1.05rem !important;
}
[data-testid="stChatInput"] textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px rgba(74,122,207,.25) !important;
}
.stChatMessage { direction: rtl; text-align: right; margin-bottom: 20px !important; }

/* ── Quick-reply buttons ──────────────────────── */
.stButton > button {
    background: var(--bg-s)  !important;
    color: var(--txt)         !important;
    border: 1px solid var(--border2) !important;
    border-radius: 12px !important;
    font-size: .95rem  !important;
    text-align: right  !important;
    direction: rtl     !important;
    padding: 10px 14px !important;
    white-space: normal !important;
    height: auto !important;
    line-height: 1.55 !important;
}
.stButton > button:hover {
    border-color: var(--accent)  !important;
    background: var(--acc-bg)    !important;
    color: #e0e8ff !important;
}

/* ── Right panel cards ───────────────────────── */
.panel-card {
    background: var(--bg-s);
    border: 1px solid var(--border);
    border-radius: 14px; padding: 16px; margin-bottom: 14px;
}
.panel-title {
    font-size: .85rem; font-weight: 700;
    color: var(--txt-m) !important;
    text-transform: uppercase; letter-spacing: .8px; margin-bottom: 12px;
}
.metric-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 8px 0; border-bottom: 1px solid #222; font-size: .95rem;
}
.metric-row:last-child { border-bottom: none; }
.metric-label { color: #bbb !important; }
.metric-val {
    background: #252525; color: #e0e0e0 !important;
    padding: 2px 10px; border-radius: 20px;
    font-weight: 600; font-size: .9rem;
}

/* ── CRM metric cards ─────────────────────────── */
div[data-testid="stMetric"] {
    background: var(--bg-s) !important;
    border: 1px solid var(--border) !important;
    border-radius: 14px !important;
    padding: 18px 20px !important;
    border-left: 4px solid var(--accent) !important;
}
div[data-testid="stMetricValue"] { font-size: 2.2rem !important; color: #fff !important; }
div[data-testid="stMetricLabel"] { color: var(--txt-m) !important; font-size: 1rem !important; }

/* ── CRM badges ───────────────────────────────── */
.badge-hot  { background:#3d1515; color:#f87171; padding:4px 14px; border-radius:20px; font-size:.9rem; font-weight:700; }
.badge-warm { background:#3d2e08; color:#fbbf24; padding:4px 14px; border-radius:20px; font-size:.9rem; font-weight:700; }
.badge-cold { background:#0d2436; color:#38bdf8; padding:4px 14px; border-radius:20px; font-size:.9rem; font-weight:700; }

/* ── CRM detail panel ────────────────────────── */
.detail-card {
    background: var(--bg-s); border: 1px solid var(--border);
    border-radius: 14px; padding: 20px;
    direction: rtl; 
}
.detail-row {
    display: flex; justify-content: space-between;
    padding: 10px 0; border-bottom: 1px solid #222; font-size: 1.05rem; 
    direction: rtl;
}
.detail-row:last-child { border-bottom: none; }
.dl { color: var(--txt-m) !important; font-weight: bold; }
.dv { color: var(--txt) !important; font-weight: 500; text-align: left; }

/* 🚀 حل الـ RTL والخط الصغير في الملخص والإجراء التالي */
div[data-testid="stAlert"] {
    direction: rtl !important;
    text-align: right !important;
}
div[data-testid="stAlert"] p {
    font-size: 1.15rem !important;
    line-height: 1.7 !important;
}
</style>
"""

def inject_css():
    st.markdown(DARK_CSS, unsafe_allow_html=True)

def render_sidebar(active: str = "chat"):
    is_admin = st.session_state.get("role") == "admin"
    user_email = st.session_state.get("user_email", "")
    
    with st.sidebar:
        logo_html = (f'<img src="{LOGO_SRC}" style="width: 140px; border-radius: 16px; margin-bottom: 20px;">'
                     if LOGO_SRC else '<span style="font-size:32px;">🎓</span>')
        st.markdown(
            f'<div style="text-align: center;">{logo_html}'
            f'<h1 style="font-size: 2.2rem; font-weight: 900; color: #fff; margin-top: -10px; margin-bottom: 30px;">Kayfa</h1></div>',
            unsafe_allow_html=True,
        )

        st.page_link("app.py", label="💬 مساعد المبيعات", icon=None)

        if is_admin:
            st.page_link("pages/crm.py", label="📊 لوحة الإدارة", icon=None)

        st.divider()

        if user_email:
            st.markdown(
                f'<p style="font-size:.9rem;color:#aaa;text-align:center;">{user_email}</p>',
                unsafe_allow_html=True,
            )

        if st.button("تسجيل الخروج 🚪", use_container_width=True):
            st.session_state.clear() # نمسح الذاكرة بالكامل عند الخروج فقط
            st.rerun()