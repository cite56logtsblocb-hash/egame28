import streamlit as st
import pandas as pd
from google.cloud import firestore
from datetime import datetime
import json
import os

# 1. إعداد الصفحة
st.set_page_config(page_title="Portail Bloc B", page_icon="🏢", layout="centered")

# 2. منطق الاتصال (يدعم البيسي عبر الملف و الهاتف عبر Secrets)
if 'db' not in st.session_state:
    try:
        key_path = "serviceAccountKey.json" 
        if os.path.exists(key_path):
            with open(key_path) as f:
                st.session_state.db = firestore.Client.from_service_account_info(json.load(f))
        elif "firebase_key" in st.secrets:
            key_dict = json.loads(st.secrets["firebase_key"])
            st.session_state.db = firestore.Client.from_service_account_info(key_dict)
        else:
            st.error("❌ ملف الاتصال serviceAccountKey.json غير موجود في المجلد!")
            st.stop()
    except Exception as e:
        st.error(f"❌ خطأ في الاتصال: {e}")
        st.stop()

db = st.session_state.db

# 3. توزيع الطوابق
FLOORS = {
    "الطابق الأول":  [61, 62, 63, 64],
    "الطابق الثاني": [23, 24, 65, 66],
    "الطابق الثالث": [25, 26, 27, 28],
    "الطابق الرابع": [29, 30, 31, 32],
    "الطابق الخامس": [33, 34, 35, 36],
    "الطابق السادس": [37, 38, 39, 40],
    "الطابق السابع": [41, 42, 43, 44],
}

@st.cache_data(ttl=5)
def load_portal_data():
    try:
        hab_docs = db.collection("habitants").stream()
        df_hab = pd.DataFrame([d.to_dict() for d in hab_docs])
        cont_docs = db.collection("cotisations").stream()
        df_cont = pd.DataFrame([d.to_dict() for d in cont_docs])
        
        # التأكد من تحويل أرقام الشقق والمبالغ لتفادي أخطاء الحساب
        if not df_hab.empty:
            df_hab["Appart"] = pd.to_numeric(df_hab["Appart"], errors="coerce")
        if not df_cont.empty:
            df_cont["Appart"] = pd.to_numeric(df_cont["Appart"], errors="coerce")
            df_cont["Montant"] = pd.to_numeric(df_cont["Montant"], errors="coerce").fillna(0)
            
        return df_hab, df_cont
    except:
        return pd.DataFrame(), pd.DataFrame()

df_hab, df_cont = load_portal_data()

# 4. واجهة المستخدم
st.title("🏢 بوابة سكان عمارات سعدادو")
st.markdown("---")

if not df_hab.empty:
    options = ["-- اختر شقتك من القائمة --"]
    for floor_name, apts in FLOORS.items():
        for a in apts:
            options.append(f"{floor_name} - شقة {a}")

    choice = st.selectbox("🏠 الرجاء اختيار رقم الشقة:", options)

    if choice != "-- اختر شقتك من القائمة --":
        try:
            selected_apt = int(choice.split("شقة ")[-1])
            res_rows = df_hab[df_hab['Appart'] == selected_apt]
            
            if not res_rows.empty:
                res_info = res_rows.iloc[0]
                st.info(f"👤 الساكن: **{res_info.get('Nom', 'غير مسجل')}**")
                
                # حساب إجمالي المدفوعات
                if not df_cont.empty:
                    apt_pays = df_cont[df_cont['Appart'] == selected_apt]
                    total_paid = apt_pays['Montant'].sum()
                else:
                    apt_pays = pd.DataFrame()
                    total_paid = 0
                
                # --- منطق حساب تاريخ انتهاء الاشتراك ---
                nb_mois = int(total_paid // 1000)
                
                if nb_mois > 0:
                    # الحساب يبدأ من 01 جانفي 2026
                    start_date = datetime(2026, 1, 1)
                    # إضافة الأشهر (استخدام relativedelta لتفادي أخطاء المكتبات)
                    from dateutil.relativedelta import relativedelta
                    target_date = start_date + relativedelta(months=nb_mois) - relativedelta(days=1)
                    jusquau = target_date.strftime('%d/%m/%Y')
                    
                    if target_date.date() >= datetime.now().date():
                        st.success(f"✅ الوضعية نظامية إلى غاية: **{jusquau}**")
                    else:
                        st.warning(f"⚠️ الوضعية مغطاة فقط إلى غاية: **{jusquau}**")
                        # عرض الدين إذا وجد تعديل يدوي
                        d_over = res_info.get('DetteOverride')
                        if d_over and d_over > 0:
                            st.error(f"🚨 الدين الحالي المطلوب: {d_over:,.0f} DA")
                else:
                    st.error("❌ لا توجد مدفوعات مسجلة لهذا السكن.")

                st.metric("إجمالي المدفوعات", f"{total_paid:,.0f} DA")
                
                st.divider()
                st.subheader("📋 سجل آخر 5 عمليات")
                if not apt_pays.empty:
                    st.table(apt_pays[['Date', 'Montant']].sort_values('Date', ascending=False).head(5))
            else:
                st.warning("بيانات هذا السكن غير مكتملة في قاعدة البيانات.")
        except Exception as e:
            st.error(f"حدث خطأ أثناء عرض التفاصيل: {e}")
else:
    st.warning("تعذر تحميل البيانات. تأكد من وجود سكان مسجلين.")
