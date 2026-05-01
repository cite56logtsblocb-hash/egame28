import streamlit as st
import pandas as pd
from google.cloud import firestore
import telebot
import time
import threading
from datetime import datetime
from dateutil.relativedelta import relativedelta

# --- 1. الإعدادات والاتصال ---
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

def notify_payment_success(apt_num, amount):
    try:
        user_doc = db.collection("habitants").document(str(apt_num)).get()
        if user_doc.exists:
            tg_id = user_doc.to_dict().get('telegram_id')
            if tg_id:
                text = (f"✨ **تأكيد استلام دفع**\n\n"
                        f"مرحباً بك جارنا العزيز، نؤكد لكم استلام مبلغ **{amount:,.0f} DA** "
                        f"الخاص بمستحقات الشقة رقم **{apt_num}**.\n\n"
                        f"شكراً لتفهمكم ومساهمتكم في صيانة عمارتنا 🤝")
                bot.send_message(tg_id, text, parse_mode="Markdown")
    except Exception as e:
        print(f"Error: {e}")

# --- 2. محرك البوت (الخلفية) ---
def run_bot():
    @bot.message_handler(commands=['start'])
    def handle_start(message):
        args = message.text.split()
        if len(args) > 1:
            apt_num = args[1]
            try:
                db.collection("habitants").document(str(apt_num)).update({"telegram_id": str(message.chat.id)})
                msg = (f"🌟 **مرحباً بك جارنا العزيز**\n\n"
                       f"لقد تم ربط حسابك ببوابة العمارة بنجاح لشقتكم رقم **({apt_num})**.\n\n"
                       f"من الآن فصاعداً، ستصلكم هنا تنبيهات الاستحقاق، تأكيدات الدفع، وأهم إعلانات لجنة العمارة. 🏢✨")
                safe_send(message.chat.id, msg)
                if ADMIN_ID:
                    safe_send(ADMIN_ID, f"🔔 **ربط جديد:** الشقة {apt_num} فعلت التلغرام.")
            except: pass
    bot.remove_webhook()
    bot.polling(none_stop=True)

if 'bot_thread' not in st.session_state:
    threading.Thread(target=run_bot, daemon=True).start()
    st.session_state.bot_thread = True

# --- دالة الإرسال المطورة ---
def safe_send(chat_id, message, apt_info=""):
    """ترسل الرسالة للساكن وترسل نسخة للأدمن آلياً"""
    if not chat_id: return False
    try:
        # إرسال للساكن
        bot.send_message(chat_id, message, parse_mode="Markdown")
        
        # إعلام الأدمن (أنت) بكل صغيرة وكبيرة
        if ADMIN_ID and str(chat_id) != str(ADMIN_ID):
            report = f"📤 **تقرير الإرسال الآلي:**\n"
            if apt_info: report += f"🏠 الشقة: {apt_info}\n"
            report += f"--- الرسالة المرسلة ---\n{message}"
            bot.send_message(ADMIN_ID, report, parse_mode="Markdown")
            
        return True
    except Exception as e:
        # إذا فشل الإرسال للساكن، أعلم الأدمن بالخطأ
        if ADMIN_ID:
            bot.send_message(ADMIN_ID, f"❌ فشل الإرسال لشقة {apt_info}\nالخطأ: {e}")
        return False

