import streamlit as st
import pandas as pd
from google.cloud import firestore
import telebot
import time
import threading
from datetime import datetime
from dateutil.relativedelta import relativedelta

# --- 1. إعداد الصفحة لـ Streamlit ---
st.set_page_config(page_title="Portal Bloc B", page_icon="🏢")

# --- 2. الإعدادات والاتصال بقاعدة البيانات ---
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

# --- وظيفة ديناميكية لجلب ID أمين المال (صاحب الشقة 27) ---
def get_treasurer_id():
    try:
        doc = db.collection("habitants").document("27").get()
        if doc.exists:
            t_id = doc.to_dict().get('telegram_id')
            if t_id and str(t_id).strip() not in ["", "None", "nan"]:
                return str(t_id)
    except:
        pass
    return None

# --- 3. دالة الإرسال الآمن وآليات البوت والإشعارات المتعددة ---
def safe_send(chat_id, message, apt_info=""):
    if not chat_id: return False
    try:
        bot.send_message(chat_id, message, parse_mode="Markdown")
        return True
    except Exception as e:
        if ADMIN_ID and str(chat_id) != str(ADMIN_ID):
            try: bot.send_message(ADMIN_ID, f"❌ فشل الإرسال لشقة {apt_info}\nالخطأ: {e}")
            except: pass
        return False

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
                safe_send(message.chat.id, msg, apt_info=str(apt_num))
                
                # إشعار إضافي إذا كان الرابط شقة 27 أمين المال
                if str(apt_num) == "27":
                    safe_send(message.chat.id, "👑 أهلاً بك بصفتك **أمين المال** للعمارة، ستصلك الآن تقارير الدفع والمصاريف آلياً هنا.")
                
                if ADMIN_ID:
                    safe_send(ADMIN_ID, f"🔔 **ربط جديد:** الشقة {apt_num} فعلت التلغرام.", apt_info=str(apt_num))
            except: pass
    try:
        bot.remove_webhook()
        bot.polling(none_stop=True, skip_pending_updates=True)
    except:
        time.sleep(5)

if 'bot_thread' not in st.session_state:
    threading.Thread(target=run_bot, daemon=True).start()
    st.session_state.bot_thread = True

