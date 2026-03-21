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

# ตั้งค่า Configuration
LINE_TOKEN = os.environ.get("LINE_TOKEN")
LINE_TO_ID = os.environ.get("LINE_TO_ID")
DATA_URL = "https://script.google.com/macros/s/AKfycbxflVoeKNYwHDhMFqoZkeKUR0AG5GI4jwfqefySHxXa6MnDdBn7NbTkT4NjN-WbgYQrMQ/exec"

def create_flex_bubble(station_name, d):
    # ฟังก์ชันช่วยเลือกสีตามสถานะน้ำมัน
    def get_color(status):
        return "#22bb33" if "มี" in status else "#bb2124" if "หมด" in status else "#aaaaaa"
    
    return {
      "type": "bubble",
      "size": "mega",
      "header": {
        "type": "box", "layout": "vertical", "backgroundColor": "#f39c12",
        "contents": [{"type": "text", "text": station_name, "weight": "bold", "color": "#ffffff", "size": "lg"}]
      },
      "body": {
        "type": "box", "layout": "vertical", "spacing": "md",
        "contents": [
          {"type": "box", "layout": "horizontal", "contents": [
            {"type": "text", "text": "ดีเซล", "flex": 1, "size": "sm", "color": "#555555"},
            {"type": "text", "text": d['ดีเซล'], "flex": 2, "size": "sm", "weight": "bold", "color": get_color(d['ดีเซล']), "align": "end"}
          ]},
          {"type": "box", "layout": "horizontal", "contents": [
            {"type": "text", "text": "G95/G91", "flex": 1, "size": "sm", "color": "#555555"},
            {"type": "text", "text": f"{d['G95']} | {d['G91']}", "flex": 2, "size": "sm", "weight": "bold", "color": "#333333", "align": "end"}
          ]},
          {"type": "box", "layout": "horizontal", "contents": [
            {"type": "text", "text": "E20", "flex": 1, "size": "sm", "color": "#555555"},
            {"type": "text", "text": d['E20'], "flex": 2, "size": "sm", "weight": "bold", "color": get_color(d['E20']), "align": "end"}
          ]},
          {"type": "separator", "margin": "md"},
          {"type": "text", "text": f"🚚 รถ: {d['รถขนส่ง']}", "size": "xs", "color": "#888888", "wrap": True},
          {"type": "text", "text": f"🕒 อัปเดตล่าสุด: {d['อัปเดตล่าสุด']}", "size": "xs", "color": "#888888"}
        ]
      },
      "footer": {
        "type": "box", "layout": "vertical",
        "contents": [{"type": "button", "action": {"type": "uri", "label": "🌐 เปิดแผนที่ (Google Maps)", "uri": d['map_url']}, "style": "primary", "color": "#3498db", "height": "sm"}]
      }
    }

def send_flex(bubbles, alt_text="อัปเดตน้ำมันอินทร์บุรี"):
    url = 'https://api.line.me/v2/bot/message/push'
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {LINE_TOKEN}'}
    # หั่นส่งครั้งละไม่เกิน 10 bubbles ตามเกณฑ์ LINE
    for i in range(0, len(bubbles), 10):
        chunk = bubbles[i:i+10]
        payload = {
            "to": LINE_TO_ID,
            "messages": [{
                "type": "flex",
                "altText": alt_text,
                "contents": {"type": "carousel", "contents": chunk}
            }]
        }
        requests.post(url, headers=headers, json=payload)

def get_fuel_data():
    print("🚀 กำลังดึงข้อมูลแม่นยำสูง (Hybrid Extraction)...")
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    stations = {}
    
    try:
        driver.get(DATA_URL)
        # มุด 2 ชั้นเข้าสู่ตารางข้อมูล
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
                if len(tds) >= 10:
                    name = tds[0].text.strip()
                    district = tds[8].text.strip()
                    
                    if "อินทร์บุรี" in district:
                        # ดึงลิงก์แผนที่จริงจากปุ่มสีฟ้า
                        map_link = tds[9].find('a')['href'] if tds[9].find('a') else "https://www.google.com/maps"
                        
                        stations[name] = {
                            "ดีเซล": tds[1].text.strip(),
                            "G95": tds[2].text.strip(),
                            "G91": tds[3].text.strip(),
                            "E20": tds[4].text.strip(),
                            "รถขนส่ง": tds[5].text.strip().replace('\n', ' '),
                            "อัปเดตล่าสุด": tds[6].text.strip(),
                            "map_url": map_link
                        }
                        print(f"✅ อ่านสำเร็จ: {name}")
    except Exception as e:
        print(f"⚠️ Error: {e}")
    finally:
        driver.quit()
    return stations

def main():
    current_data = get_fuel_data()
    if not current_data: return
    
    tz = pytz.timezone('Asia/Bangkok')
    now = datetime.datetime.now(tz)
    
    # 🕒 1. รายงานสรุปตอน 06.00 น.
    if now.hour == 6 and now.minute < 11:
        bubbles = [create_flex_bubble(s, d) for s, d in current_data.items()]
        send_flex(bubbles, "🌅 สรุปภาพรวมน้ำมันเช้านี้ (อินทร์บุรี)")

    # 🔔 2. แจ้งเตือนทันทีเมื่อมีการเปลี่ยนแปลง
    old_data = {}
    if os.path.exists("data.json"):
        with open("data.json", "r", encoding="utf-8") as f:
            try: old_data = json.load(f)
            except: pass
            
    update_bubbles = []
    for station, d in current_data.items():
        if station not in old_data or current_data[station] != old_data[station]:
            update_bubbles.append(create_flex_bubble(station, d))
            
    if update_bubbles:
        send_flex(update_bubbles, "🔔 มีอัปเดตน้ำมันใหม่ในอินทร์บุรี!")
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(current_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
