import streamlit as st
import pandas as pd
from google.cloud import firestore
import requests
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# 1. إعداد الصفحة
st.set_page_config(page_title="Portail Bloc B", page_icon="🏢")

# --- 2. دالة إرسال الإشعارات ---
def send_telegram(msg, target_chat_id=None):
    try:
        token = st.secrets["TELEGRAM_TOKEN"]
        chat_id = target_chat_id if target_chat_id else st.secrets["CHAT_ID"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, params={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})
    except:
        pass

# --- 3. اتصال قاعدة البيانات ---
if 'db' not in st.session_state:
    try:
        creds_info = dict(st.secrets["firebase_key"])
        st.session_state.db = firestore.Client.from_service_account_info(creds_info)
    except Exception as e:
        st.error("❌ فشل الاتصال بقاعدة البيانات.")
        st.stop()

db = st.session_state.db

# --- 4. جلب البيانات ---
@st.cache_data(ttl=10)
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

# --- 5. واجهة تسجيل الدخول ---
st.title("🏢 بـوابة سـكان Bloc B")
st.write("مرحباً بك! يرجى إدخال رقم هاتفك المسجل للوصول إلى بياناتك.")

# خانة إدخال رقم الهاتف
phone_input = st.text_input("رقم الهاتف:", placeholder="0XXXXXXXXX")

if phone_input:
    # البحث عن الساكن الذي يملك هذا الرقم
    # ملاحظة: تأكد أن رقم الهاتف في Firestore مخزن كنص (String)
    user_row = df_hab[df_hab['Tel'].astype(str).str.strip() == phone_input.strip()]

    if not user_row.empty:
        res_info = user_row.iloc[0]
        selected_apt = res_info['Appart']
        res_name = res_info.get('Nom', '---')
        
        st.success(f"✅ تم التعرف عليك: **{res_name}** (شقة {selected_apt})")
        st.divider()

        # --- إشعار دخول للأدمن ---
        if 'notified' not in st.session_state:
            send_telegram(f"👤 دخول جديد: {res_name} (شقة {selected_apt})")
            st.session_state.notified = True

        # --- زر تفعيل التلغرام الشخصي ---
        with st.expander("🔔 تفعيل التنبيهات على هاتفك"):
            bot_username = "bloc_b_notifier_bot" 
            telegram_link = f"https://t.me/{bot_username}?start={selected_apt}"
            st.write("اضغط على الزر أدناه ليقوم البوت بإرسال إشعارات الدفع لك مباشرة.")
            st.link_button("تفعيل إشعارات تلغرام", telegram_link)

        # --- عرض الحالة المالية ---
        is_resident = str(res_info.get('Resident', True)).lower() not in ['false', '0', 'no']
        
        if not is_resident:
            st.warning("⚠️ هذه الشقة مصنفة (غير مقيمة). الساكن معفى من المساهمات حالياً.")
        else:
            apt_pays = df_cont[df_cont['Appart'] == selected_apt] if not df_cont.empty else pd.DataFrame()
            total_paid = pd.to_numeric(apt_pays['Montant'], errors='coerce').sum() if not apt_pays.empty else 0
            
            start_y = int(res_info.get('StartYear', 2025)) if pd.notna(res_info.get('StartYear')) else 2025
            base_date = datetime(start_y, 12, 31)
            final_date = base_date + relativedelta(months=int(total_paid // 1000))
            
            # عرض المقاييس
            col1, col2 = st.columns(2)
            col1.metric("الوضعية مسواة إلى غاية", final_date.strftime('%d/%m/%Y'))
            col2.metric("إجمالي المدفوعات", f"{total_paid:,.0f} DA")

            if not apt_pays.empty:
                st.subheader("📋 آخر 5 دفعات")
                st.table(apt_pays[['Date', 'Montant']].sort_values('Date', ascending=False).head(5))
    else:
        st.error("❌ عذراً، هذا الرقم غير مسجل لدينا. يرجى التواصل مع الإدارة.")

else:
    st.info("💡 أدخل رقم هاتفك المكون من 10 أرقام للبدء.")


