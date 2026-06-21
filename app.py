import os
import re
import uuid
import time
from typing import Optional

import streamlit as st
from dotenv import load_dotenv

from utils.styles import inject_css, render_sidebar, LOGO_SRC, BOT_SRC
from core.loader import DataLoader
from core.rag import KayfaRAG
from core.agent import agent, AgentDeps, KAYFA_TURN_USAGE_LIMITS
from database.mongodb import MongoDBHandler
from pydantic_ai.exceptions import ModelHTTPError, UsageLimitExceeded

load_dotenv()

# ── Page config ───────────────────────────────────────────────
st.set_page_config(
    page_title="Kayfa AI Sales Agent",
    page_icon=LOGO_SRC or "🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()   


# ── Cached resources ──────────────────────────────────────────
@st.cache_resource
def init_db():
    return MongoDBHandler()

@st.cache_resource
def init_system(_db):
    loader  = DataLoader()
    docs    = loader.load_text()
    courses = loader.load_json()
    rag     = KayfaRAG(docs)
    rag.load_database()
    return AgentDeps(rag=rag, courses=courses, db_handler=_db)


# ── Auth — any email + "123"; admin gets role="admin" ────────
def require_login() -> bool:
    if st.session_state.get("global_authenticated"):
        return True

    # وسعنا المساحة في النص عشان اللوجو يكبر
    _, col, _ = st.columns([1, 1.5, 1])
    with col:
        if LOGO_SRC:
            st.markdown(
                f'<div style="text-align:center;margin-bottom:15px;">'
                f'<img src="{LOGO_SRC}" style="width:180px;border-radius:20px;box-shadow: 0 4px 12px rgba(0,0,0,0.5);"></div>',
                unsafe_allow_html=True,
            )
        st.markdown(
            
            "<h1 style='text-align:center;color:#fff;margin-bottom:35px;font-weight:900;font-size:2.8rem;'>"
            "Kayfa AI Sales Agent</h1>",
            unsafe_allow_html=True,
        )

        email = st.text_input("Email", key="li_email",
                               label_visibility="collapsed",
                               placeholder="you@example.com")

        pw = st.text_input("Password", type="password", key="li_pw",
                            label_visibility="collapsed", placeholder="••••••••")

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        if st.button("Sign In", use_container_width=True, key="signin_btn"):
            admin_email = os.getenv("APP_EMAIL", "admin@kayfa.com")
            admin_pw    = os.getenv("APP_PASSWORD", "123")
            valid = (pw == "123") or (email == admin_email and pw == admin_pw)

            if not email:
                st.error("Please enter your email.")
            elif valid:
                role = "admin" if email == admin_email else "user"
                st.session_state["global_authenticated"] = True
                st.session_state["role"]       = role
                st.session_state["user_email"] = email
                try:
                    MongoDBHandler().log_login(email)
                except Exception:
                    pass
                
                # 🚀 الحل السحري للأدمن: التحويل يحصل هنا مرة واحدة بس!
                if role == "admin":
                    st.switch_page("pages/crm.py")
                else:
                    st.rerun()
            else:
                st.error("Incorrect password.")
    return False


# ── Bubble HTML ───────────────────────────────────────────────
def _bubble(text: str, role: str) -> str:
    rtl     = bool(re.search(r'[\u0600-\u06FF]', text or ""))
    dir_cls = "rtl" if rtl else "ltr"
    bub_cls = "ab" if role == "agent" else "ub"
    row_cls = "agent" if role == "agent" else "user"
    safe    = (text or "").replace("&","&amp;").replace("<","&lt;") \
                          .replace(">","&gt;").replace("\n","<br>")

    av = (f'<div class="av"><img src="{BOT_SRC}" alt="Kayfa"></div>'
          if BOT_SRC else '<div class="av" style="background:#1e3a5f;">🎓</div>') if role == "agent" else '<div class="av uav">👤</div>'

    return (f'<div class="brow {row_cls}">'
            f'{av}<div class="bbl {bub_cls} {dir_cls}">{safe}</div>'
            f'</div>')


# ── Small-talk ──────────────────────────────────────
_PAT = [
    r"^\s*(hi|hello|hey|good\s*(morning|evening|afternoon))\s*[!.]*\s*$",
    r"^\s*(السلام عليكم|سلام|أهلا|اهلا|مرحبا|صباح الخير|مساء الخير|هاي|هلا)\s*[!.،]*\s*$",
    r"^\s*(thanks|thank you|thx|شكرا|شكراً|تمام|اوكي|ok|okay)\s*[!.،]*\s*$",
]
_AR = "أهلاً بيك في كيف! 👋 قولي بس عاوز تتعلم في إيه وأنا أرشحلك المسار الأنسب."
_EN = "Welcome to Kayfa! 👋 Tell me what you'd like to learn and I'll point you to the right track."

def _small_talk(text: str) -> Optional[str]:
    s = (text or "").strip()
    if not s or len(s) > 50:
        return None
    for p in _PAT:
        if re.match(p, s, re.IGNORECASE):
            return _AR if re.search(r'[\u0600-\u06FF]', s) else _EN
    return None


# ── Agent call ────────────────────────────────────────────────
def _run_agent(prompt: str, deps, sid: str) -> str:
    for attempt in range(1, 4):
        try:
            result = agent.run_sync(
                prompt,
                deps=deps,
                message_history=st.session_state.get("pydantic_messages", []),
                usage_limits=KAYFA_TURN_USAGE_LIMITS,
            )
            st.session_state["pydantic_messages"] = result.all_messages()
            return result.output
        except UsageLimitExceeded:
            return "السؤال احتاج تفكيراً أعمق. ممكن تبسّط سؤالك؟"
        except ModelHTTPError as e:
            is_rate = (getattr(e, "status_code", None) == 429 or "429" in str(e))
            if attempt < 3:
                time.sleep(20 * attempt if is_rate else 4 * attempt)
            else:
                return "السيرفر مشغول، يرجى المحاولة لاحقاً."
        except Exception as e:
            return f"عفواً، لم أتمكن من معالجة طلبك: {e}"


# ── Right panel ───────────────────────────────────────────────
def _right_panel(sid: str):
    st.markdown("""
    <div class="panel-card">
        <div class="panel-title">📚 Knowledge Base & Analytics</div>
        <div class="metric-row">
            <span class="metric-label">المقررات والدروس التدريبية</span>
            <span class="metric-val">52</span>
        </div>
        <div class="metric-row">
            <span class="metric-label">مسارات وخطوات تعليمية</span>
            <span class="metric-val">13</span>
        </div>
        <div class="metric-row">
            <span class="metric-label">فروع متخصصة</span>
            <span class="metric-val">3</span>
        </div>
    </div>""", unsafe_allow_html=True)

    if st.button("🔄 New Chat", use_container_width=True, key="nc"):
        st.session_state.pop("messages", None)
        st.session_state.pop("pydantic_messages", None)
        st.session_state["session_id"] = str(uuid.uuid4())
        st.rerun()


# ── Quick replies ─────────────────────────────────────────────
QUICK = [
    "← ما هي دبلومة الأمن السيبراني الشاملة وتفاصيلها؟ 🛡️",
    "← بكم سعر كورس الذكاء الاصطناعي وبوت كامب الـ 5 شهور؟ 🧠",
    "← ما هي شروط وسياسة استرجاع الأموال لديكم؟ 💵",
    "← ابحث لي عن كورسات يعلمها أسامة سالم مدير إيتيكا للتكنولوجيا. 👤",
]

def _quick_replies():
    if st.session_state.get("messages"):   
        return
    c1, c2 = st.columns(2)
    for i, q in enumerate(QUICK):
        with (c1 if i % 2 == 0 else c2):
            if st.button(q, key=f"qr{i}", use_container_width=True):
                st.session_state["qr_pick"] = q


# ── Main ──────────────────────────────────────────────────────
def main():
    if not require_login():
        st.stop()
   
    db   = init_db()
    deps = init_system(db)

    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid.uuid4())
    sid = st.session_state["session_id"]

    render_sidebar(active="chat")   

    left, right = st.columns([2.7, 1], gap="large")

    # ── LEFT ──────────────────────────────────────────────────
    with left:
        logo_tag = f'<img src="{LOGO_SRC}" alt="logo">' if LOGO_SRC else ""
        st.markdown(
            f'<div class="kayfa-header">{logo_tag}'
            f'<span class="hdr-title">AI Sales Agent</span></div>',
            unsafe_allow_html=True,
        )

        if "messages" not in st.session_state:
            st.session_state["messages"]          = db.get_chat_history(sid)
            st.session_state["pydantic_messages"] = []

        msgs = st.session_state["messages"]

        if not msgs:
            st.markdown("""
            <div class="welcome-banner">
                <h2>Welcome to Kayfa's Intelligent Sales Agent!</h2>
                <p>اسألني عن أي كورس، مسار، أو دبلومة وسأرشدك للخيار الأنسب</p>
            </div>""", unsafe_allow_html=True)

        # حاوية الشات الثابتة (Chat Container) - هذا هو حل الرسايل الطايرة
        chat_container = st.container()
        
        with chat_container:
            st.markdown('<div class="chat-wrap">', unsafe_allow_html=True)
            for m in msgs:
                role = "agent" if m.get("sender") == "assistant" else "user"
                st.markdown(_bubble(m.get("text", ""), role), unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        _quick_replies()

        # Chat Input
        prompt = (st.chat_input("...اكتب استفسارك هنا") or st.session_state.pop("qr_pick", None))
        
        if prompt:
            # 1. إضافة رسالة اليوزر
            msgs.append({"sender": "user", "text": prompt})
            try:
                db.save_chat_turn(sid, "user", prompt)
            except: pass

            # 2. عرضها فورا في نفس الحاوية (فوق صندوق الإدخال)
            with chat_container:
                st.markdown(_bubble(prompt, "user"), unsafe_allow_html=True)

                reply = _small_talk(prompt)
                if not reply:
                    with st.spinner("جاري التفكير…"):
                        reply = _run_agent(prompt, deps, sid)

                if reply:
                    st.markdown(_bubble(reply, "agent"), unsafe_allow_html=True)

            # 3. حفظ الرد وتحديث الشاشة
            if reply:
                msgs.append({"sender": "assistant", "text": reply})
                try:
                    db.save_chat_turn(sid, "assistant", reply)
                except: pass
            
            st.rerun()

    # ── RIGHT ─────────────────────────────────────────────────
    with right:
        _right_panel(sid)

if __name__ == "__main__":
    main()