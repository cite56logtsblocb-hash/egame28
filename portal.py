import streamlit as st
import pandas as pd
from datetime import datetime

# إعدادات الموبايل
st.set_page_config(page_title="إقامة 28 - استعلام", layout="centered")

st.title("🏘️ بوابة سكان إقامة 28")
st.info("اختر رقم شقتك للاطلاع على وضعيتك المالية")

try:
    # جلب البيانات
    df_cont = pd.read_csv('cotisations.csv')
    df_hab = pd.read_csv('habitants.csv')

    # اختيار الشقة
    apt_input = st.selectbox("رقم الشقة", sorted(df_hab['Appart'].unique()))

    if apt_input:
        # جلب معلومات الساكن
        res_info = df_hab[df_hab['Appart'] == apt_input]
        res_data = df_cont[df_cont['Appart'] == apt_input]
        
        nom_res = res_info.iloc[0]['Nom'] if not res_info.empty else "غير مسجل"
        total_paye = res_data['Montant'].sum() if not res_data.empty else 0
        
        # --- المعادلة الصحيحة لحساب التاريخ (Jusqu'au) ---
        tarif_mensuel = 1000 # مبلغ الاشتراك الشهري
        nb_mois_couverts = int(total_paye // tarif_mensuel)
        
        if nb_mois_couverts > 0:
            # نبدأ الحساب من 01 جانفي 2026
            # نضيف عدد الأشهر المدفوعة لنصل لأول يوم في الشهر التالي، ثم نرجع يوماً واحداً
            date_debut_annee = datetime(2026, 1, 1)
            target_date = date_debut_annee + pd.DateOffset(months=nb_mois_couverts)
            date_fin_validite = target_date - pd.Timedelta(days=1)
            
            jusquau_text = date_fin_validite.strftime('%d/%m/%Y')
            
            # تحديد اللون (أخضر إذا كان خالصاً لهذا الشهر، أحمر إذا كان متأخراً)
            current_date = datetime.now()
            is_valid = date_fin_validite >= current_date
            status_color = "success" if is_valid else "error"
        else:
            jusquau_text = "لم يتم تسجيل أي دفع بعد"
            status_color = "warning"

        # عرض النتائج بشكل كروت منظمة
        with st.container(border=True):
            st.markdown(f"### 👤 الساكن: {nom_res}")
            st.divider()
            
            col1, col2 = st.columns(2)
            col1.metric("إجمالي المدفوعات", f"{total_paye:,.0f} DA")
            
            if status_color == "success":
                col2.success(f"✅ خالص لغاية:\n**{jusquau_text}**")
            elif status_color == "error":
                col2.error(f"❌ خالص لغاية:\n**{jusquau_text}**")
            else:
                col2.warning(f"⚠️ الوضعية:\n**{jusquau_text}**")

        st.divider()
        st.caption(f"آخر تحديث للبيانات: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

except Exception as e:
    st.error("جاري مزامنة البيانات... يرجى المحاولة بعد قليل.")