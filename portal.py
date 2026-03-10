import streamlit as st
import pandas as pd
from google.cloud import firestore
import requests
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# 1. إعداد الصفحة
st.set_page_config(page_title="Portail Bloc B", page_icon="🏢")

# --- 2. دالة إرسال الإشعارات ---
def send_telegram(msg):
    try:
        token = st.secrets["TELEGRAM_TOKEN"]
        chat_id = st.secrets["CHAT_ID"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, params={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})
    except:
        pass

# --- 3. دالة المراقبة الأوتوماتيكية (تعمل في الخلفية) ---
def run_auto_watcher(df_hab, df_cont):
    # الفحص لمرة واحدة في كل جلسة عمل لتجنب تكرار الرسائل
    if 'last_check' not in st.session_state:
        today = datetime.now().date()
        for _, row in df_hab.iterrows():
            is_resident = str(row.get('Resident', True)).lower() not in ['false', '0', 'no']
            if not is_resident: continue
            
            apt_num = row['Appart']
            apt_pays = df_cont[df_cont['Appart'] == apt_num] if not df_cont.empty else pd.DataFrame()
            total_paid = pd.to_numeric(apt_pays['Montant'], errors='coerce').sum() if not apt_pays.empty else 0
            
            start_y = int(row.get('StartYear', 2025)) if pd.notna(row.get('StartYear')) else 2025
            final_date = (datetime(start_y, 12, 31) + relativedelta(months=int(total_paid // 1000))).date()

            if today == (final_date - timedelta(days=2)):
                send_telegram(f"🔔 **تنبيه 48 ساعة**\nالشقة: {apt_num}\nالساكن: {row['Nom']}\n⚠️ متبقي يومان على انقضاء المساهمة.")
            elif today == final_date:
                send_telegram(f"🚨 **تنبيه انتهاء**\nالشقة: {apt_num}\nالساكن: {row['Nom']}\n❌ انتهت مدة المساهمة اليوم.")
        st.session_state.last_check = today

# --- 4. جلب البيانات ---
@st.cache_data(ttl=60)
def load_data():
    try:
        db = st.session_state.db
        h_docs = db.collection("habitants").stream()
        df_h = pd.DataFrame([d.to_dict() for d in h_docs])
        c_docs = db.collection("cotisations").stream()
        df_c = pd.DataFrame([d.to_dict() for d in c_docs])
        return df_h, df_c
    except:
        return pd.DataFrame(), pd.DataFrame()

# --- 5. الاتصال بـ Firebase ---
if 'db' not in st.session_state:
    try:
        key_dict = dict(st.secrets["firebase_key"])
        st.session_state.db = firestore.Client.from_service_account_info(key_dict)
    except Exception as e:
        st.error("❌ خطأ في الاتصال بقاعدة البيانات")
        st.stop()

df_hab, df_cont = load_data()

# --- 6. واجهة المستخدم ---
st.title("🏢 Portail Bloc B")
st.markdown("---")

if not df_hab.empty:
    # تشغيل المراقبة الأوتوماتيكية في الخلفية
    run_auto_watcher(df_hab, df_cont)

    # ترتيب الطوابق
    floor_mapping = {
        61: "الطابق 1", 62: "الطابق 1", 63: "الطابق 1", 64: "الطابق 1",
        23: "الطابق 2", 24: "الطابق 2", 65: "الطابق 2", 66: "الطابق 2",
        25: "الطابق 3", 26: "الطابق 3", 27: "الطابق 3", 28: "الطابق 3",
        29: "الطابق 4", 30: "الطابق 4", 31: "الطابق 4", 32: "الطابق 4",
        33: "الطابق 5", 34: "الطابق 5", 35: "الطابق 5", 36: "الطابق 5",
        37: "الطابق 6", 38: "الطابق 6", 39: "الطابق 6", 40: "الطابق 6",
        41: "الطابق 7", 42: "الطابق 7", 43: "الطابق 7", 44: "الطابق 7"
    }
    floor_order = [61, 62, 63, 64, 23, 24, 65, 66, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44]
    available_apts = [apt for apt in floor_order if apt in df_hab['Appart'].unique()]

    # --- الحل لمشكلة الاختيار التلقائي ---
    # إضافة خيار "اختر شقتك" في البداية
    options = [None] + available_apts
    
    def format_func(option):
        if option is None:
            return "--- اختر رقم شقتك من هنا ---"
        return f"الشقة {option} - ({floor_mapping.get(option, '---')})"

    selected_apt = st.selectbox("🏠 رقم الشقة:", options=options, format_func=format_func)

    # لن يعمل هذا الكود إلا إذا قام المستخدم باختيار رقم شقة حقيقي (ليس None)
    if selected_apt is not None:
        res_info = df_hab[df_hab['Appart'] == selected_apt].iloc[0]
        res_name = res_info.get('Nom', '---')
        
        # إشعار الدخول (يرسل فقط عند الاختيار الفعلي)
        send_telegram(f"👤 دخول للبوابة: الشقة {selected_apt} ({res_name})")
        
        st.info(f"👤 الساكن: **{res_name}**")
        # --- زر ربط التلغرام للجار ---
        bot_username = "bloc_b_notifier_bot" # مثلا bloc_b_bot https://t.me/bloc_b_notifier_bot
        telegram_link = f"https://t.me/{bot_username}?start={selected_apt}"

        st.write("🔔 **هل تريد استلام تنبيهات الدفع على هاتفك؟**")
        st.link_button("اضغط هنا لتفعيل الإشعارات", telegram_link)
        
        # فحص حالة الإقامة
        is_resident = str(res_info.get('Resident', True)).lower() not in ['false', '0', 'no']
        if not is_resident:
            st.warning("⚠️ **إشعار:** هذه الشقة مصنفة (غير مقيمة). الساكن معفى من المساهمات الشهرية.")
        else:
            apt_pays = df_cont[df_cont['Appart'] == selected_apt] if not df_cont.empty else pd.DataFrame()
            total_paid = pd.to_numeric(apt_pays['Montant'], errors='coerce').sum() if not apt_pays.empty else 0
            
            start_y = int(res_info.get('StartYear', 2025)) if pd.notna(res_info.get('StartYear')) else 2025
            final_date = (datetime(start_y, 12, 31) + relativedelta(months=int(total_paid // 1000)))
            
            st.success(f"✅ الوضعية مسواة إلى غاية: **{final_date.strftime('%d/%m/%Y')}**")
            st.metric("إجمالي المبالغ المدفوعة", f"{total_paid:,.0f} DA")

            if not apt_pays.empty:
                st.divider()
                st.subheader("📋 سجل آخر المدفوعات")
                st.table(apt_pays[['Date', 'Montant']].sort_values('Date', ascending=False).head(5))
