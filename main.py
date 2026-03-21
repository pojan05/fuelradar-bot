import os
import json
import time
import requests
import datetime
import pytz
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

LINE_TOKEN = os.environ.get("LINE_TOKEN")
LINE_TO_ID = os.environ.get("LINE_TO_ID")
DATA_URL = "https://script.google.com/macros/s/AKfycbxflVoeKNYwHDhMFqoZkeKUR0AG5GI4jwfqefySHxXa6MnDdBn7NbTkT4NjN-WbgYQrMQ/exec"

def create_station_row(name, d):
    # สร้างแถวข้อมูลปั๊มแบบประหยัดพื้นที่
    def get_dot(status):
        return "🟢" if "มี" in status else "🔴" if "หมด" in status else "⚪"
    
    return {
        "type": "box", "layout": "vertical", "margin": "lg", "spacing": "sm",
        "contents": [
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": f"📍 {name}", "weight": "bold", "size": "sm", "flex": 4, "color": "#111111", "wrap": True},
                {"type": "button", "action": {"type": "uri", "label": "แผนที่", "uri": d['map_url']}, "flex": 2, "height": "xs", "style": "secondary", "color": "#eeeeee"}
            ]},
            {"type": "box", "layout": "horizontal", "contents": [
                {"type": "text", "text": f"D:{get_dot(d['ดีเซล'])} | 95:{get_dot(d['G95'])} | 91:{get_dot(d['G91'])} | E20:{get_dot(d['E20'])}", "size": "xs", "color": "#555555", "flex": 4},
                {"type": "text", "text": d['อัปเดตล่าสุด'], "size": "xxs", "color": "#aaaaaa", "align": "end", "flex": 2}
            ]},
            {"type": "text", "text": f"🚚 {d['รถขนส่ง']}", "size": "xxs", "color": "#999999"},
            {"type": "separator", "margin": "md"}
        ]
    }

def create_list_bubble(title, station_chunk):
    # สร้าง Bubble ขนาดใหญ่ที่บรรจุปั๊มได้หลายแห่ง
    rows = [create_station_row(name, data) for name, data in station_chunk.items()]
    return {
        "type": "bubble",
        "header": {"type": "box", "layout": "vertical", "backgroundColor": "#f39c12", "contents": [{"type": "text", "text": title, "color": "#ffffff", "weight": "bold", "size": "md"}]},
        "body": {"type": "box", "layout": "vertical", "contents": rows}
    }

def send_flex(bubbles, alt_text):
    url = 'https://api.line.me/v2/bot/message/push'
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {LINE_TOKEN}'}
    # ส่ง 1 Push Message บรรจุได้สูงสุด 12 Bubbles (เราส่งแค่ 1-2 แผ่นก็ครบ 16 ปั๊มแล้ว)
    payload = {
        "to": LINE_TO_ID,
        "messages": [{
            "type": "flex",
            "altText": alt_text,
            "contents": {"type": "carousel", "contents": bubbles[:12]}
        }]
    }
    requests.post(url, headers=headers, json=payload)

def get_fuel_data():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    stations = {}
    try:
        driver.get(DATA_URL)
        iframe1 = WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.ID, "sandboxFrame")))
        driver.switch_to.frame(iframe1)
        iframe2 = driver.find_element(By.TAG_NAME, "iframe")
        driver.switch_to.frame(iframe2)
        WebDriverWait(driver, 35).until(EC.presence_of_element_located((By.ID, "tbody-dash")))
        time.sleep(5)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        tbody = soup.find('tbody', id='tbody-dash')
        if tbody:
            for tr in tbody.find_all('tr'):
                tds = tr.find_all('td')
                if len(tds) >= 10 and "อินทร์บุรี" in tds[8].text:
                    name = tds[0].text.strip()
                    stations[name] = {
                        "ดีเซล": tds[1].text.strip(), "G95": tds[2].text.strip(),
                        "G91": tds[3].text.strip(), "E20": tds[4].text.strip(),
                        "รถขนส่ง": tds[5].text.strip().replace('\n', ' '),
                        "อัปเดตล่าสุด": tds[6].text.strip(),
                        "map_url": tds[9].find('a')['href'] if tds[9].find('a') else "https://www.google.com/maps"
                    }
    finally: driver.quit()
    return stations

def main():
    current_data = get_fuel_data()
    if not current_data: return
    
    tz = pytz.timezone('Asia/Bangkok')
    now = datetime.datetime.now(tz)
    
    # 🕒 1. สรุปเช้า 06.00 น. (รวมเป็นแผ่นเดียวจบ)
    if now.hour == 6 and now.minute < 11:
        items = list(current_data.items())
        # แบ่งเป็น 2 แผ่น แผ่นละ 8-9 ปั๊ม เพื่อความสวยงามไม่ยาวเกินไป
        bubble1 = create_list_bubble("🌅 สรุปน้ำมันเช้านี้ (1/2)", dict(items[:8]))
        bubble2 = create_list_bubble("🌅 สรุปน้ำมันเช้านี้ (2/2)", dict(items[8:]))
        send_flex([bubble1, bubble2], "สรุปน้ำมันยามเช้าอินทร์บุรี")

    # 🔔 2. แจ้งเตือนเมื่อเปลี่ยน (รวมรายการที่เปลี่ยนไว้ในแผ่นเดียว)
    old_data = {}
    if os.path.exists("data.json"):
        with open("data.json", "r", encoding="utf-8") as f:
            try: old_data = json.load(f)
            except: pass
            
    changes = {s: d for s, d in current_data.items() if s not in old_data or d != old_data[s]}
            
    if changes:
        bubble = create_list_bubble("🔔 พบการอัปเดตน้ำมัน!", changes)
        send_flex([bubble], "มีอัปเดตน้ำมันใหม่!")
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(current_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