# --- 4. محرك الأتمتة الدوري للتنبيهات ---
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
                is_resident = bool(res.get("Resident", True))
                
                sy_val = res.get("StartYear")
                sm_val = res.get("StartMonth")
                s_y = 2026 if pd.isna(sy_val) else int(sy_val)
                s_m = 1 if pd.isna(sm_val) else int(sm_val)

                total = pd.to_numeric(df_cont[df_cont['Appart'] == int(apt)]['Montant'], errors='coerce').sum()
                valid_date = datetime(s_y, s_m, 1) + relativedelta(months=int(total // 1000)) - pd.Timedelta(days=1)
                diff = relativedelta(now, valid_date)
                months_late = diff.months + (12 * diff.years)

                if tg_id and str(tg_id).strip() not in ["", "None", "nan"] and now > valid_date and last_sent != current_month and is_resident:
                    if months_late >= 3:
                        msg = (f"📢 **إنذار نهائي - شقة {apt}**\n\n"
                               f"تأخر في الدفع لمدة {months_late} أشهر. "
                               f"سيتم توقف المصعد آلياً بعد 48 ساعت في حال عدم تسوية مستحقاتكم المعلقة.")
                        if safe_send(tg_id, msg, apt_info=apt):
                            db.collection("habitants").document(apt).update({"last_notice_month": current_month})
                    elif months_late >= 1:
                        msg = f"👋 **تذكير ودي - شقة {apt}**\n\nمرحباً جارنا العزيز، نود تذكيركم بأن مستحقات أعباء العمارة متأخرة بـ {months_late} أشهر. شكراً لتعاونكم المتواصل."
                        if safe_send(tg_id, msg, apt_info=apt):
                            db.collection("habitants").document(apt).update({"last_notice_month": current_month})
        except Exception as e:
            if ADMIN_ID:
                try: bot.send_message(ADMIN_ID, f"⚠️ خطأ تقني في نظام الأتمتة: {e}")
                except: pass
        time.sleep(86400)

if 'auto_run' not in st.session_state:
    threading.Thread(target=automated_monthly_check, daemon=True).start()
    st.session_state.auto_run = True

# --- 5. تصميم الواجهة الرسومية للسكان ---
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
    .hero-title { font-size: 1.4rem; font-weight: 800; margin-bottom: 0.25rem; }
    .hero-subtitle { font-size: 0.95rem; opacity: 0.92; }
    .section-card {
        border: 1px solid #e5e7eb; border-radius: 12px;
        padding: 0.9rem 1rem; background: #ffffff;
        box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
    }
    .metric-card {
        border: 1px solid #e5e7eb; border-radius: 12px;
        padding: 0.9rem 1rem; background: #f8fafc; margin-bottom: 0.4rem;
    }
    .metric-label { font-size: 0.92rem; color: #475569; font-weight: 600; }
    .metric-value-big { font-size: 1.95rem; font-weight: 800; color: #1d4ed8; margin-top: 0.1rem; }
    .metric-value { font-size: 1.2rem; font-weight: 700; margin-top: 0.1rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero-card">
        <div class="hero-title">🏢 بوابة السكان Bloc B</div>
        <div class="hero-subtitle">متابعة الوضعية المالية، التنبيهات، ومصاريف الشهر الحالي بشكل واضح واحترافي.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="section-card">
        <div style="font-size: 0.95rem; font-weight: 700; color: #0f172a; margin-bottom: 0.35rem;">
            📱 أدخل رقم هاتفك المسجل للدخول للبوابة
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

phone = st.text_input("رقم الهاتف", placeholder="مثال: 0555123456", label_visibility="collapsed")

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
            if ADMIN_ID: safe_send(ADMIN_ID, f"👤 **دخول لبوابة السكان:** {name} (شقة {apt})", apt_info=apt)
            st.session_state.admin_notified = True

        st.markdown(
            f"""
            <div class="section-card" style="margin-top: 0.6rem;">
                <div style="font-size: 1rem; font-weight: 700; color: #0f172a;">👋 أهلاً بك: {name} {"(👑 أمين المال)" if apt == "27" else ""}</div>
                <div style="font-size: 0.95rem; color: #475569;">رقم الشقة: <b>{apt}</b></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.subheader("🔔 خدمة التنبيهات التلغرام")
        if not tg_id or str(tg_id).strip() in ["", "None", "nan"]:
            st.warning("⚠️ حسابك غير مرتبط ببوت التنبيهات الحالي.")
            try:
                bot_username = bot.get_me().username
                st.link_button("🚀 تفعيل التنبيهات واستلام الوصولات عبر تلغرام", f"https://t.me/{bot_username}?start={apt}")
            except:
                st.error("فشل الاتصال بالبوت، يرجى المحاولة لاحقاً.")
        else:
            st.success(f"✅ خدمة التنبيهات مفعلة ومرتبطة بحسابك الشخصي.")

        st.divider()
        try:
            c_docs = db.collection("cotisations").stream()
            df_cont = pd.DataFrame([d.to_dict() for d in c_docs])
            total = pd.to_numeric(df_cont[df_cont['Appart'] == int(apt)]['Montant'], errors='coerce').sum()
            
            tarif_mensuel = 1000
            now = datetime.now()
            
            sy_val = res.get("StartYear")
            sm_val = res.get("StartMonth")
            s_y = 2026 if pd.isna(sy_val) else int(sy_val)
            s_m = 1 if pd.isna(sm_val) else int(sm_val)
            
            mois_theoriques = max(0, (now.year - s_y) * 12 + (now.month - s_m))
            montant_theorique = mois_theoriques * tarif_mensuel
            
            dette_override = res.get("DetteOverride", pd.NA)
            dette_precedente = float(dette_override) if not pd.isna(dette_override) else 0.0
            dette_actuelle = max(0, (montant_theorique + dette_precedente) - float(total))
            
            valid_date = datetime(s_y, s_m, 1) + relativedelta(months=int(total // 1000)) - pd.Timedelta(days=1)

            # --- التعديل: حساب مصاريف الشهر الحالي فقط بدلاً من الإجمالي ---
            current_month_prefix = now.strftime("%Y-%m") # جلب السنة والشهر الحالي مثلاً '2026-05'
            try:
                exp_docs = db.collection("depenses").stream()
                df_exp = pd.DataFrame([d.to_dict() for d in exp_docs])
                if not df_exp.empty and 'Date' in df_exp.columns and 'Montant' in df_exp.columns:
                    # تحويل قيم المبالغ لأرقام وتصفية التواريخ حسب الشهر الحالي فقط
                    df_exp['Montant'] = pd.to_numeric(df_exp['Montant'], errors='coerce').fillna(0)
                    monthly_exp_df = df_exp[df_exp['Date'].astype(str).str.startswith(current_month_prefix)]
                    monthly_expenses = monthly_exp_df['Montant'].sum()
                else:
                    monthly_expenses = 0.0
            except:
                monthly_expenses = 0.0

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
                        <div class="metric-label">💳 الدين المستحق حالياً</div>
                        <div class="metric-value" style="color: {'#b91c1c' if dette_actuelle > 0 else '#15803d'}; font-size: 1.5rem;">
                            {dette_actuelle:,.0f} DA
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                
            
        except Exception as e:
            st.error(f"خطأ في معالجة الحسابات المالية: {e}")

        apt_pays = df_cont[df_cont['Appart'] == int(apt)]
        if not apt_pays.empty:
            st.subheader("📋 آخر 5 دفعات مسجلة")
            latest_pays = apt_pays[['Date', 'Montant']].sort_values('Date', ascending=False).head(5).copy()
            latest_pays['Montant'] = pd.to_numeric(latest_pays['Montant'], errors='coerce').fillna(0).map(lambda x: f"{x:,.0f} DA")
            st.dataframe(latest_pays, use_container_width=True, hide_index=True)
    else:
        st.error("❌ عذراً، رقم الهاتف هذا غير مسجل في قاعدة بيانات الساكنين.")