# --- محرك الأتمتة المحدث ---
def automated_monthly_check():
    while True:
        try:
            now = datetime.now()
            current_month = now.strftime("%Y-%m")
            h_docs = db.collection("habitants").stream()
            c_docs = db.collection("cotisations").stream()
            df_cont = pd.DataFrame([d.to_dict() for d in c_docs])
            
            for doc in h_docs:
                res = doc.to_dict()
                apt = str(res.get('Appart'))
                tg_id = res.get('telegram_id')
                last_sent = res.get('last_notice_month', "")

                # حساب المستحقات
                total = pd.to_numeric(df_cont[df_cont['Appart'] == int(apt)]['Montant'], errors='coerce').sum()
                valid_date = datetime(2026, 1, 1) + relativedelta(months=int(total // 1000)) - pd.Timedelta(days=1)
                diff = relativedelta(now, valid_date)
                months_late = diff.months + (12 * diff.years)

                # شرط الإرسال
                if tg_id and now > valid_date and last_sent != current_month:
                    if months_late >= 3:
                        msg = (f"📢 **إنذار نهائي - شقة {apt}**\n\n"
                               f"تأخر في الدفع لمدة {months_late} أشهر. "
                               f"سيتم توقف المصعد آلياً بعد 48 ساعة.")
                        # نمرر رقم الشقة لـ safe_send لكي يعلم الأدمن من استلم
                        if safe_send(tg_id, msg, apt_info=apt):
                            db.collection("habitants").document(apt).update({"last_notice_month": current_month})
                            
                    elif months_late >= 1:
                        msg = f"👋 **تذكير ودي - شقة {apt}**\nالمستحقات متأخرة بـ {months_late} شهر."
                        if safe_send(tg_id, msg, apt_info=apt):
                            db.collection("habitants").document(apt).update({"last_notice_month": current_month})
        except Exception as e:
            if ADMIN_ID: bot.send_message(ADMIN_ID, f"⚠️ خطأ تقني: {e}")
            
        time.sleep(86400) # فحص كل يوم

if 'auto_run' not in st.session_state:
    t = threading.Thread(target=automated_monthly_check, daemon=True)
    t.start()
    st.session_state.auto_run = True
# --- 3. واجهة البوابة ---
st.set_page_config(page_title="Portal Bloc B", page_icon="🏢")
st.markdown(
    """
    <style>
    .hero-card {
        background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 100%);
        border-radius: 14px;
        padding: 1.1rem 1.3rem;
        color: white;
        margin-bottom: 1rem;
        box-shadow: 0 10px 25px rgba(15, 23, 42, 0.2);
    }
    .hero-title {
        font-size: 1.4rem;
        font-weight: 800;
        margin-bottom: 0.25rem;
    }
    .hero-subtitle {
        font-size: 0.95rem;
        opacity: 0.92;
    }
    .section-card {
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 0.9rem 1rem;
        background: #ffffff;
        box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
    }
    .metric-card {
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 0.9rem 1rem;
        background: #f8fafc;
        margin-bottom: 0.4rem;
    }
    .metric-label {
        font-size: 0.92rem;
        color: #475569;
        font-weight: 600;
    }
    .metric-value-big {
        font-size: 1.95rem;
        font-weight: 800;
        color: #1d4ed8;
        margin-top: 0.1rem;
    }
    .metric-value {
        font-size: 1.2rem;
        font-weight: 700;
        margin-top: 0.1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    """
    <div class="hero-card">
        <div class="hero-title">🏢 بوابة السكان Bloc B</div>
        <div class="hero-subtitle">متابعة الوضعية المالية، التنبيهات، وآخر الدفعات بشكل واضح واحترافي.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="section-card">
        <div style="font-size: 0.95rem; font-weight: 700; color: #0f172a; margin-bottom: 0.35rem;">
            📱 ضع رقمك هنا في البوابة
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
phone = st.text_input(
    "رقم الهاتف",
    placeholder="مثال: 0555123456",
    label_visibility="collapsed",
)

if phone:
        h_docs = db.collection("habitants").stream()
        df_hab = pd.DataFrame([d.to_dict() for d in h_docs])
        user_match = df_hab[df_hab['Tel'].astype(str).str.strip() == phone.strip()]

        if not user_match.empty:
            res = user_match.iloc[0]
            apt = str(res['Appart'])
            name = res.get('Nom', 'جارنا العزيز')
            tg_id = res.get('telegram_id')

            if 'admin_notified' not in st.session_state:
                if ADMIN_ID: safe_send(ADMIN_ID, f"👤 **دخول:** {name} (شقة {apt})")
                st.session_state.admin_notified = True

            st.markdown(
                f"""
                <div class="section-card" style="margin-top: 0.6rem;">
                    <div style="font-size: 1rem; font-weight: 700; color: #0f172a;">👋 أهلاً بك: {name}</div>
                    <div style="font-size: 0.95rem; color: #475569;">رقم الشقة: <b>{apt}</b></div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # --- 4. خدمة التنبيهات ---
            st.subheader("🔔 خدمة التنبيهات")
            if not tg_id or str(tg_id).strip() in ["", "None", "nan"]:
                st.warning("⚠️ حسابك غير مرتبط بالتنبيهات.")
                try:
                    bot_username = bot.get_me().username
                    st.link_button("🚀 تفعيل التنبيهات عبر تلغرام", f"https://t.me/{bot_username}?start={apt}")
                except: st.error("فشل الاتصال بالبوت.")
            else:
                st.success(f"✅ خدمة التنبيهات مفعلة.")

            # --- 5. المالية والإنذارات ---
            st.divider()
            try:
                c_docs = db.collection("cotisations").stream()
                df_cont = pd.DataFrame([d.to_dict() for d in c_docs])
                total = pd.to_numeric(df_cont[df_cont['Appart'] == int(apt)]['Montant'], errors='coerce').sum()
                tarif_mensuel = 1000
                now = datetime.now()
                mois_theoriques = max(0, (now.year - 2026) * 12 + (now.month - 1))
                montant_theorique = mois_theoriques * tarif_mensuel
                dette_override = res.get("DetteOverride", pd.NA)
                dette_precedente = float(dette_override) if not pd.isna(dette_override) else 0.0
                dette_actuelle = max(0, (montant_theorique + dette_precedente) - float(total))
                
                valid_date = datetime(2026, 1, 1) + relativedelta(months=int(total // 1000)) - pd.Timedelta(days=1)
                diff = relativedelta(datetime.now(), valid_date)
                months_late = diff.months + (12 * diff.years)

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(
                        f"""
                        <div class="metric-card">
                            <div class="metric-label">📆 مسوى إلى غاية</div>
                            <div class="metric-value-big">{valid_date.strftime('%d/%m/%Y')}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with col2:
                    st.markdown(
                        f"""
                        <div class="metric-card">
                            <div class="metric-label">💳 الدين المسجل عليه</div>
                            <div class="metric-value" style="color: {'#b91c1c' if dette_actuelle > 0 else '#15803d'};">
                                {dette_actuelle:,.0f} DA
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            except Exception as e:
                st.error(f"خطأ: {e}")

            apt_pays = df_cont[df_cont['Appart'] == int(apt)]
            if not apt_pays.empty:
                st.subheader("📋 سجل الدفعات")
                latest_pays = apt_pays[['Date', 'Montant']].sort_values('Date', ascending=False).head(5).copy()
                latest_pays['Montant'] = pd.to_numeric(latest_pays['Montant'], errors='coerce').fillna(0).map(lambda x: f"{x:,.0f} DA")
                st.dataframe(latest_pays, use_container_width=True, hide_index=True)
        else:
            st.error("❌ الرقم غير مسجل.")
