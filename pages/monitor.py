import os
from pathlib import Path
from datetime import datetime, timezone

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
    page_title="Kayfa — Monitoring & Cost",
    page_icon="📈",
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
    st.error("⛔ ليس لديك صلاحية الوصول إلى لوحة المراقبة.")
    st.page_link("app.py", label="→ العودة للمساعد", icon="💬")
    st.stop()


# ── Sidebar (identical to app.py / crm.py) ────────────────────
render_sidebar(active="monitor")


# ── Helpers ───────────────────────────────────────────────────
def _fmt_cost(v: float) -> str:
    """تنسيق التكلفة بدقة كافية لأرقام صغيرة جداً (جزء من السنت)."""
    if v == 0:
        return "$0.00"
    if v < 0.01:
        return f"${v:.6f}"
    return f"${v:,.4f}"


def _fmt_ts(v) -> str:
    """يعرض datetime object بصيغة نظيفة HH:MM:SS، أو يرجّع القيمة كما هي لو نص قديم."""
    if isinstance(v, datetime):
        return v.strftime("%H:%M:%S")
    return str(v or "")


def _parse_ts(v):
    """
    تحويل timestamp (datetime object أو نص قديم) لـ datetime موحَّد (مع
    timezone). تُستخدَم فقط لترتيب استدعاءات النموذج ضمن نفس turn_id (مثلاً:
    استدعاء الأداة قبل صياغة الرد النهائي) - وليست أساس الربط بين الرسائل
    والسجلات (ذلك يتم عبر turn_id الصريح، انظر تعليق logs_by_turn_id أدناه).
    """
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, str):
        try:
            return datetime.strptime(v, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def _user_label(user_id: str) -> str:
    """يحوّل user_id (ObjectId كنص) لإيميل مفهوم لو متاح، وإلا يرجّع الـ id نفسه."""
    if not user_id or user_id == "anonymous":
        return "زائر غير مسجَّل (anonymous)"
    try:
        user = db.users.find_one({"_id": __import__("bson").ObjectId(user_id)})
        if user:
            return user.get("email", user_id)
    except Exception:
        pass
    return user_id


st.markdown(
    "<h2 style='color:#fff; margin-bottom:18px; direction: rtl; text-align: right;'>"
    "📈 لوحة المراقبة والتكلفة</h2>",
    unsafe_allow_html=True,
)

tab_cost, tab_trace = st.tabs(["💰 Cost Monitor", "🧭 Behaviour & Response Trace"])


# ════════════════════════════════════════════════════════════════
# TAB 1 — Cost Monitor
# ════════════════════════════════════════════════════════════════
with tab_cost:
    try:
        users_summary = db.get_all_users_cost_summary()
    except Exception as e:
        st.error(f"خطأ في تحميل بيانات التكلفة: {e}")
        users_summary = []

    total_cost = sum(u["total_cost"] for u in users_summary)
    total_calls = sum(u["model_calls"] for u in users_summary)
    total_users = len(users_summary)

    # ── 1) Total project cost ──────────────────────────────
    c1, c2, c3 = st.columns(3)
    c1.metric("إجمالي تكلفة المشروع 💵", _fmt_cost(total_cost))
    c2.metric("إجمالي استدعاءات النماذج 🔁", f"{total_calls:,}")
    c3.metric("عدد المستخدمين الذين لهم استخدام 👤", total_users)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    if not users_summary:
        st.info("لا توجد بيانات استخدام مسجَّلة بعد. تحدُث usage_logs أول استخدام فعلي للوكيل.")
    else:
        # ── 2) Aggregated cost table per user ───────────────
        st.markdown(
            "<p style='color:#bbb; direction:rtl; text-align:right; margin-bottom:6px;'>"
            "التكلفة المجمَّعة لكل مستخدم — اختر مستخدماً لعرض تفاصيل محادثاته:</p>",
            unsafe_allow_html=True,
        )

        table_rows = [
            {
                "المستخدم": _user_label(u["user_id"]),
                "user_id_raw": u["user_id"],
                "عدد المحادثات": u["conversation_count"],
                "عدد استدعاءات النموذج": u["model_calls"],
                "إجمالي التكلفة ($)": round(u["total_cost"], 6),
            }
            for u in users_summary
        ]

        st.dataframe(
            [{k: v for k, v in row.items() if k != "user_id_raw"} for row in table_rows],
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

        # ── 3) Drill-down: cost per conversation for a selected user ────
        user_options = {row["المستخدم"]: row["user_id_raw"] for row in table_rows}
        selected_label = st.selectbox(
            "🔎 عرض تفاصيل التكلفة لكل محادثة لمستخدم محدَّد",
            list(user_options.keys()),
        )

        if selected_label:
            selected_user_id = user_options[selected_label]
            try:
                conv_breakdown = db.get_conversations_for_user(selected_user_id)
            except Exception as e:
                st.error(f"خطأ في تحميل تفاصيل المحادثات: {e}")
                conv_breakdown = []

            if not conv_breakdown:
                st.info("لا توجد محادثات مسجَّلة لهذا المستخدم.")
            else:
                st.markdown(
                    f"<p style='color:#bbb; direction:rtl; text-align:right;'>"
                    f"محادثات <b>{selected_label}</b>:</p>",
                    unsafe_allow_html=True,
                )
                conv_table = [
                    {
                        "Session ID": c["conversation_id"],
                        "عدد الاستدعاءات": c["model_calls"],
                        "التكلفة ($)": round(c["total_cost"], 6),
                        "آخر نشاط": str(c.get("last_timestamp", "—")),
                    }
                    for c in conv_breakdown
                ]
                st.dataframe(conv_table, use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════════════════════
# TAB 2 — Behaviour & Response Trace
# ════════════════════════════════════════════════════════════════
with tab_trace:
    try:
        conversation_ids = db.get_all_conversation_ids()
    except Exception as e:
        st.error(f"خطأ في تحميل قائمة المحادثات: {e}")
        conversation_ids = []

    if not conversation_ids:
        st.info("لا توجد محادثات بها استدعاءات نموذج مسجَّلة بعد.")
    else:
        selected_sid = st.selectbox(
            "🗂️ اختر محادثة (Session ID) لعرض رحلتها الكاملة:",
            conversation_ids,
        )

        if selected_sid:
            try:
                chat_turns = db.get_chat_history(selected_sid)
                usage_logs = db.get_usage_logs_for_conversation(selected_sid)
            except Exception as e:
                st.error(f"خطأ في تحميل تفاصيل المحادثة: {e}")
                chat_turns, usage_logs = [], []

            # Matching assistant messages to their corresponding usage_logs
            # entries is done via an explicit `turn_id` (a deterministic
            # sequential integer computed in `app.py`), not by comparing
            # timestamps. This is 100% reliable: `turn_id` prevents collisions
            # and race conditions that can occur when using `datetime.now()`
            # which might return identical values for very closely timed calls.
            logs_by_turn_id: dict[int, list] = {}
            for log in usage_logs:
                logs_by_turn_id.setdefault(log.get("turn_id"), []).append(log)
            for tid in logs_by_turn_id:
                logs_by_turn_id[tid].sort(key=lambda l: _parse_ts(l.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc))

            st.markdown(
                f"<p style='color:#bbb; direction:rtl; text-align:right;'>"
                f"عدد الرسائل: {len(chat_turns)} — عدد استدعاءات النموذج: {len(usage_logs)}</p>",
                unsafe_allow_html=True,
            )
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

            for turn in chat_turns:
                sender = turn.get("sender")
                text = turn.get("text", "")

                if sender == "user":
                    st.markdown(
                        f"<div class='panel-card' style='border-right:4px solid #4a7acf;'>"
                        f"<div class='panel-title'>👤 USER PROMPT — {_fmt_ts(turn.get('timestamp',''))}</div>"
                        f"<div style='direction:rtl; text-align:right; color:#e8e8e8;'>{text}</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    # The tool calls and results (including RAG sources) related
                    # to this final response — matched precisely via `turn_id`,
                    # not by guessing based on timestamps.
                    related_logs = logs_by_turn_id.get(turn.get("turn_id"), [])

                    for log in related_logs:
                        for tc in log.get("tool_calls", []):
                            with st.expander(
                                f"🛠️ Tool Call: {tc.get('tool_name')}  ·  "
                                f"model={log.get('model_name')}  ·  "
                                f"{_fmt_cost(log.get('cost', {}).get('total_cost', 0))}"
                            ):
                                st.markdown("**Args:**")
                                st.json(tc.get("args", {}))
                                st.markdown("**Result (incl. RAG sources):**")
                                result_content = tc.get("result")
                                if isinstance(result_content, str):
                                    st.text(result_content)
                                else:
                                    st.json(result_content)

                        st.caption(
                            f"📊 model_call: {log.get('model_name')} | "
                            f"in={log.get('input_tokens')} out={log.get('output_tokens')} | "
                            f"latency={log.get('latency_seconds')}s | "
                            f"cost={_fmt_cost(log.get('cost', {}).get('total_cost', 0))}"
                        )

                    st.markdown(
                        f"<div class='panel-card' style='border-right:4px solid #34d399;'>"
                        f"<div class='panel-title'>🎓 FINAL RESPONSE — {_fmt_ts(turn.get('timestamp',''))}</div>"
                        f"<div style='direction:rtl; text-align:right; color:#e8e8e8;'>{text}</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
