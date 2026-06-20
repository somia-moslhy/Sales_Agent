import os
import time
import streamlit as st
from dotenv import load_dotenv
from database.mongodb import MongoDBHandler

load_dotenv()

@st.cache_resource
def init_db():
    return MongoDBHandler()

st.set_page_config(page_title="لوحة إدارة كيف", page_icon="📊", layout="wide")

st.markdown("""
<style>
    .rtl-text { direction: rtl; text-align: right; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    .main-header { text-align: center; padding: 2rem; background: linear-gradient(90deg, #1e293b 0%, #334155 100%); color: white; border-radius: 12px; margin-bottom: 2rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    div[data-testid="stMetric"] { background-color: #ffffff; padding: 15px 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; border-right: 4px solid #3b82f6; direction: rtl; }
    div[data-testid="stMetricValue"] { font-size: 2rem !important; color: #0f172a; }
    .badge-hot { background-color: #fee2e2; color: #ef4444; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 0.9rem; }
    .badge-warm { background-color: #fef3c7; color: #d97706; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 0.9rem; }
    .badge-cold { background-color: #e0f2fe; color: #0284c7; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 0.9rem; }
    /* إخفاء القائمة الإجبارية هنا كمان */
    [data-testid="stSidebarNav"] {display: none;}
</style>
""", unsafe_allow_html=True)

db_handler = init_db()

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state.get("global_authenticated"):
    st.markdown("<div class='main-header'><h1>بوابة الإدارة — كيف CRM 🔐</h1></div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.image("kayfa_logo.png", use_container_width=True)
        st.subheader("سجل دخولك للوصول إلى بيانات العملاء")
        email = st.text_input("البريد الإلكتروني", placeholder="admin@kayfa.io")
        password = st.text_input("كلمة المرور", type="password")
        
        if st.button("تسجيل الدخول", use_container_width=True):
            required_pw = os.getenv("APP_PASSWORD", "kayfa_admin")
            required_email = os.getenv("APP_EMAIL", "admin@kayfa.com")
            if password == required_pw and email == required_email:
                try:
                    db_handler.log_login(email)
                except:
                    pass
                st.session_state["global_authenticated"] = True
                st.session_state["user_email"] = email
                st.success("تم تسجيل الدخول بنجاح!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("البريد الإلكتروني أو كلمة المرور غير صحيحة.")
    st.stop()

with st.sidebar:
    st.image("kayfa_logo.png", use_container_width=True)
    st.title("إدارة كيف")
    st.write(f"المستخدم: **{st.session_state['user_email']}**")
    
    st.markdown("<br><b>القائمة الرئيسية:</b>", unsafe_allow_html=True)
    st.page_link("app.py", label="مساعد المبيعات", icon="💬")
    st.page_link("pages/crm.py", label="لوحة الإدارة", icon="📊")
    
    st.divider()
    if st.button("تسجيل الخروج 🚪", use_container_width=True):
        st.session_state["authenticated"] = False
        st.rerun()

st.markdown("<h2 class='rtl-text' style='color: #1e293b; margin-bottom: 20px;'>📊 لوحة مراقبة تذاكر المبيعات</h2>", unsafe_allow_html=True)

try:
    tickets = db_handler.get_all_leads()
    if not tickets:
        st.info("لا توجد تذاكر مسجلة حالياً.")
    else:
        total = len(tickets)
        hot = sum(1 for l in tickets if str(l.get("lead_temperature", l.get("temperature", ""))).lower() == "hot")
        warm = sum(1 for l in tickets if str(l.get("lead_temperature", l.get("temperature", ""))).lower() == "warm")
        cold = sum(1 for l in tickets if str(l.get("lead_temperature", l.get("temperature", ""))).lower() == "cold")
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("إجمالي التذاكر 🗂️", total)
        c2.metric("عملاء Hot 🔥", hot)
        c3.metric("عملاء Warm ⭐", warm)
        c4.metric("عملاء Cold ❄️", cold)
        
        st.write("---")
        
        col_chart, col_filter = st.columns([2, 1])
        
        with col_filter:
            st.markdown("<h4 class='rtl-text'>🔍 تصفية العملاء</h4>", unsafe_allow_html=True)
            filter_option = st.selectbox("اختر حالة العميل:", ["عرض الكل", "Hot 🔥", "Warm ⭐", "Cold ❄️"])
            
        with col_chart:
            chart_data = {"حالة التذاكر": {"Hot": hot, "Warm": warm, "Cold": cold}}
            st.bar_chart(chart_data, height=180, color="#3b82f6")
            
        st.write("---")

        filtered_tickets = tickets
        if filter_option != "عرض الكل":
            target_temp = "hot" if "Hot" in filter_option else "warm" if "Warm" in filter_option else "cold"
            filtered_tickets = [t for t in tickets if str(t.get("lead_temperature", t.get("temperature", ""))).lower() == target_temp]

        st.markdown(f"<h4 class='rtl-text'>📋 قائمة التذاكر ({len(filtered_tickets)})</h4>", unsafe_allow_html=True)
        
        for lead in filtered_tickets:
            temp = str(lead.get("lead_temperature", lead.get("temperature", "warm"))).lower()
            
            if temp == "hot":
                badge_html = "<span class='badge-hot'>🔥 ساخن جداً (Hot)</span>"
                icon = "🔴"
            elif temp == "cold":
                badge_html = "<span class='badge-cold'>❄️ بارد (Cold)</span>"
                icon = "🔵"
            else:
                badge_html = "<span class='badge-warm'>⭐ مهتم (Warm)</span>"
                icon = "🟡"
            
            name = lead.get("name", "غير محدد")
            products = lead.get("interested_products", lead.get("products", "غير محدد"))
            
            with st.expander(f"{icon} {name} | المهتم بـ: {products}"):
                st.markdown(f"<div class='rtl-text' style='margin-bottom: 20px;'>{badge_html} &nbsp;&nbsp;|&nbsp;&nbsp; 🕒 {lead.get('timestamp', '-')}</div>", unsafe_allow_html=True)
                
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown(f"<div class='rtl-text'><b>👤 الاسم:</b> {name}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='rtl-text'><b>📱 رقم الهاتف:</b> {lead.get('phone', '-')}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='rtl-text'><b>📍 المدينة:</b> {lead.get('location', lead.get('city', '-'))}</div>", unsafe_allow_html=True)
                with col_b:
                    st.markdown(f"<div class='rtl-text'><b>🎯 المنتجات:</b> {products}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='rtl-text'><b>📈 المستوى:</b> {lead.get('current_level', lead.get('level', '-'))}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='rtl-text'><b>🚀 الهدف:</b> {lead.get('goal', '-')}</div>", unsafe_allow_html=True)
                
                st.divider()
                st.info(f"📝 **ملخص المحادثة:**\n\n{lead.get('conversation_summary', lead.get('summary', '-'))}")
                st.success(f"⚡ **الإجراء التالي:**\n\n{lead.get('next_action', 'التواصل مع العميل وتأكيد الحجز.')}")

except Exception as e:
    st.error(f"حدث خطأ أثناء تحميل البيانات: {e}")