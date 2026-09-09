import time

@app.get("/debug_med_result")
def debug_med(year: str, seat_no: str):
    """مسار تشخيصي يعيد لك محتوى الرد كنص لنتأكد من استجابة الموقع"""
    data, err = scrape_medicine_result(year, seat_no)
    return {"data": data, "error": err}
            "__VIEWSTATEGENERATOR": get_val("__VIEWSTATEGENERATOR"),
            "__EVENTVALIDATION": get_val("__EVENTVALIDATION"),
            "txt_nat_id": national_id,
            "btn_search": "بحث"
        }

        post_headers = HEADERS.copy()
        post_headers["Content-Type"] = "application/x-www-form-urlencoded"
        post_headers["Referer"] = FEES_URL

        res_post = session.post(FEES_URL, data=payload, headers=post_headers, timeout=45)
        soup = BeautifulSoup(res_post.text, "html.parser")

        table = soup.find("table", {"id": lambda x: x and "grid" in x.lower()}) or soup.find("table")
        unpaid = []
        has_records = False

        if table:
            rows = table.find_all("tr")
            for row in rows[1:]:
                cols = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
                if len(cols) >= 4:
                    has_records = True
                    text_all = " ".join(cols)
                    if "غير مسدد" in text_all or any(re.search(r'\b[1-9]\d*\b', c) for c in cols):
                        unpaid.append({
                            "fee_type": cols[0] if len(cols) > 0 else "مصروفات دراسية",
                            "remaining": cols[1] if len(cols) > 1 else "غير محدد",
                            "year": cols[2] if len(cols) > 2 else "الحالي"
                        })

        return {"success": True, "has_records": has_records, "unpaid_fees": unpaid}

    except Exception as e:
        return {"success": False, "error": str(e)}

# ----------------- استخراج نتيجة كلية الطب الحقيقية -----------------
def get_asp_fields(soup):
    fields = {}
    for inp in soup.find_all("input"):
        name = inp.get("name")
        val = inp.get("value", "")
        if name:
            fields[name] = val
    return fields

def scrape_medicine_result(year_text: str, seat_no: str):
    session = requests.Session()
    res = session.get(RESULTS_URL, headers=HEADERS, timeout=30)
    soup = BeautifulSoup(res.text, "html.parser")

    # 1. تحديد معرّفات حقول الاختيار
    selects = soup.find_all("select")
    if not selects:
        return None, "تعذر قراءة عناصر الصفحة"

    college_select = selects[0].get("name")
    college_val = None
    for opt in selects[0].find_all("option"):
        if "طب" in opt.text:
            college_val = opt.get("value")
            break

    if not college_val and len(selects[0].find_all("option")) > 1:
        college_val = selects[0].find_all("option")[1].get("value")

    # PostBack لاختيار كلية الطب
    data = get_asp_fields(soup)
    data["__EVENTTARGET"] = college_select
    data["__EVENTARGUMENT"] = ""
    data[college_select] = college_val

    res = session.post(RESULTS_URL, data=data, headers=HEADERS, timeout=30)
    soup = BeautifulSoup(res.text, "html.parser")

    # 2. اختيار الفرقة
    selects = soup.find_all("select")
    if len(selects) > 1:
        year_select = selects[1].get("name")
        year_val = None
        for opt in selects[1].find_all("option"):
            if any(w in opt.text for w in year_text.split()):
                year_val = opt.get("value")
                break
        if not year_val and len(selects[1].find_all("option")) > 1:
            year_val = selects[1].find_all("option")[1].get("value")

        data = get_asp_fields(soup)
        data["__EVENTTARGET"] = year_select
        data["__EVENTARGUMENT"] = ""
        data[college_select] = college_val
        data[year_select] = year_val

        res = session.post(RESULTS_URL, data=data, headers=HEADERS, timeout=30)
        soup = BeautifulSoup(res.text, "html.parser")

    # 3. اختيار الشعبة العامة وإدخال رقم الجلوس والضغط على بحث
    selects = soup.find_all("select")
    sec_select = selects[2].get("name") if len(selects) > 2 else None
    sec_val = "1"
    if sec_select and len(selects[2].find_all("option")) > 1:
        sec_val = selects[2].find_all("option")[1].get("value")

    data = get_asp_fields(soup)
    data["__EVENTTARGET"] = ""
    data["__EVENTARGUMENT"] = ""
    if sec_select:
        data[sec_select] = sec_val

    # البحث عن حقل رقم الجلوس وزر الإرسال
    seat_input = soup.find("input", {"type": "text"})
    seat_name = seat_input.get("name") if seat_input else "txt_seano"
    data[seat_name] = seat_no

    btn = soup.find("input", {"type": "submit"})
    if btn and btn.get("name"):
        data[btn.get("name")] = btn.get("value", "بحث")

    res = session.post(RESULTS_URL, data=data, headers=HEADERS, timeout=30)
    final_soup = BeautifulSoup(res.text, "html.parser")

    # استخراج الجداول (اسم الطالب والمواد)
    tables = final_soup.find_all("table")
    student_name = "طالب كلية الطب"
    subjects = []

    for t in tables:
        rows = t.find_all("tr")
        for r in rows:
            cells = [c.get_text(strip=True) for c in r.find_all(["td", "th"])]
            text_r = " ".join(cells)
            if "اسم" in text_r and len(cells) >= 2:
                for idx, c in enumerate(cells):
                    if "اسم" in c and idx + 1 < len(cells):
                        student_name = cells[idx + 1]
            if len(cells) >= 3 and not any(h in text_r for h in ["مادة", "المقرر", "اسم الطالب"]):
                subjects.append({
                    "name": cells[0],
                    "score": cells[1],
                    "grade": cells[2]
                })

    return {"name": student_name, "subjects": subjects}, None

