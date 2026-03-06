import streamlit as st
import pandas as pd
from google.cloud import firestore
from datetime import datetime
import calendar
import json

# 1. إعداد الصفحة بنفس الثيم الاحترافي
st.set_page_config(
    page_title="Portail du Batiment Bloc B - Cité 56 Logements", 
    page_icon="🏢", 
    layout="centered"
)

# 2. الاتصال بـ Firebase (نفس منطق ملف الإدارة تماماً)
if 'db' not in st.session_state:
    try:
        if "firebase_key" in st.secrets:
            key_dict = json.loads(st.secrets["firebase_key"])
            st.session_state.db = firestore.Client.from_service_account_info(key_dict)
        else:
            st.error("❌ Secrets Error!")
            st.stop()
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        st.stop()

db = st.session_state.db

# 3. دالة جلب البيانات مع مطابقة المسميات
@st.cache_data(ttl=5)
def load_portal_data():
    try:
        # جلب السكان
        hab_docs = db.collection("habitants").stream()
        df_hab = pd.DataFrame([d.to_dict() for d in hab_docs])
        
        # جلب الدفعات
        cont_docs = db.collection("cotisations").stream()
        df_cont = pd.DataFrame([d.to_dict() for d in cont_docs])
        
        if not df_hab.empty:
            df_hab["Appart"] = pd.to_numeric(df_hab["Appart"], errors="coerce").astype("Int64")
            # مطابقة الحقل: في ملف الإدارة اسم الحقل 'Resident' ونوعه Boolean
            if "Resident" not in df_hab.columns:
                df_hab["Resident"] = True
            else:
                df_hab["Resident"] = df_hab["Resident"].fillna(True).astype(bool)

        if not df_cont.empty:
            df_cont["Appart"] = pd.to_numeric(df_cont["Appart"], errors="coerce").astype("Int64")
            df_cont["Montant"] = pd.to_numeric(df_cont["Montant"], errors="coerce").fillna(0)
            
        return df_hab, df_cont
    except:
        return pd.DataFrame(), pd.DataFrame()

df_hab, df_cont = load_portal_data()

# 4. دالة حساب التاريخ (تغطية الاشتراك)
def get_last_day_paid(total_amount):
    if total_amount <= 0: return None
    months_covered = int(total_amount // 1000)
    if months_covered == 0: return None
    year = 2026 + (months_covered - 1) // 12
    month = (months_covered - 1) % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return f"{last_day:02d}/{month:02d}/{year}"

# 5. واجهة المستخدم
st.title("🏢 Portail du Batiment Bloc B")
st.subheader("Cité 56 Logements Bensouna")
st.markdown("---")

if not df_hab.empty:
    # القائمة بنفس ترتيب الطوابق في ملف الإدارة
    FLOORS = {
        "1er Étage": [61, 62, 63, 64],
        "2ème Étage": [23, 24, 65, 66],
        "3ème Étage": [25, 26, 27, 28],
        "4ème Étage": [29, 30, 31, 32],
        "5ème Étage": [33, 34, 35, 36],
        "6ème Étage": [37, 38, 39, 40],
        "7ème Étage": [41, 42, 43, 44],
    }

    display_options = ["-- Sélectionner votre appartement --"]
    for floor_name, apts in FLOORS.items():
        for a in apts:
            display_options.append(f"{floor_name} - N° {a}")

    choice = st.selectbox("🏠 Veuillez choisir votre appartement:", display_options)

    if choice != "-- Sélectionner votre appartement --":
        selected_apt = int(choice.split("N° ")[-1])
        
        # تصفية البيانات
        resident_info = df_hab[df_hab['Appart'] == selected_apt]
        
        if not resident_info.empty:
            row = resident_info.iloc[0]
            st.info(f"👤 Résident: **{row.get('Nom', 'Inconnu')}**")
            
            # استخراج الحالة (Resident = True يعني مقيم)
            is_resident = bool(row.get('Resident', True))
            
            # جلب الدفعات
            apt_payments = df_cont[df_cont['Appart'] == selected_apt] if not df_cont.empty else pd.DataFrame()
            total_paid = apt_payments['Montant'].sum() if not apt_payments.empty else 0
            
            expiry_date = get_last_day_paid(total_paid)
            
            # منطق الحساب المالي الموحد
            if not is_resident:
                st.warning("✅ Statut: Non-résident (Exonéré)")
                dette = 0
            else:
                # حساب الدين بناءً على الشهر الحالي (سعر 1000دج)
                current_month = datetime.now().month
                required_total = current_month * 1000
                dette = max(0, required_total - total_paid)

            col1, col2 = st.columns(2)
            col1.metric("Total Payé", f"{total_paid:,.0f} DA")
            
            if is_resident:
                if dette > 0:
                    st.error(f"⚠️ Dette: {dette:,.0f} DA")
                else:
                    st.success("✅ Situation Régularisée")
                    if expiry_date:
                        st.caption(f"Couvert jusqu'au: {expiry_date}")

            st.divider()
            st.subheader("📋 Historique des paiements:")
            if not apt_payments.empty:
                display_df = apt_payments[['Date', 'Montant']].sort_values('Date', ascending=False)
                st.table(display_df.head(5))
            else:
                st.write("Aucun paiement enregistré.")
    else:
        st.write("Veuillez sélectionner votre numéro d'appartement.")
else:
    st.warning("⚠️ Chargement des données... (Vérifiez la connexion Firebase)")
