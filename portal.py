import streamlit as st
import pandas as pd
from google.cloud import firestore
import telebot
import threading
from datetime import datetime
from dateutil.relativedelta import relativedelta

# --- 1. الإعدادات الأساسية ---
TOKEN = st.secrets["TELEGRAM_TOKEN"]
ADMIN_ID = st.secrets.get("CHAT_ID") # تأكد من وجود CHAT_ID في Secrets الخاص بك
bot = telebot.TeleBot(TOKEN)

if 'db' not in st.session_state:
    creds = dict(st.import streamlit as st
import pandas as pd
from google.cloud import firestore
import telebot
import threading
from datetime import datetime
from dateutil.relativedelta import relativedelta

# --- 1. الإعدادات والاتصال ---
TOKEN = st.secrets["TELEGRAM_TOKEN"]
ADMIN_ID = st.secrets.get("CHAT_ID")
bot = telebot.TeleBot(TOKEN)

if 'db' not in st.session_state:
    creds = dict(st.secrets["firebase_key"])
    if "private_key" in creds:
        creds["private_key"] = creds["private_key"].replace("\\n", "\n")
    st.session_state.db = firestore.Client.from_service_account_info(creds)

db = st.session_state.db

# --- 2. محرك البوت في الخلفية ---
def run_bot():
    @bot.message_handler(commands=['start'])
    def handle_start(message):
        args = message.text.split()
        if len(args) > 1:
            apt_num = args[1]
            try:
                db.collection("habitants").document(str(apt_num)).update({"telegram_id": str(message.chat.id)})
                bot.send_message(message.chat.id, f"✅ تم ربط الشقة {apt_num} بنجاح! ستصلك التنبيهات هنا.")
                if ADMIN_ID:
                    bot.send_message(ADMIN_ID, f"🔔 ربط جديد: الشقة {apt_num} فعلت التلغرام.")
            except: pass
    bot.remove_webhook()
    bot.polling(none_stop=True)

if 'bot_thread' not in st.session_state:
    threading.Thread(target=run_bot, daemon=True).start()
    st.session_state.bot_thread = True

# --- 3. واجهة البوابة ---
st.set_page_config(page_title="Portal Bloc B", page_icon="🏢")
st.title("🏢 بوابة سكان Bloc B")

phone = st.text_input("أدخل رقم هاتفك المسجل:")

if phone:
    h_docs = db.collection("habitants").stream()
    df_h = pd.DataFrame([d.to_dict() for d in h_docs])
    user = df_h[df_h['Tel'].astype(str).str.strip() == phone.strip()]

    if not user.empty:
        res = user.iloc[0]
        apt = str(res['Appart'])
        name = res.get('Nom', 'جارنا')
        tg_id = res.get('telegram_id')

        # إشعار دخول للأدمن (مرة واحدة في الجلسة)
        if 'admin_notified' not in st.session_state:
            if ADMIN_ID:
                try: bot.send_message(ADMIN_ID, f"👤 دخول: {name} (شقة {apt}) يتصفح البوابة.")
                except: pass
            st.session_state.admin_notified = True

        st.success(f"أهلاً بك سيد: {name} (شقة {apt})")

        # --- 4. حساب المالية (الترتيب الصحيح) ---
        c_docs = db.collection("cotisations").stream()
        df_c = pd.DataFrame([d.to_dict() for d in c_docs])
        total = pd.to_numeric(df_c[df_c['Appart'] == int(apt)]['Montant'], errors='coerce').sum()
        
        # إنشاء valid_date أولاً قبل استعمالها
        valid_date = datetime(2026, 1, 1) + relativedelta(months=int(total // 1000)) - pd.Timedelta(days=1)
        
        # حساب أشهر التأخير
        diff = relativedelta(datetime.now(), valid_date)
        months_late = diff.months + (12 * diff.years)

        st.divider()
        col1, col2 = st.columns(2)
        col1.metric("وضعية مسواة إلى غاية", valid_date.strftime('%d/%m/%Y'))
        col2.metric("المجموع المدفوع", f"{total:,.0f} DA")

        # --- 5. نظام التنبيهات الذكي ---
        if tg_id and datetime.now() > valid_date:
            # قفل لمنع تكرار الرسائل في نفس الزيارة
            if 'alert_sent' not in st.session_state:
                if months_late >= 2:
                    warn_msg = (f"🚨 **إنذار نهائي - شقة {apt}**\n\nلديكم تأخر {months_late} أشهر.\n"
                                f"في حالة عدم التسوية خلال 48 ساعة، سيتم فصل مفاتيحكم آلياً.\n\nشكراً لتفهمكم.")
                    bot.send_message(tg_id, warn_msg, parse_mode="Markdown")
                    if ADMIN_ID: bot.send_message(ADMIN_ID, f"📢 إنذار قطع مرسل لشقة {apt}.")
                    
                    # مؤقت الـ 48 ساعة
                    def final_cutoff():
                        bot.send_message(tg_id, f"🚫 **تنبيه: شقة {apt}**\n\nانتهت المهلة، تم فصل المفاتيح. يرجى الاتصال بالإدارة.")
                    threading.Timer(172800, final_cutoff).start()

                elif months_late >= 1:
                    warn_msg = f"⚠️ **تذكير - شقة {apt}**\n\nتأخرتم بشهر واحد. يرجى التسوية لتجنب تراكم الديون."
                    bot.send_message(tg_id, warn_msg, parse_mode="Markdown")
                    if ADMIN_ID: bot.send_message(ADMIN_ID, f"📢 تذكير مرسل لشقة {apt}.")
                
                st.session_state.alert_sent = True

        # زر الربط إذا لم يكن مربوطاً
        if not tg_id or str(tg_id).lower() in ["none", ""]:
            bot_username = bot.get_me().username
            st.link_button("🚀 تفعيل تنبيهات تلغرام", f"https://t.me/{bot_username}?start={apt}")

        if not df_c[df_c['Appart'] == int(apt)].empty:
            st.subheader("📋 سجل الدفعات")
            st.table(df_c[df_c['Appart'] == int(apt)][['Date', 'Montant']].sort_values('Date', ascending=False).head(5))
    else:
        st.error("الرقم غير مسجل.")["firebase_key"])
    if "private_key" in creds:
        creds["private_key"] = creds["private_key"].replace("\\n", "\n")
    st.session_state.db = firestore.Client.from_service_account_info(creds)

db = st.session_state.db

# --- 2. محرك البوت (الخلفية) مع إشعارات للأدمن ---
def run_bot():
    @bot.message_handler(commands=['start'])
    def handle_start(message):
        args = message.text.split()
        if len(args) > 1:
            apt_num = args[1]
            chat_id = message.chat.id
            try:
                # تحديث قاعدة البيانات
                db.collection("habitants").document(str(apt_num)).update({"telegram_id": str(chat_id)})
                
                # رسالة ترحيب للساكن
                welcome = f"✅ **تم الربط بنجاح!**\nمرحباً بك جارنا الساكن في شقة {apt_num}. فعل تنبيهات التلغرام لأن الإشعارات ستصلك هنا."
                bot.send_message(chat_id, welcome, parse_mode="Markdown")
                
                # إشعار للأدمن (أنت)
                if ADMIN_ID:
                    bot.send_message(ADMIN_ID, f"🔔 **ربط جديد:** الشقة {apt_num} قامت بتفعيل التلغرام بنجاح.")
            except:
                bot.send_message(chat_id, "⚠️ خطأ في الربط، يرجى إعادة المحاولة من البوابة.")
    
    bot.remove_webhook()
    bot.polling(none_stop=True)

if 'bot_thread' not in st.session_state:
    threading.Thread(target=run_bot, daemon=True).start()
    st.session_state.bot_thread = True

# --- 3. واجهة البوابة (Streamlit) ---
st.set_page_config(page_title="Portal Bloc B", page_icon="🏢")
st.title("🏢 Portail Bloc B")

phone = st.text_input("أدخل رقم هاتفك المسجل:")

if phone:
    h_docs = db.collection("habitants").stream()
    df_h = pd.DataFrame([d.to_dict() for d in h_docs])
    user = df_h[df_h['Tel'].astype(str).str.strip() == phone.strip()]

    if not user.empty:
        res = user.iloc[0]
        apt = str(res['Appart'])
        name = res.get('Nom', 'جارنا')
        tg_id = res.get('telegram_id')

        # --- إشعار دخول للأدمن (يرسل مرة واحدة في الجلسة) ---
        if 'notified_admin' not in st.session_state:
            if ADMIN_ID:
                try:
                    bot.send_message(ADMIN_ID, f"👤 **دخول للبوابة:** الساكن {name} (شقة {apt}) يتصفح حسابه الآن.")
                    st.session_state.notified_admin = True
                except: pass

        st.success(f"(ة)أهلاً بك سيد: {name} (شقة {apt})")
        
        # رابط البوت
        bot_user = bot.get_me().username
        link = f"https://t.me/{bot_user}?start={apt}"

        if not tg_id or str(tg_id).lower() in ["none", ""]:
            st.warning("🔔 خدمة التنبيهات غير مفعلة.")
            st.link_button("🚀 تفعيل التنبيهات الآن", link)
        else:
            st.info(f"✅ الإشعارات مفعلة (ID: {tg_id})")

        # --- عرض المالية والتنبيهات ---
        diff = relativedelta(datetime.now(), valid_date)
        months_late = diff.months + (12 * diff.years)
        st.divider()
        c_docs = db.collection("cotisations").stream()
        df_c = pd.DataFrame([d.to_dict() for d in c_docs])
        total = pd.to_numeric(df_c[df_c['Appart'] == int(apt)]['Montant'], errors='coerce').sum()
        
        valid_date = datetime(2026, 1, 1) + relativedelta(months=int(total // 1000)) - pd.Timedelta(days=1)
        
        col1, col2 = st.columns(2)
        col1.metric("وضعية مسواة إلى غاية", valid_date.strftime('%d/%m/%Y'))
        col2.metric("المجموع", f"{total:,.0f} DA")

        # --- إرسال تنبيهات تحذيرية (للساكن وللأدمن) ---
        if tg_id and datetime.now() > valid_date:
            diff = relativedelta(datetime.now(), valid_date)
            months_late = diff.months + (12 * diff.years)
            
            if months_late >= 2:
    # التنبيه الخطير (شهرين فما فوق)
                warn_msg = (
                    f"🚨 **إنذار نهائي - شقة {apt}**\n\n"
                    f"لديكم تأخر في الدفع قدره **{months_late} أشهر**.\n"
                    f"في حالة عدم التسوية خلال الـ 48 ساعة القادمة، سيتم **فصل مفاتيحكم الإلكترونية آلياً**.\n\n"
                    f"شكراً على تفهمكم. 🙏"
               )
    # نبعث للساكن والأدمن
                bot.send_message(tg_id, warn_msg, parse_mode="Markdown")
                if ADMIN_ID:
                    bot.send_message(ADMIN_ID, f"📢 **تم إرسال إنذار قطع:** شقة {apt} متأخرة بـ {months_late} شهر.")

            elif months_late >= 1:
    # التنبيه العادي (شهر واحد فقط)
                warn_msg = f"⚠️ **تذكير بالدفع - شقة {apt}**\n\nلديكم تأخر في المساهمة قدره **شهر واحد**. يرجى تسوية الوضعية لتجنب تراكم الديون. 🙏"
    # نبعث للساكن والأدمن
                bot.send_message(tg_id, warn_msg, parse_mode="Markdown")
                if ADMIN_ID:
                    bot.send_message(ADMIN_ID, f"📢 **تم إرسال تذكير:** شقة {apt} متأخرة بشهر واحد.")

        if not df_c[df_c['Appart'] == int(apt)].empty:
            st.subheader("📋 سجل الدفعات")
            st.table(df_c[df_c['Appart'] == int(apt)][['Date', 'Montant']].sort_values('Date', ascending=False).head(5))
    else:
        st.error("الرقم غير مسجل.")
