import streamlit as st
import pandas as pd
from google.cloud import firestore
from datetime import datetime
import calendar
import json

# إعداد الصفحة بالعنوان الجديد
st.set_page_config(
    page_title="Portail du Batiment Bloc B - Cité 56 Logements", 
    page_icon="🏢", 
    layout="centered"
)

# --- الاتصال بـ Firebase عبر Secrets ---
if 'db' not in st.session_state:
    try:
        key_dict = json.loads(st.secrets["firebase_key"])
        st.session_state.db = firestore.Client.from_service_account_info(key_dict)
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        st.stop()

db = st.session_state.db

# --- دالة جلب البيانات ---
@st.cache_data(ttl=10)
def load_portal_data():
    try:
        hab_docs = db.collection("habitants").stream()
        df_hab = pd.DataFrame([d.to_dict() for d in hab_docs])
        
        cont_docs = db.collection("cotisations").stream()
        df_cont = pd.DataFrame([d.to_dict() for d in cont_docs])
        
        if not df_hab.empty:
            df_hab["Appart"] = pd.to_numeric(df_hab["Appart"], errors="coerce").astype("Int64")
            if "is_absent" not in df_hab.columns:
                df_hab["is_absent"] = False
            else:
                df_hab["is_absent"] = df_hab["is_absent"].fillna(False)

        if not df_cont.empty:
            df_cont["Appart"] = pd.to_numeric(df_cont["Appart"], errors="coerce").astype("Int64")
            df_cont["Montant"] = pd.to_numeric(df_cont["Montant"], errors="coerce").fillna(0)
            
        return df_hab, df_cont
    except:
        return pd.DataFrame(), pd.DataFrame()

df_hab, df_cont = load_portal_data()

# --- دالة حساب آخر يوم في الشهر المسوى ---
def get_last_day_paid(total_amount):
    if total_amount <= 0: return None
    months_covered = int(total_amount // 1000)
    if months_covered == 0: return None
    year = 2026 + (months_covered - 1) // 12
    month = (months_covered - 1) % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return f"{last_day:02d}/{month:02d}/{year}"

# العنوان الجديد الذي طلبته
st.title("🏢 Portail du Batiment Bloc B")
st.subheader("Cité 56 Logements Bensouna")
st.markdown("---")

if not df_hab.empty:
    floors = {
        "1er Étage": [61, 62, 63, 64],
        "2ème Étage": [23, 24, 65, 66],
        "3ème Étage": [25, 26, 27, 28],
        "4ème Étage": [29, 30, 31, 32],
        "5ème Étage": [33, 34, 35, 36],
        "6ème Étage": [37, 38, 39, 40],
        "7ème Étage": [41, 42, 43, 44],
    }

    display_options = ["-- Sélectionner votre appartement --"]
    for floor_name, apts in floors.items():
        for a in apts:
            display_options.append(f"{floor_name} - N° {a}")

    choice = st.selectbox("🏠 Veuillez choisir votre appartement:", display_options)

    if choice != "-- Sélectionner votre appartement --":
        selected_apt = int(choice.split(" ")[-1])
        
        resident_info = df_hab[df_hab['Appart'] == selected_apt]
        
        if not resident_info.empty:
            row = resident_info.iloc[0]
            st.info(f"👤 Résident: **{row['Nom']}**")
            
            is_absent = row.get('is_absent', False)
            
            apt_payments = df_cont[df_cont['Appart'] == selected_apt] if not df_cont.empty else pd.DataFrame()
            total_paid = apt_payments['Montant'].sum() if not apt_payments.empty else 0
            
            expiry_date = get_last_day_paid(total_paid)
            
            if is_absent:
                st.warning("✅ Statut spécial: Non-résident (Exonéré des cotisations)")
                dette = 0
            else:
                current_month = datetime.now().month
                required_total = current_month * 1000
                dette = max(0, required_total - total_paid)

            col1, col2 = st.columns(2)
            col1.metric("Total Payé", f"{total_paid:,.0f} DA")
            
            if not is_absent:
                if dette > 0:
                    st.error(f"⚠️ Dette actuelle: {dette:,.0f} DA")
                else:
                    st.success("✅ Situation financière régularisée")
                    if expiry
