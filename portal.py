import streamlit as st
import pandas as pd
from google.cloud import firestore
from datetime import datetime
import calendar
import json

# 1. إعداد الصفحة
st.set_page_config(page_title="Portail Bloc B", page_icon="🏢")

# 2. الاتصال بـ Firebase
if 'db' not in st.session_state:
    try:
        key_dict = json.loads(st.secrets["firebase_key"])
        st.session_state.db = firestore.Client.from_service_account_info(key_dict)
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        st.stop()

db = st.session_state.db

# 3. جلب البيانات مع دعم التعديل اليدوي (DetteOverride)
@st.cache_data(ttl=5)
def load_portal_data():
    try:
        hab_docs = db.collection("habitants").stream()
        df_hab = pd.DataFrame([d.to_dict() for d in hab_docs])
        
        cont_docs = db.collection("cotisations").stream()
        df_cont = pd.DataFrame([d.to_dict() for d in cont_docs])
        
        if not df_hab.empty:
            df_hab["Appart"] = pd.to_numeric(df_hab["Appart"], errors="coerce").astype("Int64")
            # التأكد من وجود الأعمدة التي نعدلها في ملف الإدارة
            for col in ["Resident", "DetteOverride"]:
                if col not in df_hab.columns:
                    df_hab[col] = True if col == "Resident" else pd.NA
        
        if not df_cont.empty:
            df_cont["Appart"] = pd.to_numeric(df_cont["Appart"], errors="coerce").astype("Int64")
            df_cont["Montant"] = pd.to_numeric(df_cont["Montant"], errors="coerce").fillna(0)
            
        return df_hab, df_cont
    except:
        return pd.DataFrame(), pd.DataFrame()

df_hab, df_cont = load_portal_data()

# 4. واجهة المستخدم
st.title("🏢 Portail du Batiment Bloc B")
st.markdown("---")

if not df_hab.empty:
    # القائمة المنسدلة (نفس ترتيب ملف الإدارة)
    options = ["-- Sélectionner votre appartement --"]
    apts_list = sorted(df_hab["Appart"].dropna().unique())
    for a in apts_list:
        options.append(f"Appartement N° {a}")

    choice = st.selectbox("🏠 Veuillez choisir votre appartement:", options)

    if choice != "-- Sélectionner votre appartement --":
        selected_apt = int(choice.split("N° ")[-1])
        res_info = df_hab[df_hab['Appart'] == selected_apt].iloc[0]
        
        # --- منطق حساب الدين المحدث ---
        is_resident = bool(res_info.get('Resident', True))
        dette_manual = res_info.get('DetteOverride', pd.NA)
        
        # جلب إجمالي المدفوعات لعرضها فقط
        apt_pays = df_cont[df_cont['Appart'] == selected_apt] if not df_cont.empty else pd.DataFrame()
        total_paid = apt_pays['Montant'].sum() if not apt_pays.empty else 0

        st.info(f"👤 Résident: **{res_info.get('Nom', 'Inconnu')}**")

        if not is_resident:
            st.warning("✅ Statut: Non-résident (Exonéré)")
            final_dette = 0
        else:
            # هنا السر: إذا عدلت القيمة يدوياً في الجدول، نستخدمها هي
            if not pd.isna(dette_manual):
                final_dette = float(dette_manual)
            else:
                # إذا لم تعدلها يدوياً، نحسبها آلياً (الشهر الحالي * 1000 - المدفوع)
                current_month = datetime.now().month
                final_dette = max(0, (current_month * 1000) - total_paid)

        # عرض النتائج
        col1, col2 = st.columns(2)
        col1.metric("Total Payé", f"{total_paid:,.0f} DA")
        
        if is_resident:
            if final_dette > 0:
                st.error(f"⚠️ Dette Actuelle: {final_dette:,.0f} DA")
            else:
                st.success("✅ Situation Régularisée")

        st.divider()
        st.subheader("📋 Historique:")
        if not apt_pays.empty:
            st.table(apt_pays[['Date', 'Montant']].sort_values('Date', ascending=False).head(5))
        else:
            st.write("Aucun paiement.")
