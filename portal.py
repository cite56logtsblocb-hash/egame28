import streamlit as st
import pandas as pd
from google.cloud import firestore
import telebot
import threading
from datetime import datetime
from dateutil.relativedelta import relativedelta

# --- 1. إعدادات البوت والقاعدة (من Secrets) ---
TOKEN = st.secrets["TELEGRAM_TOKEN"]
bot = telebot.TeleBot(TOKEN)

# اتصال Firestore
if 'db' not in st.session_state:
    creds = dict(st.secrets["firebase_key"])
    if "private_key" in creds:
        creds["private_key"] = creds["private_key"].replace("\\n", "\n")
    st.session_state.db = firestore.Client.from_service_account_info(creds)

db = st.session_state.db

# --- 2. وظيفة البوت (تخدم في الخلفية) ---
def run_bot():
    @bot.message_handler(commands=['start'])
    def handle_start(message):
        args = message.text.split()
        if len(args) > 1:
            apt_num = args[1]
            chat_id = message.chat.id
            try:
                # التحديث في Firestore
                db.collection("habitants").document(str(apt_num)).update({
                    "telegram_id": str(chat_id)
                })
                # رسالة الترحيب
                bot.send_message(chat_id, f"✅ **تم الربط بنجاح!**\n\nمرحباً بك جارنا العزيز في شقة {apt_num}.\nستصلك كل التنبيهات هنا آلياً. 🏢")
            except:
                bot.send_message(chat_id, "⚠️ فشل الربط، تأكد من رقم الشقة في البوابة.")
        else:
            bot.send_message(message.chat.id, "مرحباً! يرجى الدخول عبر البوابة لتفعيل حسابك.")
    
    # تشغيل البوت بدون توقف البرنامج
    bot.remove_webhook()
    bot.polling(none_stop=True, interval=0)

# تشغيل البوت في Thread منفصل لمرة واحدة فقط
if 'bot_thread' not in st.session_state:
    thread = threading.Thread(target=run_bot, daemon=True)
    thread.start()
    st.session_state.bot_thread = True

# --- 3. واجهة البوابة (Streamlit) ---
st.set_page_config(page_title="Portal Bloc B", page_icon="🏢")

st.title("🏢 بوابة سكان Bloc B")
phone = st.text_input("أدخل رقم هاتفك المسجل:", placeholder="0XXXXXXXXX")

if phone:
    # جلب البيانات
    h_docs = db.collection("habitants").stream()
    df_h = pd.DataFrame([d.to_dict() for d in h_docs])
    user = df_h[df_h['Tel'].astype(str).str.strip() == phone.strip()]

    if not user.empty:
        res = user.iloc[0]
        apt = str(res['Appart'])
        tg_id = res.get('telegram_id')

        st.success(f"أهلاً بك سيد: {res.get('Nom', 'جارنا')} (شقة {apt})")
        st.divider()

        # زر الربط (الجسر)
        if not tg_id:
            st.warning("🔔 حسابك غير مربوط بتلغرام")
            bot_name = bot.get_me().username
            link = f"https://t.me/{bot_name}?start={apt}"
            st.link_button("🚀 تفعيل التنبيهات الآن", link)
        else:
            st.info(f"✅ خدمة التنبيهات مفعلة (ID: {tg_id})")

        # عرض المالية
        c_docs = db.collection("cotisations").stream()
        df_c = pd.DataFrame([d.to_dict() for d in c_docs])
        apt_pays = df_c[df_c['Appart'] == int(apt)] if not df_c.empty else pd.DataFrame()
        total = pd.to_numeric(apt_pays['Montant'], errors='coerce').sum()
        
        valid_date = datetime(2026, 1, 1) + relativedelta(months=int(total // 1000)) - pd.Timedelta(days=1)
        
        c1, c2 = st.columns(2)
        c1.metric("مسوى إلى غاية", valid_date.strftime('%d/%m/%Y'))
        c2.metric("إجمالي الدفع", f"{total:,.0f} DA")
    else:
        st.error("❌ الرقم غير مسجل.")