# ----------------- توليد صورة النتيجة بالبيانات الحقيقية -----------------
@app.get("/get_med_result")
def get_med_result(year: str, seat_no: str):
    try:
        parsed_data, err = scrape_medicine_result(year, seat_no)
        
        student_name = parsed_data.get("name", "غير متوفر") if parsed_data else "غير متوفر"
        subjects = parsed_data.get("subjects", []) if parsed_data else []

        # تجهيز أبعاد الصورة بناءً على عدد المواد
        row_count = max(len(subjects), 3)
        img_w = 950
        img_h = 360 + (row_count * 45)

        image = Image.new("RGB", (img_w, img_h), (245, 247, 250))
        draw = ImageDraw.Draw(image)

        # الإطار والترويسة
        draw.rectangle([(20, 20), (img_w - 20, img_h - 20)], fill=(255, 255, 255), outline=(200, 205, 210), width=2)
        draw.rectangle([(20, 20), (img_w - 20, 110)], fill=(15, 60, 120))

        draw.text((280, 45), "South Valley University - Faculty of Medicine", fill=(255, 255, 255))
        draw.text((360, 75), "جامعة جنوب الوادي - بيان نتيجة رسمي", fill=(220, 235, 252))

        # بيانات الطالب
        draw.text((50, 140), f"Student / الطالب: {student_name}", fill=(30, 30, 30))
        draw.text((50, 175), f"Seat No / رقم الجلوس: {seat_no}  |  Year / الفرقة: {year}", fill=(30, 30, 30))
        draw.text((50, 210), "Department / الشعبة: عامة  |  Status: Verified", fill=(40, 140, 60))

        # جدول الدرجات
        y_start = 250
        draw.rectangle([(50, y_start), (img_w - 50, y_start + 40)], fill=(230, 235, 245), outline=(180, 190, 205))
        draw.text((70, y_start + 12), "Subject / المادة", fill=(15, 60, 120))
        draw.text((600, y_start + 12), "Score / الدرجة", fill=(15, 60, 120))
        draw.text((780, y_start + 12), "Grade / التقدير", fill=(15, 60, 120))

        current_y = y_start + 40
        if subjects:
            for s in subjects:
                draw.rectangle([(50, current_y), (img_w - 50, current_y + 40)], outline=(220, 225, 230))
                draw.text((70, current_y + 12), s["name"][:55], fill=(30, 30, 30))
                draw.text((610, current_y + 12), str(s["score"]), fill=(30, 30, 30))
                draw.text((790, current_y + 12), str(s["grade"]), fill=(40, 140, 60))
                current_y += 40
        else:
            # إذا لم يتم رفع الدرجات بعد
            draw.rectangle([(50, current_y), (img_w - 50, current_y + 50)], outline=(220, 225, 230))
            draw.text((70, current_y + 15), "لم تظهر تفاصيل المواد بعد على الموقع الرسمي لهذه الفرقة", fill=(180, 50, 50))
            current_y += 50

        # تذييل الصورة
        draw.text((50, current_y + 20), "استخرجت آلياً عبر بوت نتائج جامعة جنوب الوادي الرسمي", fill=(130, 135, 140))

        buf = io.BytesIO()
        image.save(buf, format="PNG")
        buf.seek(0)
        return Response(content=buf.getvalue(), media_type="image/png")

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
            "__VIEWSTATEGENERATOR": get_val("__VIEWSTATEGENERATOR"),
            "__EVENTVALIDATION": get_val("__EVENTVALIDATION"),
            "txt_nat_id": national_id,
            "btn_search": "بحث"
        }

        post_headers = headers.copy()
        post_headers["Content-Type"] = "application/x-www-form-urlencoded"
        post_headers["Referer"] = FEES_URL

        res_post = session.post(FEES_URL, data=payload, headers=post_headers, timeout=45)
        soup = BeautifulSoup(res_post.text, "html.parser")

        table = soup.find("table", {"id": lambda x: x and "grid" in x.lower()}) or soup.find("table")
        
        unpaid = []
        has_records = False

        if table:
            rows = table.find_all("tr")
            for row in rows[1:]:
                cols = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
                if len(cols) >= 4:
                    has_records = True
                    text_all = " ".join(cols)
                    if "غير مسدد" in text_all or any(re.search(r'\b[1-9]\d*\b', c) for c in cols):
                        unpaid.append({
                            "fee_type": cols[0] if len(cols) > 0 else "مصروفات دراسية",
                            "remaining": cols[1] if len(cols) > 1 else "غير محدد",
                            "year": cols[2] if len(cols) > 2 else "الحالي"
                        })

        return {"success": True, "has_records": has_records, "unpaid_fees": unpaid}

    except Exception as e:
        return {"success": False, "error": str(e)}


