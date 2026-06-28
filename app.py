import os
import re
import uuid
import time
from typing import Optional
from datetime import datetime, timezone

import streamlit as st
from dotenv import load_dotenv

from utils.styles import inject_css, render_sidebar, LOGO_SRC, BOT_SRC
from core.loader import DataLoader
from core.rag import KayfaRAG
from database.mongodb import MongoDBHandler
from pydantic_ai.exceptions import ModelHTTPError, UsageLimitExceeded, UnexpectedModelBehavior
from pydantic_ai.models.groq import GroqModel

from core.agent import agent, AgentDeps, KAYFA_TURN_USAGE_LIMITS

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

# ── Auth ──────────────────────────────────────────────────────
def require_login() -> bool:
    if st.session_state.get("global_authenticated"):
        return True

    db = init_db()
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

        mode = st.radio("mode", ["تسجيل الدخول", "حساب جديد"], horizontal=True, label_visibility="collapsed", key="auth_mode")

        if mode == "حساب جديد":
            name = st.text_input("Name", key="su_name", label_visibility="collapsed", placeholder="الاسم")
            email = st.text_input("Email", key="su_email", label_visibility="collapsed", placeholder="you@example.com")
            pw = st.text_input("Password", type="password", key="su_pw", label_visibility="collapsed", placeholder="••••••••")
            pw2 = st.text_input("Confirm Password", type="password", key="su_pw2", label_visibility="collapsed", placeholder="تأكيد كلمة السر")
            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

            if st.button("إنشاء حساب", use_container_width=True, key="signup_btn"):
                if not email or not pw: st.error("من فضلك أدخل البريد الإلكتروني وكلمة السر.")
                elif len(pw) < 8: st.error("كلمة السر لازم تكون 8 أحرف على الأقل.")
                elif pw != pw2: st.error("كلمتا السر غير متطابقتين.")
                else:
                    try:
                        db.signup_user(email, pw, name)
                        st.success("تم إنشاء الحساب بنجاح! سجّل دخولك دلوقتي.")
                    except ValueError as e: st.error(str(e))

        else:
            email = st.text_input("Email", key="li_email", label_visibility="collapsed", placeholder="you@example.com")
            pw = st.text_input("Password", type="password", key="li_pw", label_visibility="collapsed", placeholder="••••••••")
            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

            if st.button("Sign In", use_container_width=True, key="signin_btn"):
                if not email or not pw: st.error("من فضلك أدخل البريد الإلكتروني وكلمة السر.")
                else:
                    try: user = db.login_user(email, pw)
                    except ValueError as e:
                        st.error(str(e))
                        return False

                    admin_email = os.getenv("APP_ADMIN_EMAIL", "").strip().lower()
                    role = "admin" if (user["role"] == "admin" or email.strip().lower() == admin_email) else "user"

                    st.session_state["global_authenticated"] = True
                    st.session_state["role"] = role
                    st.session_state["user_email"] = user["email"]
                    st.session_state["user_id"] = str(user["_id"])
                    st.session_state["user_name"] = user.get("name", user["email"])
                    try: db.log_login(user["email"])
                    except: pass

                    if role == "admin": st.switch_page("pages/crm.py")
                    else: st.rerun()
    return False

