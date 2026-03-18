import streamlit as st
import pandas as pd
from google.cloud import firestore
import requests
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta

# --- 1. إعدادات الصفحة ---
st.set_page_config(page_title="بوابة السكان - Bloc B", page_icon="🏢", layout="centered")

# تنسيق CSS بسيط لتحسين المظهر
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 8px; background-color: #007bff; color: white; }
    .status-box { padding: 20px; border-radius: 10px; border: 1px solid #ddd; background-color: #f9f9f9; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. دالة إرسال التلغرام (المحرك) ---
def send_telegram(msg, chat_id):
    if not chat_id: return
    try:
        token = st.secrets["TELEGRAM_TOKEN"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    except:
        return False

# --- 3. الاتصال بقاعدة البيانات ---
if 'db' not in st.session_state:
    try:
        creds = dict(st.secrets["firebase_key"])
        if "private_key" in creds:
            creds["private_key"] = creds["private_key"].replace("\\n", "\n")
        st.session_state.db = firestore.Client.from_service_account_info(creds)
    except Exception as e:
        st.error(f"❌ فشل الاتصال بقاعدة البيانات: {e}")
        st.stop()

db = st.session_state.db

# --- 4. جلب البيانات ---
@st.cache_data(ttl=5)
def load_portal_data():
    try:
        h_docs = db.collection("habitants").stream()
        df_h = pd.DataFrame([d.to_dict() for d in h_docs])
        c_docs = db.collection("cotisations").stream()
        df_c = pd.DataFrame([d.to_dict() for d in c_docs])
        return df_h, df_c
    except:
        return pd.DataFrame(), pd.DataFrame()

df_hab, df_cont = load_portal_data()

# --- 5. واجهة تسجيل الدخول ---
st.title("🏢 بوابة سكان Bloc B")
phone_input = st.text_input("أدخل رقم هاتفك المسجل:", placeholder="0XXXXXXXXX")

if phone_input:
    # البحث عن الساكن عبر رقم الهاتف
    user_row = df_hab[df_hab['Tel'].astype(str).str.strip() == phone_input.strip()]

    if not user_row.empty:
        res_info = user_row.iloc[0]
        # ملاحظة: نفترض أن ID الوثيقة في Firestore هو رقم الشقة
        apt_id = str(res_info['Appart'])
        res_name = res_info.get('Nom', 'جارنا العزيز')
        saved_tg_id = res_info.get('telegram_id')

        st.success(f"✅ أهلاً بك {res_name} (شقة {apt_id})")

        # --- 6. نظام الربط (الجسر) ---
        if not saved_tg_id or str(saved_tg_id).strip() == "" or saved_tg_id == "None":
            with st.container():
                st.subheader("🔗 ربط التنبيهات بهاتفك")
                st.write("للحصول على وصولات الدفع والإشعارات فوراً، اتبع الخطوات:")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.info("1️⃣ ادخل لبوت المشروع واضغط **START**")
                    # استبدل YOUR_BOT_USERNAME باسم يوزر بوتك الحقيقي
                    st.link_button("افتح البوت هنا", "https://t.me/bloc_b_notifier_bot") 
                
                with col2:
                    st.info("2️⃣ احصل على ID الخاص بك")
                    st.link_button("اضغط لجلب ID", "https://t.me/userinfobot")

                new_id = st.text_input("3️⃣ أدخل رقم الـ ID المحصل عليه هنا:")
                
                if st.button("حفظ وإرسال ترحيب"):
                    if new_id.isdigit():
                        try:
                            # التحديث في Firestore (تأكد أن اسم الوثيقة هو رقم الشقة)
                            db.collection("habitants").document(apt_id).set({"telegram_id": str(new_id)}, merge=True)
                            
                            # إرسال رسالة الترحيب
                            welcome_msg = (
                                f"🎊 **تم تفعيل خدمة التنبيهات بنجاح!**\n\n"
                                f"مرحباً بك {res_name} (شقة {apt_id}).\n"
                                f"سوف تستلم كل إشعارات الدفع والإنذارات هنا بصفة آلية. 🏢"
                            )
                            
                            if send_telegram(welcome_msg, new_id):
                                st.success("🎉 تم الربط بنجاح! تفقد تلغرام الآن.")
                                st.balloons()
                                time.sleep(3)
                                st.rerun()
                            else:
                                st.error("❌ تم حفظ الرقم ولكن البوت لم يستطع مراسلتك. هل ضغطت START في بوت المشروع؟")
                        except Exception as e:
                            st.error(f"خطأ في الحفظ: {e}")
                    else:
                        st.warning("الرجاء إدخال رقم ID صحيح.")
        else:
            st.caption(f"🔔 حسابك مربوط حالياً بالتلغرام (ID: {saved_tg_id})")

        # --- 7. عرض الوضعية المالية ---
        st.divider()
        apt_pays = df_cont[df_cont['Appart'] == int(apt_id)] if not df_cont.empty else pd.DataFrame()
        total_paid = pd.to_numeric(apt_pays['Montant'], errors='coerce').sum()
        
        # حساب التاريخ (البداية جانفي 2026)
        start_date = datetime(2026, 1, 1)
        valid_until = start_date + relativedelta(months=int(total_paid // 1000)) - pd.Timedelta(days=1)
        
        c1, c2 = st.columns(2)
        c1.metric("مسوى إلى غاية", valid_until.strftime('%d/%m/%Y'))
        c2.metric("إجمالي الدفعات", f"{total_paid:,.0f} DA")

        # إرسال تنبيه آلي إذا كان هناك تأخير
        if saved_tg_id and datetime.now() > valid_until:
             diff = relativedelta(datetime.now(), valid_until)
             months_late = diff.months + (12 * diff.years)
             if months_late >= 1:
                 alert = f"⚠️ **تنبيه وضعية:** شقة {apt_id}، لديكم تأخر في المساهمات لمدة {months_late} شهر. يرجى التسوية."
                 send_telegram(alert, saved_tg_id)

        if not apt_pays.empty:
            st.subheader("📋 سجل الدفعات")
            st.table(apt_pays[['Date', 'Montant']].sort_values('Date', ascending=False).head(5))

    else:
        st.error("❌ هذا الرقم غير مسجل. يرجى الاتصال بالأدمن.")
else:
    st.info("💡 أدخل رقم هاتفك للبدء.")
