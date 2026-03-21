import os
import json
import time
import requests
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

def send_message(text):
    url = 'https://api.line.me/v2/bot/message/push'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_TOKEN}'
    }
    # หั่นส่งครั้งละไม่เกิน 5,000 ตัวอักษรตามเกณฑ์ของ LINE
    payload = {
        "to": LINE_TO_ID,
        "messages": [{"type": "text", "text": text[:5000]}]
    }
    requests.post(url, headers=headers, json=payload)

def get_fuel_data():
    print("กำลังดึงข้อมูลด้วยระบบเจาะ 2 ชั้น (เน้นความแม่นยำสูง)...")
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    stations = {}
    
    try:
        driver.get(DATA_URL)
        # มุดเข้าห้องลับ 2 ชั้นเพื่อเข้าถึงข้อมูลตารางที่แท้จริง
        iframe1 = WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.ID, "sandboxFrame")))
        driver.switch_to.frame(iframe1)
        
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
        iframe2 = driver.find_element(By.TAG_NAME, "iframe")
        driver.switch_to.frame(iframe2)
        
        # รอจนกว่าตารางข้อมูล (tbody-dash) จะปรากฏ
        WebDriverWait(driver, 35).until(EC.presence_of_element_located((By.ID, "tbody-dash")))
        time.sleep(5) 
        
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        tbody = soup.find('tbody', id='tbody-dash')
        
        if tbody:
            rows = tbody.find_all('tr')
            for tr in rows:
                tds = tr.find_all('td')
                if len(tds) >= 9:
                    name = tds[0].text.strip()
                    district = tds[8].text.strip()
                    
                    if "อินทร์บุรี" in district:
                        stations[name] = {
                            "ดีเซล": tds[1].text.strip(),
                            "G95": tds[2].text.strip(),
                            "G91": tds[3].text.strip(),
                            "E20": tds[4].text.strip(),
                            "รถขนส่ง": tds[5].text.strip().replace('\n', ' '),
                            "อัปเดตล่าสุด": tds[6].text.strip(),
                            "อำเภอ": district
                        }
                        print(f"✅ อ่านข้อมูลสำเร็จ: {name}")
    except Exception as e:
        print(f"⚠️ เกิดข้อผิดพลาด: {e}")
    finally:
        driver.quit()
    return stations

def main():
    current_data = get_fuel_data()
    if not current_data:
        return
        
    old_data = {}
    if os.path.exists("data.json"):
        with open("data.json", "r", encoding="utf-8") as f:
            try: old_data = json.load(f)
            except: old_data = {}
            
    updates = []
    for station, d in current_data.items():
        # ตรวจสอบการเปลี่ยนแปลงทุกฟิลด์ (สถานะน้ำมันทุกชนิด, รถขนส่ง, และเวลาอัปเดต)
        if station not in old_data or current_data[station] != old_data[station]:
            
            # ฟังก์ชันช่วยเปลี่ยนข้อความ "มี/หมด" เป็นไอคอนเพื่อความสวยงาม
            def get_icon(status):
                return "✅" if "มี" in status else "❌" if "หมด" in status else "⚪"

            msg = f"📍 {station}\n"
            msg += f"⛽ ดีเซล:{get_icon(d['ดีเซล'])} {d['ดีเซล']} | G95:{get_icon(d['G95'])} {d['G95']}\n"
            msg += f"⛽ G91:{get_icon(d['G91'])} {d['G91']} | E20:{get_icon(d['E20'])} {d['E20']}\n"
            
            # ตรวจสอบสถานะรถขนส่ง
            trans_icon = "🚚" if "จัดส่ง" in d['รถขนส่ง'] else "✅"
            msg += f"{trans_icon} รถขนส่ง: {d['รถขนส่ง']}\n"
            msg += f"🕒 อัปเดตล่าสุด: {d['อัปเดตล่าสุด']}"
            
            updates.append(msg)
            
    if updates:
        print(f"พบการเปลี่ยนแปลง {len(updates)} แห่ง กำลังแจ้งเตือน...")
        # หั่นส่งทีละ 5 ปั๊มเพื่อให้ข้อความไม่ยาวเกินไปและดูอ่านง่าย
        for i in range(0, len(updates), 5):
            chunk = updates[i:i+5]
            final_msg = "🔔 แจ้งอัปเดตน้ำมัน (อินทร์บุรี)\n\n" + "\n\n".join(chunk)
            send_message(final_msg)
            time.sleep(2)
            
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(current_data, f, ensure_ascii=False, indent=2)
    else:
        print("✅ ข้อมูลยังเป็นปัจจุบัน ไม่มีการเปลี่ยนแปลงจากหน้าเว็บหลัก")

if __name__ == "__main__":
    main()