# ── Bubble HTML ───────────────────────────────────────────────
def _bubble(text: str, role: str) -> str:
    rtl     = bool(re.search(r'[\u0600-\u06FF]', text or ""))
    dir_cls = "rtl" if rtl else "ltr"
    bub_cls = "ab" if role == "agent" else "ub"
    row_cls = "agent" if role == "agent" else "user"
    safe    = (text or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace("\n","<br>")
    av = (f'<div class="av"><img src="{BOT_SRC}" alt="Kayfa"></div>' if BOT_SRC else '<div class="av" style="background:#1e3a5f;">🎓</div>') if role == "agent" else '<div class="av uav">👤</div>'
    return f'<div class="brow {row_cls}">{av}<div class="bbl {bub_cls} {dir_cls}">{safe}</div></div>'

# ── Small-talk ──────────────────────────────────────
_PAT = [r"^\s*(hi|hello|hey|good\s*(morning|evening|afternoon))\s*[!.]*\s*$", r"^\s*(السلام عليكم|سلام|أهلا|اهلا|مرحبا|صباح الخير|مساء الخير|هاي|هلا)\s*[!.،]*\s*$", r"^\s*(thanks|thank you|thx|شكرا|شكراً|تمام|اوكي|ok|okay)\s*[!.،]*\s*$"]
_AR = "أهلاً بيك في كيف! 👋 قولي بس عاوز تتعلم في إيه وأنا أرشحلك المسار الأنسب."
_EN = "Welcome to Kayfa! 👋 Tell me what you'd like to learn and I'll point you to the right track."

def _small_talk(text: str) -> Optional[str]:
    s = (text or "").strip()
    if not s or len(s) > 50: return None
    for p in _PAT:
        if re.match(p, s, re.IGNORECASE): return _AR if re.search(r'[\u0600-\u06FF]', s) else _EN
    return None

# ── Usage logging (Granular Logic - Fixed) ─────────────────────
def _log_model_usage(result, deps, sid: str, turn_id: int, user_id: str, selected_model_str: str) -> None:
    db = deps.db_handler
    if db is None: return

    messages = result.new_messages()
    prev_request_ts = None
    
    for i, msg in enumerate(messages):
        msg_type = type(msg).__name__

        if msg_type == "ModelRequest":
            ts = getattr(msg, "parts", [None])[0]
            prev_request_ts = getattr(ts, "timestamp", None) if ts else None
            continue

        if msg_type != "ModelResponse": continue

        usage = getattr(msg, "usage", None)
        input_tokens = getattr(usage, "request_tokens", 0) if usage else 0
        output_tokens = getattr(usage, "response_tokens", 0) if usage else 0
        
        # Pydantic AI newer version properties fallback
        if hasattr(usage, "input_tokens"): input_tokens = usage.input_tokens
        if hasattr(usage, "output_tokens"): output_tokens = usage.output_tokens

        model_name = getattr(msg, "model_name", None) or selected_model_str
        provider_name = "openai" if "gpt" in model_name.lower() else "google"

        # 💰 Accurate pricing calculation (without relying on an external pricing file)
        cost_val = 0.0
        if provider_name == "openai":
            cost_val = (input_tokens / 1_000_000) * 0.15 + (output_tokens / 1_000_000) * 0.60
        else:
            cost_val = (input_tokens / 1_000_000) * 0.30 + (output_tokens / 1_000_000) * 2.50

        # Associate tool calls with their results
        tool_calls_info = []
        next_msg = messages[i + 1] if i + 1 < len(messages) else None
        next_returns = {}
        if next_msg is not None and type(next_msg).__name__ == "ModelRequest":
            for p in getattr(next_msg, "parts", []):
                if type(p).__name__ == "ToolReturnPart":
                    next_returns[p.tool_call_id] = getattr(p, "content", str(p))

        for part in msg.parts:
            if type(part).__name__ == "ToolCallPart":
                tool_calls_info.append({
                    "tool_name": part.tool_name,
                    "args": part.args_as_dict() if hasattr(part, "args_as_dict") else getattr(part, "args", {}),
                    "result": next_returns.get(part.tool_call_id),
                })

        response_ts = getattr(msg, "timestamp", None)
        latency_seconds = (response_ts - prev_request_ts).total_seconds() if prev_request_ts and response_ts else None

        log_doc = {
            "user_id": user_id,
            "conversation_id": sid,
            "turn_id": turn_id,
            "call_type": "chat",
            "model_name": model_name,
            "provider_name": provider_name,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "tool_calls": tool_calls_info,
            "latency_seconds": latency_seconds,
            "cost": {"total_cost": cost_val},
            "timestamp": response_ts or datetime.now(timezone.utc),
        }
        try: db.save_usage_log(log_doc)
        except Exception: pass

    # Embeddings invocations
    for emb_call in getattr(deps, "embedding_calls", []):
        emb_cost = (emb_call.get("input_tokens", 0) / 1_000_000) * 0.02
        try:
            db.save_usage_log({
                "user_id": user_id,
                "conversation_id": sid,
                "turn_id": turn_id,
                "call_type": "embedding",
                "model_name": emb_call.get("model_name", "gemini-embedding-001"),
                "provider_name": emb_call.get("provider_name", "google"),
                "input_tokens": emb_call.get("input_tokens", 0),
                "output_tokens": 0,
                "tool_calls": [],
                "latency_seconds": None,
                "cost": {"total_cost": emb_cost},
                "timestamp": emb_call.get("timestamp", datetime.now(timezone.utc)),
            })
        except: pass
    
    # Clear them after saving
    if hasattr(deps, "embedding_calls"):
        deps.embedding_calls.clear()

# ── Agent call ────────────────────────────────────────────────
def _run_agent(prompt: str, deps, sid: str, turn_id: int) -> str:
    # 🚀 Keep the email in `AgentDeps` without adding `turn_id` to the agent class!
    request_deps = AgentDeps(
        rag=deps.rag,
        courses=deps.courses,
        db_handler=deps.db_handler,
        session_id=sid,
        user_email=st.session_state.get("user_email")
    )

    # 🚀 Preserve the LLM router logic
    keywords = ["دبلوم", "كورس", "سعر", "بكام", "مسار", "تفاصيل", "حجز", "تسجيل", "محتوى", "دفع", "تقسيط", "برمجة", "مجاني", "مجانا"]
    
    if any(kw in prompt.lower() for kw in keywords):
        selected_model = "google:gemini-2.5-flash"
    else:
        selected_model = GroqModel('openai/gpt-oss-120b')

    model_str = selected_model if isinstance(selected_model, str) else "groq/gpt-oss-120b"

    for attempt in range(1, 4):
        try:
            result = agent.run_sync(
                prompt,
                deps=request_deps,
                message_history=st.session_state.get("pydantic_messages", []),
                usage_limits=KAYFA_TURN_USAGE_LIMITS,
                model=selected_model  
            )
            st.session_state["pydantic_messages"] = result.all_messages()
            
            # 🚀 Call optimized log function for detailed recording
            _log_model_usage(result, request_deps, sid, turn_id, st.session_state.get("user_id", "anonymous"), model_str)
            
            return result.output

        except UsageLimitExceeded: return "السؤال احتاج تفكيراً أعمق. ممكن تبسّط سؤالك؟"
        except ModelHTTPError as e:
            is_rate = (getattr(e, "status_code", None) == 429 or "429" in str(e))
            if attempt < 3: time.sleep(20 * attempt if is_rate else 4 * attempt)
            else: return "السيرفر مشغول، يرجى المحاولة لاحقاً."
        except UnexpectedModelBehavior as e:
            error_text = str(e)
            if "create_sales_ticket" in error_text or "رقم الهاتف" in error_text:
                return "في مشكلة صغيرة في رقم الهاتف اللي وصلني — مش متطابق مع المدينة/الدولة اللي ذكرتها. ممكن تأكدلي الرقم تاني (مع كود الدولة لو مختلف) عشان أقدر أسجّل بياناتك صح؟ 🙏"
            return "حصلت مشكلة بسيطة في إكمال هذه الخطوة. ممكن تجرّب تصيغ طلبك بشكل مختلف؟ 🙏"
        except Exception as e: return f"عفواً، لم أتمكن من معالجة طلبك: {e}"

# ── Right panel ───────────────────────────────────────────────
def _right_panel(sid: str):
    st.markdown("""
    <div class="panel-card">
        <div class="panel-title">📚 Knowledge Base & Analytics</div>
        <div class="metric-row"><span class="metric-label">المقررات والدروس التدريبية</span><span class="metric-val">52</span></div>
        <div class="metric-row"><span class="metric-label">مسارات وخطوات تعليمية</span><span class="metric-val">13</span></div>
        <div class="metric-row"><span class="metric-label">فروع متخصصة</span><span class="metric-val">3</span></div>
    </div>""", unsafe_allow_html=True)
    if st.button("🔄 New Chat", use_container_width=True, key="nc"):
        st.session_state.pop("messages", None)
        st.session_state.pop("pydantic_messages", None)
        st.session_state["session_id"] = str(uuid.uuid4())
        st.rerun()

# ── Quick replies ─────────────────────────────────────────────
QUICK = ["← ما هي دبلومة الأمن السيبراني الشاملة وتفاصيلها؟ 🛡️", "← بكم سعر كورس الذكاء الاصطناعي وبوت كامب الـ 5 شهور؟ 🧠", "← ما هي شروط وسياسة استرجاع الأموال لديكم؟ 💵", "← ابحث لي عن كورسات يعلمها أسامة سالم مدير إيتيكا للتكنولوجيا. 👤"]
def _quick_replies():
    if st.session_state.get("messages"): return
    c1, c2 = st.columns(2)
    for i, q in enumerate(QUICK):
        with (c1 if i % 2 == 0 else c2):
            if st.button(q, key=f"qr{i}", use_container_width=True): st.session_state["qr_pick"] = q

# ── Main ──────────────────────────────────────────────────────
def main():
    if not require_login(): st.stop()
    db = init_db()
    deps = init_system(db)
    if "session_id" not in st.session_state: st.session_state["session_id"] = str(uuid.uuid4())
    sid = st.session_state["session_id"]
    render_sidebar(active="chat")   
    left, right = st.columns([2.7, 1], gap="large")

    with left:
        logo_tag = f'<img src="{LOGO_SRC}" alt="logo">' if LOGO_SRC else ""
        st.markdown(f'<div class="kayfa-header">{logo_tag}<span class="hdr-title">AI Sales Agent</span></div>', unsafe_allow_html=True)

        if "messages" not in st.session_state:
            st.session_state["messages"] = db.get_chat_history(sid)
            st.session_state["pydantic_messages"] = []
        msgs = st.session_state["messages"]

        if not msgs:
            st.markdown("""<div class="welcome-banner"><h2>Welcome to Kayfa's Intelligent Sales Agent!</h2><p>اسألني عن أي كورس، مسار، أو دبلومة وسأرشدك للخيار الأنسب</p></div>""", unsafe_allow_html=True)

        chat_container = st.container()
        with chat_container:
            st.markdown('<div class="chat-wrap">', unsafe_allow_html=True)
            for m in msgs:
                role = "agent" if m.get("sender") == "assistant" else "user"
                st.markdown(_bubble(m.get("text", ""), role), unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        _quick_replies()
        prompt = (st.chat_input("...اكتب استفسارك هنا") or st.session_state.pop("qr_pick", None))
        
        if prompt:
            turn_id = sum(1 for m in msgs if m.get("sender") == "user") + 1
            msgs.append({"sender": "user", "text": prompt})
            try: db.save_chat_turn(sid, "user", prompt, turn_id=turn_id)
            except: pass

            with chat_container:
                st.markdown(_bubble(prompt, "user"), unsafe_allow_html=True)
                reply = _small_talk(prompt)
                if not reply:
                    loading_placeholder = st.empty()
                    loading_placeholder.markdown(f"""<style>@keyframes pulse-logo {{0% {{ transform: scale(1); opacity: 1; }} 50% {{ transform: scale(1.15); opacity: 0.6; }} 100% {{ transform: scale(1); opacity: 1; }}}}.kayfa-thinking {{display: flex; align-items: center; gap: 12px; direction: rtl; padding: 10px 5px; margin-bottom: 20px;}}.kayfa-thinking img {{width: 35px; height: 35px; border-radius: 50%; animation: pulse-logo 1.2s infinite ease-in-out;}}.kayfa-thinking span {{color: #4CAF50; font-size: 16px; font-weight: bold;}}</style><div class="kayfa-thinking"><img src="{BOT_SRC}" alt="Thinking"><span>جاري التفكير...</span></div>""", unsafe_allow_html=True)
                    reply = _run_agent(prompt, deps, sid, turn_id)
                    loading_placeholder.empty()

                if reply:
                    st.markdown(_bubble(reply, "agent"), unsafe_allow_html=True)

            if reply:
                msgs.append({"sender": "assistant", "text": reply})
                try: db.save_chat_turn(sid, "assistant", reply, turn_id=turn_id)
                except: pass
            st.rerun()

    with right: _right_panel(sid)

if __name__ == "__main__":
    main()