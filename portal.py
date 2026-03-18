import streamlit as st
import pandas as pd
from google.cloud import firestore
import telebot
import threading
from datetime import datetime
from dateutil.relativedelta import relativedelta

# --- 1. الإعدادات والاتصال بقاعدة البيانات ---
TOKEN = st.secrets["TELEGRAM_TOKEN"]
ADMIN_ID = st.secrets.get("CHAT_ID")
bot = telebot.TeleBot(TOKEN)

if 'db' not in st.session_state:
    try:
        # تصحيح السطر الذي حدث فيه الخطأ
        creds_info = dict(st.secrets["firebase_key"])
        if "private_key" in creds_info:
            creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
        st.session_state.db = firestore.Client.from_service_account_info(creds_info)
    except Exception as e:
        st.error(f"خطأ في قاعدة البيانات: {e}")
        st.stop()

db = st.session_state.db

# --- 2. محرك البوت في الخلفية (الربط الآلي) ---
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

# --- 3. واجهة بوابة السكان ---
st.set_page_config(page_title="Portal Bloc B", page_icon="🏢")
st.title("🏢 بوابة سكان Bloc B")

phone = st.text_input("أدخل رقم هاتفك المسجل (0XXXXXXXXX):")

if phone:
    # جلب البيانات
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
                try: bot.send_message(ADMIN_ID, f"👤 دخول: {name} (شقة {apt}) يتصفح البوابة.")
                except: pass
            st.session_state.admin_notified = True

        st.success(f"أهلاً بك سيد: {name} (شقة {apt})")

        # --- 4. الحسابات المالية (الترتيب الصحيح) ---
        c_docs = db.collection("cotisations").stream()
        df_cont = pd.DataFrame([d.to_dict() for d in c_docs])
        total = pd.to_numeric(df_cont[df_cont['Appart'] == int(apt)]['Montant'], errors='coerce').sum()
        
        # حساب تاريخ نهاية الصلاحية (بداية من 2026)
        valid_date = datetime(2026, 1, 1) + relativedelta(months=int(total // 1000)) - pd.Timedelta(days=1)
        
        # حساب أشهر التأخير
        diff = relativedelta(datetime.now(), valid_date)
        months_late = diff.months + (12 * diff.years)

        st.divider()
        col1, col2 = st.columns(2)
        col1.metric("مسوى إلى غاية", valid_date.strftime('%d/%m/%Y'))
        col2.metric("إجمالي المدفوعات", f"{total:,.0f} DA")

        # --- 5. نظام التنبيهات والإنذارات ---
        if tg_id and datetime.now() > valid_date:
            if 'alert_sent' not in st.session_state:
                if months_late >= 2:
                    # إنذار الـ 48 ساعة
                    warn_msg = (f"🚨 **إنذار نهائي - شقة {apt}**\n\n"
                                f"لديكم تأخر {months_late} أشهر.\n"
                                f"في حالة عدم التسوية خلال 48 ساعة، سيتم فصل مفاتيحكم آلياً.\n\n"
                                f"شكراً لتفهمكم.")
                    bot.send_message(tg_id, warn_msg, parse_mode="Markdown")
                    if ADMIN_ID: bot.send_message(ADMIN_ID, f"📢 إنذار قطع مرسل لشقة {apt}.")
                    
                    # مؤقت إرسال "تم الفصل" بعد 48 ساعة
                    def final_cutoff():
                        try:
                            bot.send_message(tg_id, f"🚫 **تنبيه إداري: شقة {apt}**\n\nانتهت المهلة ولم يتم التسوية. **لقد تم فصل مفاتيحكم الإلكترونية**. يرجى الاتصال بالإدارة.")
                        except: pass
                    threading.Timer(172800, final_cutoff).start()

                elif months_late >= 1:
                    # تذكير بسيط
                    warn_msg = f"⚠️ **تذكير - شقة {apt}**\n\nتأخرتم بشهر واحد. يرجى تسوية الوضعية لتجنب تراكم الديون."
                    bot.send_message(tg_id, warn_msg, parse_mode="Markdown")
                    if ADMIN_ID: bot.send_message(ADMIN_ID, f"📢 تذكير مرسل لشقة {apt}.")
                
                st.session_state.alert_sent = True

        # زر الربط (يظهر فقط إذا لم يسبق الربط)
        if not tg_id or str(tg_id).lower() in ["none", ""]:
            try:
                bot_info = bot.get_me()
                st.link_button("🚀 تفعيل تنبيهات تلغرام", f"https://t.me/{bot_info.username}?start={apt}")
            except: st.warning("البوت غير متاح حالياً.")

        # سجل الدفعات
        apt_pays = df_cont[df_cont['Appart'] == int(apt)]
        if not apt_pays.empty:
            st.subheader("📋 سجل الدفعات الأخيرة")
            st.table(apt_pays[['Date', 'Montant']].sort_values('Date', ascending=False).head(5))
    else:
        st.error("❌ الرقم غير مسجل في قاعدة البيانات.")
