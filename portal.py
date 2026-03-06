import streamlit as st
import pandas as pd
from google.cloud import firestore
from datetime import datetime
import json

# 1. إعداد الصفحة بنفس الهوية البصرية
st.set_page_config(page_title="Portail Résidents - Bloc B", page_icon="🏢", layout="centered")

# 2. الاتصال بـ Firebase (عبر Secrets)
if 'db' not in st.session_state:
    try:
        if "firebase_key" in st.secrets:
            key_dict = json.loads(st.secrets["firebase_key"])
            st.session_state.db = firestore.Client.from_service_account_info(key_dict)
        else:
            st.error("❌ secrets.toml غير موجود أو فارغ!")
            st.stop()
    except Exception as e:
        st.error(f"❌ فشل الاتصال بقاعدة البيانات: {e}")
        st.stop()

db = st.session_state.db

# 3. توزيع الطوابق (نفس الترتيب في ملف الإدارة الخاص بك)
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
        # جلب بيانات السكان (habitants)
        hab_docs = db.collection("habitants").stream()
        df_hab = pd.DataFrame([d.to_dict() for d in hab_docs])
        
        # جلب بيانات المدفوعات (cotisations)
        cont_docs = db.collection("cotisations").stream()
        df_cont = pd.DataFrame([d.to_dict() for d in cont_docs])
        
        if not df_hab.empty:
            df_hab["Appart"] = pd.to_numeric(df_hab["Appart"], errors="coerce").astype("Int64")
        if not df_cont.empty:
            df_cont["Appart"] = pd.to_numeric(df_cont["Appart"], errors="coerce").astype("Int64")
            df_cont["Montant"] = pd.to_numeric(df_cont["Montant"], errors="coerce").fillna(0)
            
        return df_hab, df_cont
    except:
        return pd.DataFrame(), pd.DataFrame()

df_hab, df_cont = load_portal_data()

# 4. واجهة المستخدم
st.title("🏢 بوابة سكان عمارات سعدادو")
st.markdown("---")

if not df_hab.empty:
    # إنشاء القائمة المنسدلة مرتبة حسب الطوابق
    options = ["-- اختر شقتك من القائمة --"]
    for floor_name, apts in FLOORS.items():
        for a in apts:
            options.append(f"{floor_name} - شقة {a}")

    choice = st.selectbox("🏠 الرجاء اختيار رقم الشقة:", options)

    if choice != "-- اختر شقتك من القائمة --":
        try:
            # استخراج رقم الشقة من الاختيار
            selected_apt = int(choice.split("شقة ")[-1])
            res_mask = df_hab[df_hab['Appart'] == selected_apt]
            
            if not res_mask.empty:
                row = res_mask.iloc[0]
                st.info(f"👤 الساكن: **{row.get('Nom', 'غير مسجل')}**")
                
                # جلب المتغيرات الهامة من الداتاباز
                is_resident = bool(row.get('Resident', True))
                # هنا يتم سحب القيمة التي غيرتها أنت يدوياً في جدول الديون
                dette_manual = row.get('DetteOverride', pd.NA)
                
                # حساب إجمالي المدفوعات التاريخية للساكن
                apt_pays = df_cont[df_cont['Appart'] == selected_apt] if not df_cont.empty else pd.DataFrame()
                total_paid = apt_pays['Montant'].sum() if not apt_pays.empty else 0

                # تحديد الدين النهائي المعروض
                if not is_resident:
                    st.warning("✅ الحالة: غير مقيم (معفى من الأعباء)")
                    final_dette = 0
                else:
                    # الأولوية للدين اليدوي (DetteOverride)
                    if not pd.isna(dette_manual):
                        final_dette = float(dette_manual)
                    else:
                        # حساب آلي احتياطي (الشهر الحالي * 1000 - المدفوع)
                        current_month = datetime.now().month
                        final_dette = max(0, (current_month * 1000) - total_paid)

                # عرض النتائج
                col1, col2 = st.columns(2)
                col1.metric("إجمالي المدفوعات", f"{total_paid:,.0f} DA")
                
                if is_resident:
                    if final_dette > 0:
                        st.error(f"⚠️ الدين الحالي: {final_dette:,.0f} DA")
                    else:
                        st.success("✅ الوضعية نظامية (لا يوجد ديون)")

                st.divider()
                st.subheader("📋 سجل آخر المدفوعات:")
                if not apt_pays.empty:
                    # ترتيب التواريخ الأحدث أولاً
                    apt_pays['Date'] = pd.to_datetime(apt_pays['Date']).dt.strftime('%d/%m/%Y')
                    st.table(apt_pays[['Date', 'Montant']].sort_values('Date', ascending=False).head(5))
                else:
                    st.write("لا توجد دفعات مسجلة بعد.")
        except Exception as e:
            st.error(f"حدث خطأ في عرض البيانات: {e}")
else:
    st.warning("جاري جلب البيانات... تأكد من الاتصال بالإنترنت.")
