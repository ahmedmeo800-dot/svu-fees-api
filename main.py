from fastapi import FastAPI
import requests
from bs4 import BeautifulSoup

app = FastAPI()
URL = "http://mispg.svu.edu.eg/svu_pg/enquery.aspx"

@app.get("/")
def home():
    return {"status": "running"}

@app.get("/get_fees")
def get_fees(national_id: str):
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ar,en-US;q=0.7,en;q=0.3"
    }

    try:
        res_get = session.get(URL, headers=headers, timeout=25)
        soup = BeautifulSoup(res_get.text, "html.parser")

        viewstate = soup.find("input", {"id": "__VIEWSTATE"})
        viewstate_gen = soup.find("input", {"id": "__VIEWSTATEGENERATOR"})
        event_val = soup.find("input", {"id": "__EVENTVALIDATION"})

        txt_input = soup.find("input", {"type": "text"})
        btn_submit = soup.find("input", {"type": "submit"})

        txt_name = txt_input.get("name", "TextBox1") if txt_input else "TextBox1"
        btn_name = btn_submit.get("name", "Button1") if btn_submit else "Button1"
        btn_val = btn_submit.get("value", "بحث") if btn_submit else "بحث"

        payload = {
            "__VIEWSTATE": viewstate.get("value", "") if viewstate else "",
            "__VIEWSTATEGENERATOR": viewstate_gen.get("value", "") if viewstate_gen else "",
            "__EVENTVALIDATION": event_val.get("value", "") if event_val else "",
            txt_name: national_id,
            btn_name: btn_val
        }

        post_headers = headers.copy()
        post_headers["Referer"] = URL

        res_post = session.post(URL, data=payload, headers=post_headers, timeout=25)
        soup_post = BeautifulSoup(res_post.text, "html.parser")

        unpaid_items = []
        rows = soup_post.find_all("tr")

        for tr in rows:
            text = tr.get_text()
            if "غير مسدد" in text or "لم يتم" in text:
                cols = [td.get_text(strip=True) for td in tr.find_all("td")]
                if len(cols) >= 5:
                    fee_type = cols[4] if len(cols) > 4 else "مصروفات"
                    req_amount = cols[5] if len(cols) > 5 else "—"
                    remaining = cols[7] if len(cols) > 7 else req_amount
                    year = cols[8] if len(cols) > 8 else "—"

                    unpaid_items.append({
                        "fee_type": fee_type,
                        "remaining": remaining,
                        "year": year
                    })

        has_data = national_id in res_post.text
        return {
            "success": True,
            "national_id": national_id,
            "has_records": has_data,
            "unpaid_fees": unpaid_items
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

