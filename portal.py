import streamlit as st
import pandas as pd
from google.cloud import firestore
from datetime import datetime
import calendar
import json

# الاتصال الآمن بـ Firebase
if 'db' not in st.session_state:
    try:
        # قراءة المفتاح من Secrets
        key_dict = json.loads(st.secrets["firebase_key"])
        st.session_state.db = firestore.Client.from_service_account_info(key_dict)
    except Exception as e:
        st.error(f"❌ فشل الاتصال: {e}")
        st.stop()

db = st.session_state.db

# --- دالة جلب البيانات ---
@st.cache_data(ttl=5)
def load_portal_data():
    hab_docs = db.collection("habitants").stream()
    df_hab = pd.DataFrame([d.to_dict() for d in hab_docs])
    cont_docs = db.collection("cotisations").stream()
    df_cont = pd.DataFrame([d.to_dict() for d in cont_docs])
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

st.title("🏢"حي 56 مسكن بن سونة - Bloc B"")

if not df_hab.empty:
    floors = {
        "الطابق الأول": [61, 62, 63, 64],
        "الطابق الثاني": [23, 24, 65, 66],
        "الطابق الثالث": [25, 26, 27, 28],
        "الطابق الرابع": [29, 30, 31, 32],
        "الطابق الخامس": [33, 34, 35, 36],
        "الطابق السادس": [37, 38, 39, 40],
        "الطابق السابع": [41, 42, 43, 44]
    }

    display_options = ["-- اختر رقم السكن --"]
    for floor_name, apts in floors.items():
        for a in apts:
            display_options.append(f"{floor_name} - سكن رقم {a}")

    choice = st.selectbox("🏠 الرجاء تحديد سكنك:", display_options)

    if choice != "-- اختر رقم السكن --":
        selected_apt = int(choice.split(" ")[-1])
        
        resident_info = df_hab[df_hab['Appart'] == selected_apt]
        if not resident_info.empty:
            st.info(f"👤 السيد(ة): **{resident_info.iloc[0]['Nom']}**")

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
                 st.warning("لم يتم دفع أي مبلغ بعد.")

        st.divider()
        st.subheader("📋 سجل آخر الدفعات:")
        if not apt_payments.empty:
            display_df = apt_payments[['Date', 'Montant']].sort_values('Date', ascending=False)
            st.table(display_df.head(5))
    else:
        st.write("الرجاء اختيار سكنك من القائمة أعلاه.")
else:
    st.warning("جاري تحميل البيانات...")


