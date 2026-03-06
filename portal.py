import streamlit as st
import pandas as pd
from google.cloud import firestore
from datetime import datetime
from dateutil.relativedelta import relativedelta
import json
import os

# 1. إعداد الصفحة
st.set_page_config(page_title="Portail Bloc B", page_icon="🏢")

# 2. اتصال قاعدة البيانات (بيسي + هاتف)
if 'db' not in st.session_state:
    try:
        key_path = "serviceAccount_key.json" 
        if os.path.exists(key_path):
            with open(key_path) as f:
                st.session_state.db = firestore.Client.from_service_account_info(json.load(f))
        elif "firebase_key" in st.secrets:
            key_dict = json.loads(st.secrets["firebase_key"])
            st.session_state.db = firestore.Client.from_service_account_info(key_dict)
        else:
            st.error("⚠️ ملف الاتصال غير موجود")
            st.stop()
    except Exception as e:
        st.error(f"❌ خطأ: {e}")
        st.stop()

db = st.session_state.db

# 3. جلب البيانات
@st.cache_data(ttl=2)
def load_data():
    try:
        h_docs = db.collection("habitants").stream()
        df_h = pd.DataFrame([d.to_dict() for d in h_docs])
        c_docs = db.collection("cotisations").stream()
        df_c = pd.DataFrame([d.to_dict() for d in c_docs])
        return df_h, df_c
    except:
        return pd.DataFrame(), pd.DataFrame()

df_hab, df_cont = load_data()

# 4. واجهة المستخدم
st.title("🏢 بوابة سكان عمارات سعدادو")
st.markdown("---")

if not df_hab.empty:
    # قائمة الشقق (نفس التوزيع السابق)
    apart_list = sorted(df_hab['Appart'].unique())
    selected_apt = st.selectbox("🏠 اختر رقم شقتك:", apart_list)

    if selected_apt:
        res_info = df_hab[df_hab['Appart'] == selected_apt].iloc[0]
        st.info(f"👤 الساكن: **{res_info.get('Nom', '---')}**")

        # حساب المدفوعات
        apt_pays = df_cont[df_cont['Appart'] == selected_apt] if not df_cont.empty else pd.DataFrame()
        total_paid = pd.to_numeric(apt_pays['Montant'], errors='coerce').sum() if not apt_pays.empty else 0
        
        # --- منطق "الوضعية مسواة إلى غاية" ---
        # نقطة الانطلاق: نهاية سنة 2025
        base_date = datetime(2025, 12, 31)
        
        # كل 1000 دج تزيد شهراً واحداً
        months_to_add = int(total_paid // 1000)
        
        # حساب تاريخ نهاية التسوية
        final_date = base_date + relativedelta(months=months_to_add)
        formatted_date = final_date.strftime('%d/%m/%Y')

        # عرض النتيجة باللون الأخضر دائماً كما طلبت
        st.success(f"✅ الوضعية مسواة إلى غاية: **{formatted_date}**")
        
        # إظهار المبلغ الإجمالي
        st.metric("إجمالي المبالغ المدفوعة", f"{total_paid:,.0f} DA")

        # سجل العمليات
        if not apt_pays.empty:
            st.divider()
            st.subheader("📋 آخر عمليات الدفع")
            st.table(apt_pays[['Date', 'Montant']].sort_values('Date', ascending=False).head(5))
