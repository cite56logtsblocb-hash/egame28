import streamlit as st
import pandas as pd
from google.cloud import firestore
import json
import os

# 1. إعداد الصفحة
st.set_page_config(page_title="Portail Bloc B", page_icon="🏢")

# 2. منطق الاتصال المرن (يعمل في البيسي وفي الهاتف)
if 'db' not in st.session_state:
    try:
        # الحالة 1: إذا كنت في "البيسي" (يبحث عن ملف JSON بجانب الكود)
        # استبدل 'serviceAccountKey.json' باسم ملفك الحقيقي إذا كان مختلفاً
        key_path = "serviceAccountKey.json" 
        
        if os.path.exists(key_path):
            st.session_state.db = firestore.Client.from_service_account_info(json.load(open(key_path)))
        
        # الحالة 2: إذا كنت في "الهاتف/Cloud" (يبحث في Secrets)
        elif "firebase_key" in st.secrets:
            key_dict = json.loads(st.secrets["firebase_key"])
            st.session_state.db = firestore.Client.from_service_account_info(key_dict)
            
        else:
            st.error("❌ لم يتم العثور على مفتاح الاتصال (لا ملف JSON ولا Secrets)")
            st.stop()
    except Exception as e:
        st.error(f"❌ فشل الاتصال: {e}")
        st.stop()

db = st.session_state.db
