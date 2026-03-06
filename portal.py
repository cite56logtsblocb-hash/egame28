import streamlit as st
import json
from google.cloud import firestore

# قراءة البيانات من Secrets
if 'db' not in st.session_state:
    try:
        # تحويل النص من Secrets إلى قاموس بايثون
        key_dict = json.loads(st.secrets["firebase_key"])
        st.session_state.db = firestore.Client.from_service_account_info(key_dict)
    except Exception as e:
        st.error(f"❌ مشكلة في التوصيل: {e}")
        st.stop()

db = st.session_state.db

# حماية التطبيق بكلمة السر
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 دخول الإدارة")
    user_pwd = st.text_input("كلمة المرور", type="password")
    if st.button("دخول"):
        if user_pwd == st.secrets["admin_password"]:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("كلمة المرور خاطئة")
    st.stop()
