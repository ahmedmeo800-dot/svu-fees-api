from fastapi import FastAPI
from fastapi.responses import JSONResponse
import requests
from bs4 import BeautifulSoup
import re

app = FastAPI()

FEES_URL = "http://mispg.svu.edu.eg/svu_pg/enquery.aspx"

@app.get("/")
def read_root():
    return {"status": "running", "service": "SVU Fees API"}

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