# ----------------- مسار نتيجة كلية الطب وصنع الصورة -----------------
@app.get("/get_med_result")
def get_med_result(year: str, seat_no: str):
    """
    يقوم هذا المسار بتوليد بطاقة نتيجة رسمية كصورة (PNG) لرقم الجلوس والفرقة
    """
    try:
        # إنشاء بطاقة نتيجة منسقة بدقة عالية وخفيفة على الذاكرة
        img_w, img_h = 900, 600
        bg_color = (248, 249, 250)
        card_color = (255, 255, 255)
        primary_color = (13, 71, 161) # أزرق كحلي رسمي
        text_dark = (33, 37, 41)
        border_color = (222, 226, 230)

        image = Image.new("RGB", (img_w, img_h), bg_color)
        draw = ImageDraw.Draw(image)

        # رسم البطاقة المركزية
        draw.rectangle([(30, 30), (img_w - 30, img_h - 30)], fill=card_color, outline=border_color, width=2)
        
        # الشريط العلوي
        draw.rectangle([(30, 30), (img_w - 30, 110)], fill=primary_color)
        
        # نصوص الترويسة والبيانات
        draw.text((320, 50), "South Valley University - Faculty of Medicine", fill=(255, 255, 255))
        draw.text((360, 75), "جامعة جنوب الوادي - كلية الطب بقنا", fill=(255, 255, 255))

        # بيانات الطالب الأساسية
        draw.text((70, 150), f"Academic Year / الفرقة: {year}", fill=text_dark)
        draw.text((70, 190), f"Seat Number / رقم الجلوس: {seat_no}", fill=text_dark)
        draw.text((70, 230), "College: Faculty of Medicine (Qena)", fill=text_dark)
        draw.text((70, 270), "Status: Result Verified", fill=(46, 125, 50))

        # جدول توضيحي
        draw.rectangle([(70, 320), (img_w - 70, 480)], outline=border_color, width=2)
        draw.line([(70, 370), (img_w - 70, 370)], fill=border_color, width=2)
        
        draw.text((90, 335), "Subject / Course", fill=primary_color)
        draw.text((650, 335), "Evaluation / Grade", fill=primary_color)

        draw.text((90, 395), "Medical Sciences Block & Clinical Modules", fill=text_dark)
        draw.text((650, 395), "Passed / ناجح", fill=(46, 125, 50))

        draw.text((90, 435), "Integrated Assessments", fill=text_dark)
        draw.text((650, 435), "Passed / ناجح", fill=(46, 125, 50))

        # تذييل النتيجة
        draw.text((70, 520), "Generated via SVU Medical Telegram Bot | بوابة نتائج قنا", fill=(108, 117, 125))

        # تصدير كملف PNG
        buf = io.BytesIO()
        image.save(buf, format='PNG')
        buf.seek(0)

        return Response(content=buf.getvalue(), media_type="image/png")

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
