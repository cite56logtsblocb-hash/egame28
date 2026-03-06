import streamlit as st
import pandas as pd
from google.cloud import firestore
from datetime import datetime
import calendar
import json

# 1. إعداد الصفحة
st.set_page_config(
    page_title="Portail du Batiment Bloc B - Cité 56 Logements", 
    page_icon="🏢", 
    layout="centered"
)

# 2. الاتصال بـ Firebase عبر Secrets
if 'db' not in st.session_state:
    try:
        # تأكد من أن "firebase_key" موجود في Secrets بموقع Streamlit
        key_dict = json.loads(st.secrets["firebase_key"])
        st.session_state.db = firestore.Client.from_service_account_info(key_dict)
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        st.stop()

db = st.session_state.db

# 3. دالة جلب البيانات
@st.cache_data(ttl=10)
def load_portal_data():
    try:
        # جلب السكان
        hab_docs = db.collection("habitants").stream()
        df_hab = pd.DataFrame([d.to_dict() for d in hab_docs])
        
        # جلب الدفعات
        cont_docs = db.collection("cotisations").stream()
        df_cont = pd.DataFrame([d.to_dict() for d in cont_docs])
        
        # تنظيف بيانات السكان
        if not df_hab.empty:
            if "Appart" in df_hab.columns:
                df_hab["Appart"] = pd.to_numeric(df_hab["Appart"], errors="coerce")
            
            # معالجة خانة الإعفاء (is_absent)
            if "is_absent" not in df_hab.columns:
                df_hab["is_absent"] = False
            else:
                df_hab["is_absent"] = df_hab["is_absent"].fillna(False)

        # تنظيف بيانات الدفعات
        if not df_cont.empty:
            if "Appart" in df_cont.columns:
                df_cont["Appart"] = pd.to_numeric(df_cont["Appart"], errors="coerce")
            if "Montant" in df_cont.columns:
                df_cont["Montant"] = pd.to_numeric(df_cont["Montant"], errors="coerce").fillna(0)
            
        return df_hab, df_cont
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame(), pd.DataFrame()

df_hab, df_cont = load_portal_data()

# 4. دالة حساب تاريخ التغطية
def get_last_day_paid(total_amount):
    if total_amount <= 0:
        return None
    months_covered = int(total_amount // 1000)
    if months_covered == 0:
        return None
    
    # الحساب يبدأ من جانفي 2026
    year = 2026 + (months_covered - 1) // 12
    month = (months_covered - 1) % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return f"{last_day:02d}/{month:02d}/{year}"

# 5. واجهة المستخدم بالعناوين الجديدة
st.title("🏢 Portail du Batiment Bloc B")
st.subheader("Cité 56 Logements Bensouna")
st.markdown("---")

if not df_hab.empty:
    # تقسيم الطوابق
    floors = {
        "1er Étage": [61, 62, 63, 64],
        "2ème Étage": [23, 24, 65, 66],
        "3ème Étage": [25, 26, 27, 28],
        "4ème Étage": [29, 30, 31, 32],
        "5ème Étage": [33, 34, 35, 36],
        "6ème Étage": [37, 38, 39, 40],
        "7ème Étage": [41, 42, 43, 44],
    }

    options = ["-- Sélectionner votre appartement --"]
    for f_name, apts in floors.items():
        for a in apts:
            options.append(f"{f_name} - N° {a}")

    choice = st.selectbox("🏠 Veuillez choisir votre appartement:", options)

    if choice != "-- Sélectionner votre appartement --":
        # استخراج رقم الشقة من النص
        try:
            selected_apt = int(choice.split("N° ")[-1])
            
            # البحث عن الساكن
            res_data = df_hab[df_hab['Appart'] == selected_apt]
            
            if not res_data.empty:
                row = res_data.iloc[0]
                st.info(f"👤 Résident: **{row['Nom']}**")
                
                # حالة الإعفاء
                is_absent = row.get('is_absent', False)
                
                # حساب الدفعات
                apt_pays = df_cont[df_cont['Appart'] == selected_apt] if not df_cont.empty else pd.DataFrame()
                total_paid = apt_pays['Montant'].sum() if not apt_pays.empty else 0
                
                expiry = get_last_day_paid(total_paid)
                
                # منطق الحساب
                if is_absent:
                    st.warning("✅ Statut: Non-résident (Exonéré)")
                    dette = 0
                else:
                    curr_month = datetime.now().month
                    req_total = curr_month * 1000
                    dette = max(0, req_total - total_paid)

                # عرض الأرقام
                c1, c2 = st.columns(2)
                c1.metric("Total Payé", f"{total_paid:,.0f} DA")
                
                if not is_absent:
                    if dette > 0:
                        st.error(f"⚠️ Dette: {dette:,.0f} DA")
                    else:
                        st.success("✅ Situation Régularisée")
                        if expiry:
                            st.caption(f"Couvert jusqu'au: {expiry}")

                st.divider()
                st.subheader("📋 Historique:")
                if not apt_pays.empty:
                    # عرض آخر 5 دفعات
                    hist = apt_pays[['Date', 'Montant']].sort_values('Date', ascending=False)
                    st.table(hist.head(5))
                else:
                    st.write("Aucun paiement.")
        except Exception as e:
            st.error(f"Error processing apartment: {e}")
    else:
        st.write("Sélectionnez une option.")
else:
    st.warning("⚠️ Chargement...")
