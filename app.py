import os
import re
import uuid
import time
from typing import Optional
import streamlit as st
from dotenv import load_dotenv

from core.loader import DataLoader
from core.rag import KayfaRAG
from core.agent import agent, AgentDeps, KAYFA_TURN_USAGE_LIMITS
from database.mongodb import MongoDBHandler
from pydantic_ai.exceptions import ModelHTTPError, UsageLimitExceeded

load_dotenv()

def render_bubble(text: str):
    """
    يعرض رسالة الشات مع اتجاه نص صريح:
    - rtl + محاذاة لليمين لو النص فيه حروف عربية (يدعم السوري/السعودي/المصري لأنها نفس الحروف).
    - ltr + محاذاة لليسار للإنجليزي.
    لازم اتجاه صريح هنا (مش direction:auto) لأن auto ممكن يعطي نتيجة غلط
    لما تتقابل في نفس الرسالة كلمات إنجليزية زي SOC أو Python وسط جملة عربية.
    """
    has_arabic = bool(re.search(r'[\u0600-\u06FF]', text or ""))
    direction = "rtl" if has_arabic else "ltr"
    align = "right" if has_arabic else "left"
    st.markdown(
        f"<div style='direction:{direction}; text-align:{align};'>{text}</div>",
        unsafe_allow_html=True,
    )

@st.cache_resource
def init_db():
    return MongoDBHandler()

# =========================
# Lightweight Pre-Router (تحسين توكنز)
# =========================
# قبل استدعاء agent.run_sync (اللي معاه الـ system prompt الكامل + تعريف
# الأدوات + جولتين LLM على الأقل) بنفحص أول لو الرسالة "تحية/كلام عابر" بسيط
# مالوش أي علاقة بكورسات أو أسعار أو نية شراء. في هذه الحالة بس بنرد برسالة
# ثابتة بدون أي استدعاء للموديل خالص - توفير 100% من توكنز هذه الرسالة
# (كانت تكلف ~1,500+ توكن في الـ turn الأول بس لمجرد قول "صباح الخير").
# لو الرسالة فيها أي إشارة لكورس/سعر/تسجيل/مشكلة فعلية، بترجع None فوراً
# والتدفق الطبيعي (agent.run_sync) بيشتغل عادي - فالفلتر دايماً "متحفظ" ولا
# بيرفض أبداً سؤال حقيقي.
_SMALL_TALK_PATTERNS = [
    r"^\s*(hi|hello|hey|good\s*(morning|evening|afternoon))\s*[!.]*\s*$",
    r"^\s*(السلام عليكم|سلام عليكم|أهلا|اهلا|أهلاً|مرحبا|صباح الخير|مساء الخير|هاي|هلا)\s*[!.،]*\s*$",
    r"^\s*(thanks|thank you|thx)\s*[!.]*\s*$",
    r"^\s*(شكرا|شكراً|تمام|تمم|اوكي|أوكي|ok|okay)\s*[!.،]*\s*$",
]
_SMALL_TALK_REPLY_AR = "أهلاً بيك في كيف! 👋 قولي بس عاوز تتعلم في إيه أو أي مجال يهمك (ذكاء اصطناعي، داتا، أمن سيبراني...) وأنا أرشحلك المسار الأنسب."
_SMALL_TALK_REPLY_EN = "Welcome to Kayfa! 👋 Tell me what you're interested in learning (AI, Data, Cybersecurity, etc.) and I'll point you to the right track."

def route_small_talk(text: str) -> Optional[str]:
    """يرجع رد ثابت فوري لو الرسالة كلام عابر بحت، أو None لو محتاجة الوكيل الفعلي."""
    stripped = (text or "").strip()
    if not stripped or len(stripped) > 40:
        return None
    for pattern in _SMALL_TALK_PATTERNS:
        if re.match(pattern, stripped, flags=re.IGNORECASE):
            has_arabic = bool(re.search(r"[\u0600-\u06FF]", stripped))
            return _SMALL_TALK_REPLY_AR if has_arabic else _SMALL_TALK_REPLY_EN
    return None


