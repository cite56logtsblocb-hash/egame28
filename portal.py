def automated_monthly_check():
    while True:
        try:
            now = datetime.now()
            current_month = now.strftime("%Y-%m")
            
            h_docs = db.collection("habitants").stream()
            c_docs = db.collection("cotisations").stream()
            df_cont = pd.DataFrame([d.to_dict() for d in c_docs])
            
            all_debtors = [] 

            for doc in h_docs:
                res = doc.to_dict()
                apt = str(res.get('Appart'))
                tg_id = res.get('telegram_id')
                last_sent = res.get('last_notice_month', "")
                is_resident = bool(res.get("Resident", True))
                
                # حساب الديون (المنطق تاعك)
                sy_val = res.get("StartYear")
                sm_val = res.get("StartMonth")
                s_y = 2026 if pd.isna(sy_val) else int(sy_val)
                s_m = 1 if pd.isna(sm_val) else int(sm_val)
                
                if not df_cont.empty and 'Appart' in df_cont.columns:
                    total = pd.to_numeric(df_cont[df_cont['Appart'] == int(apt)]['Montant'], errors='coerce').sum()
                else:
                    total = 0
                
                valid_date = datetime(s_y, s_m, 1) + relativedelta(months=int(total // 1000)) - pd.Timedelta(days=1)
                diff = relativedelta(now, valid_date)
                months_late = diff.months + (12 * diff.years)

                if now > valid_date and is_resident:
                    if months_late > 0:
                        all_debtors.append(f"🏠 شقة {apt} ⬅️ متأخر بـ {months_late} شهر")

                    # إرسال الخاص إذا لم يتم الإرسال هذا الشهر
                    if tg_id and str(tg_id).strip() not in ["", "None", "nan"] and last_sent != current_month:
                        msg = f"🔔 **تذكير بالديون - شقة {apt}**\n\nجارنا العزيز، نذكركم بمتأخرات أعباء العمارة: {months_late} أشهر."
                        if safe_send(tg_id, msg):
                            db.collection("habitants").document(apt).update({"last_notice_month": current_month})

            # --- إرسال القائمة للمجموعة (يوم 1 في الشهر) ---
            config_ref = db.collection("settings").document("notifications")
            config = config_ref.get().to_dict() or {}
            
            if now.day == 1 and config.get("last_group_report") != current_month:
                if all_debtors:
                    report_msg = f"📋 **قائمة الديون المعلقة - {now.strftime('%m/%Y')}**\n"
                    report_msg += "________________________\n\n"
                    report_msg += "\n".join(all_debtors)
                    report_msg += "\n\n⚠️ يرجى تسوية المستحقات. شكراً."
                    
                    if safe_send(GROUP_CHAT_ID, report_msg):
                        config_ref.set({"last_group_report": current_month}, merge=True)

        except Exception as e:
            if ADMIN_ID:
                try: bot.send_message(ADMIN_ID, f"⚠️ خطأ في سكريبت الأتمتة: {e}")
                except: pass
        
        time.sleep(3600) # فحص كل ساعة
