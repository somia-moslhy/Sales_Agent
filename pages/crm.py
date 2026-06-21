import os
from pathlib import Path

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
inject_css()   # ← exact same CSS as app.py


# ── DB ────────────────────────────────────────────────────────
@st.cache_resource
def init_db():
    return MongoDBHandler()

db = init_db()


# ── Auth guard: MUST be logged in + admin role ────────────────
# session_state is shared across pages in the same browser session,
# so if the user logged in on app.py the keys are already present here.
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

def _badge(temp: str) -> str:
    cls = {"hot": "badge-hot", "cold": "badge-cold", "warm": "badge-warm"}.get(temp, "badge-warm")
    emoji = {"hot": "🔥", "cold": "❄️", "warm": "⭐"}.get(temp, "⭐")
    lbl   = {"hot": "Hot", "cold": "Cold", "warm": "Warm"}.get(temp, "Warm")
    return f"<span class='{cls}'>{emoji} {lbl}</span>"

def _dot(temp: str) -> str:
    return {"hot": "🔴", "cold": "🔵", "warm": "🟡"}.get(temp, "🟡")


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

# ── LEFT: ticket list ─────────────────────────────────────────
with list_col:
    st.markdown(
        f"<p style='color:#777;font-size:.82rem;margin-bottom:10px;'>"
        f"{len(tickets)} تذكرة</p>",
        unsafe_allow_html=True,
    )
    for i, t in enumerate(tickets):
        temp = _temp(t)
        name = t.get("name", "غير محدد")
        ts   = str(t.get("timestamp", ""))[:16]
        prod = str(t.get("interested_products", ""))[:38]

        if st.button(f"{_dot(temp)}  {name}", key=f"tb_{i}",
                     use_container_width=True):
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
        name = t.get("name", "—")
        st.markdown(
            # لاحظي الـ direction: rtl وتكبير الـ font-size لـ 1.7rem
            f"<div style='display:flex;align-items:center;gap:14px;margin-bottom:24px; direction:rtl; justify-content:flex-start;'>"
            f"<span style='font-size:1.7rem;font-weight:800;color:#fff;'>{name}</span>"
            f"{_badge(tmp)}</div>",
            unsafe_allow_html=True,
        )

        fields = [
            ("📱 الهاتف / واتساب",  t.get("phone", "—")),
            ("📧 البريد",           t.get("email") or "—"),
            ("📍 المدينة",          t.get("location", t.get("city", "—"))),
            ("🗣️ اللهجة",           t.get("language_dialect", "—")),
            ("🎯 المنتجات",         str(t.get("interested_products", "—"))),
            ("📈 المستوى",          t.get("current_level", t.get("level", "—"))),
            ("🚀 الهدف",            t.get("goal", "—")),
            ("⚠️ الاعتراضات",       t.get("objections") or "—"),
            ("🕒 التاريخ",          str(t.get("timestamp", "—"))[:16]),
        ]
        rows = "".join(
            f'<div class="detail-row">'
            f'<span class="dl">{lbl}</span>'
            f'<span class="dv">{val}</span>'
            f'</div>'
            for lbl, val in fields
        )
        st.markdown(f'<div class="detail-card">{rows}</div>', unsafe_allow_html=True)

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        # ستلاحظين أن حجم الخط العربي هنا أصبح كبيراً ورائعاً بفضل الـ CSS الجديد
        st.info(f"📝 **ملخص المحادثة:**\n\n{t.get('conversation_summary', t.get('summary','—'))}")
        st.success(f"⚡ **الإجراء التالي:**\n\n{t.get('next_action','التواصل مع العميل.')}")

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
            e_prod  = st.text_input("المنتجات",      value=str(t.get("interested_products","")))
            e_goal  = st.text_area ("الهدف",         value=t.get("goal",""), height=80)
            temps   = ["Hot","Warm","Cold"]
            cur_t   = tmp.capitalize() if tmp.capitalize() in temps else "Warm"
            e_temp  = st.selectbox("درجة الحرارة",   temps,
                                    index=temps.index(cur_t))
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
