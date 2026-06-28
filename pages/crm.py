import os
from pathlib import Path
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv
from database.mongodb import MongoDBHandler

# ── import shared styles (CSS + logo + sidebar) ───────────────
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.styles import inject_css, render_sidebar, LOGO_SRC

load_dotenv()

# ── Page config ───────────────────────────────────────────────
st.set_page_config(
    page_title="Kayfa CRM Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_css()  


# ── DB ────────────────────────────────────────────────────────
@st.cache_resource
def init_db():
    return MongoDBHandler()

db = init_db()


# ── Auth guard: MUST be logged in + admin role ────────────────
if not st.session_state.get("global_authenticated"):
    st.warning("يرجى تسجيل الدخول أولاً من الصفحة الرئيسية.")
    st.page_link("app.py", label="→ الذهاب لصفحة الدخول", icon="🔐")
    st.stop()

if st.session_state.get("role") != "admin":
    st.error("⛔ ليس لديك صلاحية الوصول إلى لوحة الإدارة.")
    st.page_link("app.py", label="→ العودة للمساعد", icon="💬")
    st.stop()


# ── Sidebar (identical to app.py) ─────────────────────────────
render_sidebar(active="crm")


# ── Load tickets ──────────────────────────────────────────────
try:
    all_tickets = db.get_all_leads() or []
except Exception as e:
    st.error(f"خطأ في تحميل البيانات: {e}")
    all_tickets = []


# ── Helpers ───────────────────────────────────────────────────
def _temp(t: dict) -> str:
    return str(t.get("lead_temperature", t.get("temperature", "warm"))).lower()

def _dot(temp: str) -> str:
    return {"hot": "🔴", "cold": "🔵", "warm": "🟡"}.get(temp, "🟡")
def render_ticket_card(ticket):
    prods = ticket.get('interested_products', '—')
    if isinstance(prods, list):
        prods = "، ".join(prods)
        
    temp_val = _temp(ticket)
    temp_color = "#ff4b4b" if temp_val == 'hot' else "#ffa421" if temp_val == 'warm' else "#1c83e1"
    temp_text = temp_val.upper()

    card_html = f"""
<div style="direction: rtl; text-align: right; background-color: #1e1e27; border: 1px solid #333; border-radius: 10px; padding: 20px; margin-bottom: 20px; font-family: sans-serif; color: #eee;">
    <div style="display: flex; justify-content: space-between; border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 15px;">
        <span style="color: #aaa; font-size: 14px; background: #2b2b36; padding: 3px 8px; border-radius: 5px;">ID: {ticket.get('_id', '')}</span>
        <span style="color: {temp_color}; font-weight: bold;">عميل محتمل • {temp_text}</span>
    </div>
    <table style="width: 100%; border-collapse: collapse;">
        <tr style="border-bottom: 1px solid #333;">
            <td style="padding: 10px; color: #4DA8DA; font-weight: bold; width: 25%;">الاسم</td>
            <td style="padding: 10px;">{ticket.get('name', '—')}</td>
        </tr>
        <tr style="border-bottom: 1px solid #333;">
            <td style="padding: 10px; color: #4DA8DA; font-weight: bold;">البريد الإلكتروني</td>
            <td style="padding: 10px; direction: ltr; text-align: right;">{ticket.get('email', '—')}</td>
        </tr>
        <tr style="border-bottom: 1px solid #333;">
            <td style="padding: 10px; color: #4DA8DA; font-weight: bold;">رقم التواصل</td>
            <td style="padding: 10px; direction: ltr; text-align: right;">{ticket.get('phone', '—')}</td>
        </tr>
        <tr style="border-bottom: 1px solid #333;">
            <td style="padding: 10px; color: #4DA8DA; font-weight: bold;">المدينة</td>
            <td style="padding: 10px;">{ticket.get('location', ticket.get('city', '—'))}</td>
        </tr>
        <tr style="border-bottom: 1px solid #333;">
            <td style="padding: 10px; color: #4DA8DA; font-weight: bold;">اللغة / اللهجة</td>
            <td style="padding: 10px;">{ticket.get('language_dialect', '—')}</td>
        </tr>
        <tr style="border-bottom: 1px solid #333;">
            <td style="padding: 10px; color: #4DA8DA; font-weight: bold;">المنتجات محل الاهتمام</td>
            <td style="padding: 10px; direction: ltr; text-align: right;">{prods}</td>
        </tr>
        <tr style="border-bottom: 1px solid #333;">
            <td style="padding: 10px; color: #4DA8DA; font-weight: bold;">الهدف</td>
            <td style="padding: 10px;">{ticket.get('goal', '—')}</td>
        </tr>
        <tr style="border-bottom: 1px solid #333;">
            <td style="padding: 10px; color: #4DA8DA; font-weight: bold;">المستوى الحالي</td>
            <td style="padding: 10px;">{ticket.get('current_level', '—')}</td>
        </tr>
        <tr style="border-bottom: 1px solid #333;">
            <td style="padding: 10px; color: #4DA8DA; font-weight: bold;">الاعتراضات</td>
            <td style="padding: 10px;">{ticket.get('objections', '—')}</td>
        </tr>
        <tr style="border-bottom: 1px solid #333;">
            <td style="padding: 10px; color: #4DA8DA; font-weight: bold;">ملخص المحادثة</td>
            <td style="padding: 10px; line-height: 1.6;">{ticket.get('conversation_summary', '—')}</td>
        </tr>
        <tr style="border-bottom: 1px solid #333;">
            <td style="padding: 10px; color: #4DA8DA; font-weight: bold;">الإجراء التالي</td>
            <td style="padding: 10px;">{ticket.get('next_action', '—')}</td>
        </tr>
        <tr>
            <td style="padding: 10px; color: #4DA8DA; font-weight: bold;">التاريخ</td>
            <td style="padding: 10px; direction: ltr; text-align: right;">{str(ticket.get('timestamp', '—'))[:16]}</td>
        </tr>
    </table>
</div>
"""
    st.markdown(card_html, unsafe_allow_html=True)
    
    raw_chat = ticket.get('conversation_transcript', 'لا توجد محادثة مسجلة.')
    formatted_chat = raw_chat.replace(
        "العميل:", "<br><br><span style='color:#ff4b4b; font-weight:bold; font-size:16px;'>👤 العميل:</span><br>"
    ).replace(
        "الوكيل:", "<br><br><span style='color:#00d4ff; font-weight:bold; font-size:16px;'>🤖 الوكيل:</span><br>"
    )

    with st.expander("💬 عرض المحادثة الكاملة"):
        chat_html = f"""
<div style='direction: rtl; text-align: right; line-height: 1.8; font-family: sans-serif; background-color: #1e1e27; padding: 20px; border-radius: 8px; border: 1px solid #333; color: #eee; margin-top: -15px;'>
{formatted_chat}
</div>
"""
        st.markdown(chat_html, unsafe_allow_html=True)
        
# ── Page title ────────────────────────────────────────────────
st.markdown(
    "<h2 style='color:#fff; margin-bottom:18px; direction: rtl; text-align: right;'>📊 لوحة مراقبة تذاكر المبيعات</h2>",
    unsafe_allow_html=True,
)

# ── KPI row ───────────────────────────────────────────────────
total = len(all_tickets)
hot   = sum(1 for t in all_tickets if _temp(t) == "hot")
warm  = sum(1 for t in all_tickets if _temp(t) == "warm")
cold  = sum(1 for t in all_tickets if _temp(t) == "cold")

k1, k2, k3, k4 = st.columns(4)
k1.metric("إجمالي التذاكر 🗂️", total)
k2.metric("Hot 🔥", hot)
k3.metric("Warm ⭐", warm)
k4.metric("Cold ❄️", cold)

st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

if not all_tickets:
    st.info("لا توجد تذاكر مسجلة حالياً.")
    st.stop()

# ── Filter dropdown ───────────────────────────────────────────
fc, _ = st.columns([1, 3])
with fc:
    filt = st.selectbox(
        "تصفية حسب درجة الحرارة",
        ["الكل", "Hot 🔥", "Warm ⭐", "Cold ❄️"],
        label_visibility="collapsed",
    )

filt_map = {"Hot 🔥": "hot", "Warm ⭐": "warm", "Cold ❄️": "cold"}
tickets  = ([t for t in all_tickets if _temp(t) == filt_map[filt]]
            if filt != "الكل" else all_tickets)

st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

# ── Two-column: list (left) + detail/edit (right) ─────────────
if "sel" not in st.session_state:
    st.session_state["sel"] = 0
if "edit" not in st.session_state:
    st.session_state["edit"] = False

list_col, detail_col = st.columns([1, 1.7], gap="large")

# ── LEFT: ticket list (with scroll container) ─────────────────
with list_col:
    st.markdown(
        f"<p style='color:#777;font-size:.82rem;margin-bottom:10px;'>"
        f"{len(tickets)} تذكرة</p>",
        unsafe_allow_html=True,
    )
    with st.container(height=600):
        for i, t in enumerate(tickets):
            temp = _temp(t)
            name = t.get("name", "غير محدد")
            ts   = str(t.get("timestamp", ""))[:16]
            prod = str(t.get("interested_products", ""))[:38]

            if st.button(f"{_dot(temp)}  {name}", key=f"tb_{i}", use_container_width=True):
                st.session_state["sel"]  = i
                st.session_state["edit"] = False
                st.rerun()

            st.markdown(
                f"<p style='font-size:.73rem;color:#555;margin:-10px 0 8px 6px;'>"
                f"{ts}  ·  {prod}</p>",
                unsafe_allow_html=True,
            )

# ── RIGHT: detail + edit ──────────────────────────────────────
with detail_col:
    if not tickets:
        st.info("اختر تذكرة من القائمة")
        st.stop()

    idx = min(st.session_state["sel"], len(tickets) - 1)
    t   = tickets[idx]
    tmp = _temp(t)

    # ── VIEW mode ─────────────────────────────────────────────
    if not st.session_state["edit"]:
        render_ticket_card(t)

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        if st.button("✏️ تعديل التذكرة", key="edit_btn"):
            st.session_state["edit"] = True
            st.rerun()
            
    # ── EDIT mode ─────────────────────────────────────────────
    else:
        st.markdown("<h4 style='color:#fff;margin-bottom:14px;'>✏️ تعديل التذكرة</h4>",
                    unsafe_allow_html=True)
        with st.form("ef"):
            e_name  = st.text_input("الاسم",         value=t.get("name",""))
            e_phone = st.text_input("الهاتف",        value=t.get("phone",""))
            e_email = st.text_input("البريد",        value=t.get("email","") or "")
            e_loc   = st.text_input("المدينة",       value=t.get("location", t.get("city","")))
            
            # --- Edit here: convert the list to plain text ---
            raw_p = t.get("interested_products", "")
            clean_p = "، ".join(raw_p) if isinstance(raw_p, list) else str(raw_p)
            e_prod  = st.text_input("المنتجات",      value=clean_p)
            # ------------------------------------------
            
            e_goal  = st.text_area ("الهدف",         value=t.get("goal",""), height=80)
            temps   = ["Hot","Warm","Cold"]
            cur_t   = tmp.capitalize() if tmp.capitalize() in temps else "Warm"
            e_temp  = st.selectbox("درجة الحرارة",   temps, index=temps.index(cur_t))
            e_note  = st.text_area ("الإجراء التالي", value=t.get("next_action",""), height=80)

            s1, s2 = st.columns(2)
            save   = s1.form_submit_button("💾 حفظ", use_container_width=True)
            cancel = s2.form_submit_button("❌ إلغاء", use_container_width=True)

            if save:
                updates = {k: v for k, v in {
                    "name": e_name, "phone": e_phone, "email": e_email,
                    "location": e_loc, "interested_products": e_prod,
                    "goal": e_goal, "lead_temperature": e_temp,
                    "next_action": e_note,
                }.items() if v}
                try:
                    doc_id = t.get("_id")
                    if doc_id:
                        db.update_ticket(doc_id, updates)
                        st.success("✅ تم الحفظ بنجاح!")
                    else:
                        st.warning("لم يتم العثور على معرف التذكرة.")
                except Exception as ex:
                    st.error(f"خطأ: {ex}")
                st.session_state["edit"] = False
                st.rerun()

            if cancel:
                st.session_state["edit"] = False
                st.rerun()