import streamlit as st
from google.cloud import firestore
import pandas as pd
from datetime import datetime

# الاتصال بـ Firebase (نفس إعدادات برنامج الإدارة)
if 'db' not in st.session_state:
    st.session_state.db = firestore.Client.from_service_account_json("firebase_key.json")
db = st.session_state.db

st.title("🏢 بوابة سكان إقامة 28 - Bloc B")
st.markdown("استعلم عن وضعية اشتراكك وديونك من خلال رقم الشقة")

# 1. جلب البيانات من السحاب
@st.cache_data(ttl=60)
def get_resident_data():
    docs = db.collection("cotisations").stream()
    return pd.DataFrame([d.to_dict() for d in docs])

df_cont = get_resident_data()

# 2. خانة البحث للسكان
apt_num = st.number_input("أدخل رقم شقتك", min_value=1, step=1)

if apt_num:
    # حساب إجمالي المدفوعات
    apt_data = df_cont[df_cont['Appart'] == apt_num]
    total_paid = apt_data['Montant'].sum() if not apt_data.empty else 0
    
    # حساب الدين (بناءً على 1000 دج شهرياً من بداية 2026)
    months_passed = datetime.now().month
    total_due = months_passed * 1000
    dette = max(0, total_due - total_paid)
    
    # عرض النتائج في بطاقات واضحة
    col1, col2 = st.columns(2)
    col1.metric("إجمالي مدفوعاتك", f"{total_paid:,.0f} DA")
    
    if dette > 0:
        col2.error(f"الدين المتبقي: {dette:,.0f} DA")
    else:
        col2.success("وضعية قانونية (لا يوجد دين) ✅")

    st.subheader("آخر عمليات الدفع المسجلة")
    st.dataframe(apt_data[['Date', 'Montant']].sort_values('Date', ascending=False), use_container_width=True)")
