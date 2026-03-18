import streamlit as st
import pandas as pd
from google.cloud import firestore
import telebot
import threading
from datetime import datetime
from dateutil.relativedelta import relativedelta

# --- 1. الإعدادات ---
TOKEN = st.secrets["TELEGRAM_TOKEN"]
ADMIN_ID = st.secrets.get("CHAT_ID")
bot = telebot.TeleBot(TOKEN)

if 'db' not in st.session_state:
    try:
        creds_info = dict(st.secrets["firebase_key"])
        if "private_key" in creds_info:
            creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
        st.session_state.db = firestore.Client.from_service_account_info(creds_info)
    except Exception as e:
        st.error(f"خطأ في قاعدة البيانات: {e}")
        st.stop()

db = st.session_state.db

# دالة آمنة لإرسال الرسائل لتجنب الـ Crash
def safe_send(chat_id, message):
    try:
        bot.send_message(chat_id, message, parse_mode="Markdown")
        return True
    except Exception as e:
        print(f"فشل الإرسال إلى {chat_id}: {e}")
        return False

# --- 2. محرك البوت (الخلفية) ---
def run_bot():
    @bot.message_handler(commands=['start'])
    def handle_start(message):
        args = message.text.split()
        if len(args) > 1:
            apt_num = args[1]
            try:
                db.collection("habitants").document(str(apt_num)).update({"telegram_id": str(message.chat.id)})
                safe_send(message.chat.id, f"✅ تم ربط الشقة {apt_num} بنجاح! ستصلك التنبيهات هنا.")
                if ADMIN_ID:
                    safe_send(ADMIN_ID, f"🔔 ربط جديد: الشقة {apt_num} فعلت التلغرام.")
            except: pass
    bot.remove_webhook()
    bot.polling(none_stop=True)

if 'bot_thread' not in st.session_state:
    threading.Thread(target=run_bot, daemon=True).start()
    st.session_state.bot_thread = True

# --- 3. واجهة بوابة السكان ---
st.set_page_config(page_title="Portal Bloc B", page_icon="🏢")
st.title("🏢 بوابة سكان Bloc B")

phone = st.text_input("أدخل رقم هاتفك المسجل:")

if phone:
    h_docs = db.collection("habitants").stream()
    df_hab = pd.DataFrame([d.to_dict() for d in h_docs])
    user_match = df_hab[df_hab['Tel'].astype(str).str.strip() == phone.strip()]

    if not user_match.empty:
        res = user_match.iloc[0]
        apt = str(res['Appart'])
        name = res.get('Nom', 'جارنا العزيز')
        tg_id = res.get('telegram_id')

        # إشعار دخول للأدمن
        if 'admin_notified' not in st.session_state:
            if ADMIN_ID:
                safe_send(ADMIN_ID, f"👤 دخول: {name} (شقة {apt}) يتصفح البوابة.")
            st.session_state.admin_notified = True

        st.success(f"أهلاً بك سيد: {name} (شقة {apt})")

        # --- 4. الحسابات المالية ---
        c_docs = db.collection("cotisations").stream()
        df_cont = pd.DataFrame([d.to_dict() for d in c_docs])
        total = pd.to_numeric(df_cont[df_cont['Appart'] == int(apt)]['Montant'], errors='coerce').sum()
        
        valid_date = datetime(2026, 1, 1) + relativedelta(months=int(total // 1000)) - pd.Timedelta(days=1)
        diff = relativedelta(datetime.now(), valid_date)
        months_late = diff.months + (12 * diff.years)

        st.divider()
        col1, col2 = st.columns(2)
        col1.metric("وضعية مسواة إلى غاية", valid_date.strftime('%d/%m/%Y'))
        col2.metric("إجمالي المدفوعات", f"{total:,.0f} DA")

        # --- 5. نظام التنبيهات (المحمي بـ safe_send) ---
        if tg_id and datetime.now() > valid_date:
            if 'alert_sent' not in st.session_state:
                if months_late >= 2:
                    warn_msg = (f"🚨 **إنذار نهائي - شقة {apt}**\n\nلديكم تأخر {months_late} أشهر.\n"
                                f"في حالة عدم التسوية خلال 48 ساعة، سيتم فصل مفاتيحكم آلياً.")
                    if safe_send(tg_id, warn_msg):
                        if ADMIN_ID: safe_send(ADMIN_ID, f"📢 إنذار قطع مرسل لشقة {apt}.")
                        
                        def final_cutoff():
                            safe_send(tg_id, f"🚫 **تنبيه إداري: شقة {apt}**\n\nانتهت المهلة. تم فصل المفاتيح.")
                        threading.Timer(172800, final_cutoff).start()
                    else:
                        st.error("⚠️ لم نتمكن من إرسال إنذار التلغرام. هل قمت بحظر البوت؟")

                elif months_late >= 1:
                    warn_msg = f"⚠️ **تذكير - شقة {apt}**\n\nتأخرتم بشهر واحد. يرجى تسوية الوضعية."
                    safe_send(tg_id, warn_msg)
                    if ADMIN_ID: safe_send(ADMIN_ID, f"📢 تذكير مرسل لشقة {apt}.")
                
                st.session_state.alert_sent = True

        # زر الربط
        if not tg_id or str(tg_id).lower() in ["none", ""]:
            try:
                bot_info = bot.get_me()
                st.link_button("🚀 تفعيل تنبيهات تلغرام", f"https://t.me/{bot_info.username}?start={apt}")
            except: pass

        # سجل الدفعات
        apt_pays = df_cont[df_cont['Appart'] == int(apt)]
        if not apt_pays.empty:
            st.subheader("📋 سجل الدفعات الأخيرة")
            st.table(apt_pays[['Date', 'Montant']].sort_values('Date', ascending=False).head(5))
    else:
        st.error("❌ الرقم غير مسجل.")
