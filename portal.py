import streamlit as st
import pandas as pd
from google.cloud import firestore
from datetime import datetime
import json
import os

# 1. إعداد الصفحة
st.set_page_config(page_title="Portail Bloc B", page_icon="🏢")

# 2. منطق الاتصال (بيسي + هاتف)
if 'db' not in st.session_state:
    try:
        # ابحث عن ملف JSON المحرك بجانب الكود أولاً (للبيسي)
        key_path = "serviceAccountKey.json" 
        if os.path.exists(key_path):
            with open(key_path) as f:
                st.session_state.db = firestore.Client.from_service_account_info(json.load(f))
        elif "firebase_key" in st.secrets:
            key_dict = json.loads(st.secrets["firebase_key"])
            st.session_state.db = firestore.Client.from_service_account_info(key_dict)
        else:
            st.error("❌ مفتاح الاتصال غير موجود")
            st.stop()
    except Exception as e:
        st.error(f"❌ خطأ اتصال: {e}")
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

@st.cache_data(ttl=2)
def load_portal_data():
    try:
        hab_docs = db.collection("habitants").stream()
        df_hab = pd.DataFrame([d.to_dict() for d in hab_docs])
        cont_docs = db.collection("cotisations").stream()
        df_cont = pd.DataFrame([d.to_dict() for d in cont_docs])
        return df_hab, df_cont
    except:
        return pd.DataFrame(), pd.DataFrame()

df_hab, df_cont = load_portal_data()

# 4. واجهة المستخدم
st.title("🏢 Portail Bloc B")
st.markdown("---")

if not df_hab.empty:
    options = ["-- اختر شقتك من القائمة --"]
    for floor_name, apts in FLOORS.items():
        for a in apts:
            options.append(f"{floor_name} - شقة {a}")

    choice = st.selectbox("🏠 الرجاء اختيار رقم الشقة:", options)

    if choice != "-- اختر شقتك من القائمة --":
        selected_apt = int(choice.split("شقة ")[-1])
        res_info = df_hab[df_hab['Appart'] == selected_apt].iloc[0] if not df_hab[df_hab['Appart'] == selected_apt].empty else {}
        
        if res_info:
            st.info(f"👤 الساكن: **{res_info.get('Nom', 'غير مسجل')}**")
            
            # حساب إجمالي المدفوعات
            apt_pays = df_cont[df_cont['Appart'] == selected_apt] if not df_cont.empty else pd.DataFrame()
            total_paid = apt_pays['Montant'].sum() if not apt_pays.empty else 0
            
            # --- منطق حساب "نظامية إلى غاية" ---
            # الحساب يبدأ من جانفي 2026 (1000 دج للشهر)
            nb_mois_payes = int(total_paid // 1000)
            
            if nb_mois_payes > 0:
                # إضافة عدد الأشهر لتاريخ البداية (01/01/2026)
                start_date = datetime(2026, 1, 1)
                # التاريخ الذي تم تغطيته (نهاية الشهر الأخير المدفوع)
                target_date = start_date + pd.DateOffset(months=nb_mois_payes) - pd.Timedelta(days=1)
                jusquau = target_date.strftime('%d/%m/%Y')
                
                # التحقق إذا كان التاريخ في المستقبل (نظامية) أو الماضي (عليه دين)
                if target_date.date() >= datetime.now().date():
                    st.success(f"✅ الوضعية نظامية إلى غاية: **{jusquau}**")
                else:
                    st.warning(f"⚠️ الوضعية مغطاة فقط إلى غاية: **{jusquau}**")
                    # عرض الدين المتبقي (اختياري)
                    dette_manual = res_info.get('DetteOverride', pd.NA)
                    if not pd.isna(dette_manual):
                        st.error(f"🚨 الدين الحالي المستحق: {dette_manual:,.0f} DA")
            else:
                st.error("❌ لم يتم تسجيل أي دفعات لهذا السكن بعد.")

            st.metric("إجمالي ما تم دفعه", f"{total_paid:,.0f} DA")
            
            st.divider()
            st.subheader("📋 سجل المدفوعات")
            if not apt_pays.empty:
                st.table(apt_pays[['Date', 'Montant']].sort_values('Date', ascending=False).head(5))