@st.cache_resource
def init_system(_db_handler):
    loader = DataLoader()
    docs = loader.load_text()
    courses = loader.load_json()
    rag = KayfaRAG(docs)
    rag.load_database()
    
    deps = AgentDeps(rag=rag, courses=courses, db_handler=_db_handler)
    return deps

st.set_page_config(page_title="مساعد مبيعات كيف", page_icon="🤖", layout="wide")

st.markdown("""
<style>
    .rtl-text { direction: rtl; text-align: right; font-family: sans-serif; }
    .stChatMessage { direction: rtl; text-align: right; font-family: sans-serif; }
    /* السطر ده بيخفي قائمة Streamlit الإجبارية اللي مكتوب فيها app و crm */
    [data-testid="stSidebarNav"] {display: none;}
</style>
""", unsafe_allow_html=True)

def require_login():
    if st.session_state.get("global_authenticated"):
        return True

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.image("kayfa_logo.png", use_container_width=True)
    st.markdown("<h2 class='rtl-text'>🔐 الدخول إلى مساعد مبيعات كيف</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<p style='margin-bottom:2px;'>Email</p>", unsafe_allow_html=True)
        email = st.text_input("Email", key="chat_login_email", label_visibility="collapsed")
        st.markdown("<p style='margin-bottom:2px;'>Password</p>", unsafe_allow_html=True)
        pw = st.text_input("Password", type="password", key="chat_login_pw", label_visibility="collapsed")
        if st.button("دخول", use_container_width=True):
            required_email = os.getenv("APP_EMAIL", "admin@kayfa.com")
            required_pw = os.getenv("APP_PASSWORD", "kayfa_admin")
            if email == required_email and pw == required_pw:
                
                # ------ هنا بنجرب نكلم مونجو ونشوف هيقول إيه ------
                try:
                    from database.mongodb import MongoDBHandler
                    _db = MongoDBHandler()
                    _db.log_login(email)
                except Exception as e:
                    st.error(f"⚠️ خطأ اتصال بمونجو أثناء اللوجين: {e}")
                # --------------------------------------------------

                st.session_state["global_authenticated"] = True
                st.session_state["user_email"] = email
                st.rerun()
            else:
                st.error("Email أو Password غير صحيح.")
    return False

