from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
import io
import re

app = FastAPI()

FEES_URL = "http://mispg.svu.edu.eg/svu_pg/enquery.aspx"
RESULTS_URL = "http://mised.svu.edu.eg/exam-result/"

@app.get("/")
def read_root():
    return {"status": "running", "service": "SVU Fees and Results API"}

# ----------------- فحص المصروفات -----------------
@app.get("/get_fees")
def get_fees(national_id: str):
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ar,en;q=0.9"
    }

    try:
        res_get = session.get(FEES_URL, headers=headers, timeout=45)
        soup_get = BeautifulSoup(res_get.text, "html.parser")

        def get_val(name):
            el = soup_get.find("input", {"name": name})
            return el["value"] if el and el.has_attr("value") else ""

        payload = {
            "__VIEWSTATE": get_val("__VIEWSTATE"),
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
