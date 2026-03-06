import streamlit as st
import pandas as pd
from google.cloud import firestore
from datetime import datetime
import json
import calendar

# إعداد الصفحة
st.set_page_config(page_title="إقامة 28 - Bloc B", page_icon="🏢")

# --- الاتصال بـ Firebase ---
if 'db' not in st.session_state:
    try:
        st.session_state.db = firestore.Client.from_service_account_json("firebase_key.json")
    except Exception as e:
        st.error("خطأ في الاتصال بقاعدة البيانات")
        st.stop()

db = st.session_state.db

# --- دالة جلب البيانات ---
@st.cache_data(ttl=5)
def load_portal_data():
    hab_docs = db.collection("habitants").stream()
    df_hab = pd.DataFrame([d.to_dict() for d in hab_docs])
    cont_docs = (
        db.collection("cotisations")
        .order_by("Timestamp", direction=firestore.Query.DESCENDING)
        .stream()
    )
    df_cont = pd.DataFrame([d.to_dict() for d in cont_docs])
    if "Appart" in df_hab.columns:
        df_hab["Appart"] = pd.to_numeric(df_hab["Appart"], errors="coerce").astype("Int64")
    if "Appart" in df_cont.columns:
        df_cont["Appart"] = pd.to_numeric(df_cont["Appart"], errors="coerce").astype("Int64")
    if "Montant" in df_cont.columns:
        df_cont["Montant"] = pd.to_numeric(df_cont["Montant"], errors="coerce").fillna(0)
    return df_hab, df_cont

df_hab, df_cont = load_portal_data()

# --- دالة حساب آخر يوم في الشهر المسوى ---
def get_last_day_paid(total_amount):
    if total_amount <= 0:
        return None
    # حساب عدد الأشهر (كل 1000 دج تغطي شهراً)
    months_covered = int(total_amount // 1000)
    if months_covered == 0:
        return None
    
    # حساب السنة والشهر (نبدأ من جانفي 2026)
    year = 2026 + (months_covered - 1) // 12
    month = (months_covered - 1) % 12 + 1
    
    # الحصول على آخر يوم في ذلك الشهر
    last_day = calendar.monthrange(year, month)[1]
    return f"{last_day:02d}/{month:02d}/{year}"

st.title("🏢 بوابة سكان إقامة 28")

if not df_hab.empty:
    floors = {
        "الطابق الأول": [61, 62, 63, 64],
        "الطابق الثاني": [23, 24, 65, 66],
        "الطابق الثالث": [25, 26, 27, 28],
        "الطابق الرابع": [29, 30, 31, 32],
        "الطابق الخامس": [33, 34, 35, 36],
        "الطابق السادس": [37, 38, 39, 40],
        "الطابق السابع": [41, 42, 43, 44],
    }

    display_options = ["-- اختر رقم الشقة --"]
    for floor_name, apts in floors.items():
        for a in apts:
            display_options.append(f"{floor_name} - شقة رقم {a}")

    choice = st.selectbox("🏠 الرجاء تحديد شقتك:", display_options)

    if choice != "-- اختر رقم الشقة --":
        selected_apt = int(choice.split(" ")[-1])
        
        resident_info = df_hab[df_hab['Appart'] == selected_apt]
        if not resident_info.empty:
            st.info(f"👤 الساكن: **{resident_info.iloc[0]['Nom']}**")

        apt_payments = df_cont[df_cont['Appart'] == selected_apt] if not df_cont.empty else pd.DataFrame()
        total_paid = apt_payments['Montant'].sum() if not apt_payments.empty else 0
        
        # حساب آخر تاريخ مغطى
        expiry_date = get_last_day_paid(total_paid)
        
        current_month = datetime.now().month
        required_total = current_month * 1000
        dette = max(0, required_total - total_paid)

        col1, col2 = st.columns(2)
        col1.metric("إجمالي المدفوعات", f"{total_paid:,.0f} دج")
        
        if expiry_date:
            st.success(f"✅ الوضعية مُسواة إلى غاية: **{expiry_date}**")
        
        if dette > 0:
            st.error(f"⚠️ الدين المتبقي لليوم: {dette:,.0f} دج")
        else:
            if not expiry_date:
                 st.warning("لم يتم تسجيل أي مبالغ بعد.")

        st.divider()
        st.subheader("📋 سجل آخر الدفعات:")
        if not apt_payments.empty:
            display_df = apt_payments[['Date', 'Montant']].sort_values('Date', ascending=False)
            st.table(display_df.head(5))
    else:
        st.write("الرجاء اختيار شقتك من القائمة أعلاه.")
else:
    st.warning("جاري تحميل البيانات...")