def main():
    if not require_login():
        st.stop()

    db_handler = init_db()
    deps = init_system(db_handler)

    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid.uuid4())

    with st.sidebar:
        st.image("kayfa_logo.png", use_container_width=True)
        st.title("مرحباً بك في كيف")
        
        # قائمة تنقل عربية صممناها بإيدينا
        st.markdown("<br><b>القائمة الرئيسية:</b>", unsafe_allow_html=True)
        st.page_link("app.py", label="مساعد المبيعات", icon="💬")
        st.page_link("pages/crm.py", label="دخول الإدارة", icon="🔐")
        
        st.divider()
        
        if st.button("بدء محادثة جديدة 🔄", use_container_width=True):
            st.session_state["session_id"] = str(uuid.uuid4())
            st.session_state.messages = []
            st.session_state.pydantic_messages = []
            st.rerun()


    st.markdown("<h2 class='rtl-text'>🤖 مستشار المبيعات التفاعلي لـ كيف</h2>", unsafe_allow_html=True)
    st.divider()

    if "messages" not in st.session_state:
        st.session_state.messages = db_handler.get_chat_history(st.session_state.session_id)
        st.session_state.pydantic_messages = []

    for msg in st.session_state.messages:
        sender = msg.get("sender", "assistant")
        text = msg.get("text", "")
        role = "user" if sender == "user" else "assistant"
        emoji = "👤" if role == "user" else "🎓"
        with st.chat_message(role, avatar=emoji):
            render_bubble(text)

    if prompt := st.chat_input("اكتب استفسارك هنا..."):
        sid = st.session_state.session_id
        
        with st.chat_message("user", avatar="👤"):
            render_bubble(prompt)
            
        st.session_state.messages.append({"sender": "user", "text": prompt})
        try:
            db_handler.save_chat_turn(sid, "user", prompt)
        except Exception as e:
            st.error(f"⚠️ خطأ أثناء حفظ المحادثة: {e}")

        small_talk_reply = route_small_talk(prompt)
        if small_talk_reply is not None:
            # رد فوري بدون أي استدعاء لـ agent.run_sync - صفر توكنز API لهذه
            # الرسالة. ملحوظة: لا نضيفها لـ pydantic_messages (تاريخ الوكيل)
            # لأنها مفيش فيها سياق فعلي يحتاج الوكيل يتذكره في الردود الجاية.
            with st.chat_message("assistant", avatar="🎓"):
                render_bubble(small_talk_reply)
            st.session_state.messages.append({"sender": "assistant", "text": small_talk_reply})
            db_handler.save_chat_turn(sid, "assistant", small_talk_reply)
        else:
            with st.chat_message("assistant", avatar="🎓"):
                status = st.empty()
                status.info("جاري التفكير...")

                max_attempts = 3
                for attempt in range(1, max_attempts + 1):
                    try:
                        result = agent.run_sync(
                            prompt,
                            deps=deps,
                            message_history=st.session_state.pydantic_messages,
                            usage_limits=KAYFA_TURN_USAGE_LIMITS
                        )

                        response = result.output
                        st.session_state.pydantic_messages = result.all_messages()

                        status.empty()
                        render_bubble(response)
                        st.session_state.messages.append({"sender": "assistant", "text": response})
                        db_handler.save_chat_turn(sid, "assistant", response)
                        break

                    except UsageLimitExceeded:
                        # حد أقصى داخلي وضعناه نحن (وليس خطأ من Google) لمنع رسالة واحدة
                        # من استهلاك عدد كبير من الطلبات في حلقة استدلال طويلة. لا فائدة
                        # من إعادة المحاولة فوراً لأن السبب منطقي وليس عرضي.
                        status.empty()
                        st.warning("السؤال احتاج تفكيراً أعمق من المتوقع. ممكن تبسّط سؤالك أو تجزّئه لخطوتين؟")
                        break

                    except ModelHTTPError as e:
                        # رسالة 429 معناها "تجاوزت العدد المسموح بالدقيقة" عند مزوّد
                        # النموذج (Groq أو غيره) — إعادة المحاولة فوراً بعد ثواني قليلة
                        # عادةً لا تنجح لأن نافذة الحصة قد تكون دقيقة كاملة، فننتظر
                        # بفترة متصاعدة (backoff) ونعطي رسالة واضحة بدل التكرار بلا فائدة.
                        is_rate_limit = getattr(e, "status_code", None) == 429 or "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)

                        if attempt < max_attempts:
                            wait_seconds = 20 * attempt if is_rate_limit else 4 * attempt
                            status.warning(
                                f"تم الوصول للحد الأقصى من الطلبات مؤقتاً، جاري إعادة المحاولة بعد {wait_seconds} ثانية..."
                                if is_rate_limit else "ضغط على السيرفر، جاري إعادة المحاولة..."
                            )
                            time.sleep(wait_seconds)
                        else:
                            status.empty()
                            if is_rate_limit:
                                st.error("تم الوصول للحد الأقصى من الطلبات المسموح بها حالياً (Rate Limit). جرّب بعد دقيقة من فضلك 🙏")
                            else:
                                st.error("السيرفر مشغول حالياً، يرجى المحاولة لاحقاً.")
                    except Exception as e:
                        status.empty()
                        st.error(f"خطأ: {e}")
                        break

if __name__ == "__main__":
    main()