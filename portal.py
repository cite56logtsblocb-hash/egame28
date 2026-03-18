import streamlit as st
import pandas as pd
from google.cloud import firestore
import telebot
import threading
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta

# 1. إعدادات البوت والقاعدة
TOKEN = st.secrets["TELEGRAM_TOKEN"]
bot = telebot.TeleBot(TOKEN)

if 'db' not in st.session_state:
    creds = dict(st.secrets["firebase_key"])
    if "private_key" in creds:
        creds["private_key"] = creds["private_key"].replace("\\n", "\n")
    st.session_state.db = firestore.Client.from_service_account_info(creds)

db = st.session_state.db

# 2. تشغيل البوت في الخلفية (Thread)
def run_bot():
    @bot.message_handler(commands=['start'])
    def handle_start(message):
        args = message.text.split()
        if len(args) > 1:
            apt_num = args[1]
            chat_id = message.chat.id
            try:
                db.collection("habitants").document(str(apt_num)).update({"telegram_id": str(chat_id)})
                bot.send_message(chat_id, f"✅ تم ربط الشقة {apt_num} بنجاح!")
            except:
                pass
    bot.remove_webhook()
    bot.polling(none_stop=True)

if 'bot_thread' not in st.session_state:
    threading.Thread(target=run_bot, daemon=True).start()
    st.session_state.bot_thread = True

# 3. واجهة البوابة
st.set_page_config(page_title="Portal Bloc B", page_icon="🏢")
st.title("🏢 بوابة سكان Bloc B")

phone = st.text_input("رقم الهاتف المسجل:")

if phone:
    # جلب البيانات بدون Cache للتأكد من التحديث اللحظي
    h_docs = db.collection("habitants").stream()
    df_h = pd.DataFrame([d.to_dict() for d in h_docs])
    user = df_h[df_h['Tel'].astype(str).str.strip() == phone.strip()]

    if not user.empty:
        res = user.iloc[0]
        apt = str(res['Appart'])
        tg_id = res.get('telegram_id')

        st.success(f"مرحباً بك شقة {apt}")
        
        # --- تعديل منطق الزر ---
        bot_info = bot.get_me()
        link = f"https://t.me/{bot_info.username}?start={apt}"

        if not tg_id or str(tg_id).lower() in ["none", ""]:
            st.warning("🔔 حسابك غير مربوط")
            st.link_button("🚀 تفعيل التنبيهات الآن", link)
        else:
            st.info(f"✅ الإشعارات مفعلة (ID: {tg_id})")
            # اختيار إضافي: زر لإعادة الربط في حال غير الساكن حسابه
            with st.expander("تغيير حساب التلغرام؟"):
                st.link_button("إعادة الربط بحساب جديد", link)

        # عرض الحالة المالية
        c_docs = db.collection("cotisations").stream()
        df_c = pd.DataFrame([d.to_dict() for d in c_docs])
        total = pd.to_numeric(df_c[df_c['Appart'] == int(apt)]['Montant'], errors='coerce').sum()
        valid_date = datetime(2026, 1, 1) + relativedelta(months=int(total // 1000)) - pd.Timedelta(days=1)
        
        st.divider()
        col1, col2 = st.columns(2)
        col1.metric("مغطى إلى غاية", valid_date.strftime('%d/%m/%Y'))
        col2.metric("المجموع", f"{total:,.0f} DA")
    else:
        st.error("الرقم غير مسجل.")
