import os
import json
import time
import requests
from datetime import datetime
import pytz
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

LINE_TOKEN = os.environ.get("LINE_TOKEN")
LINE_TO_ID = os.environ.get("LINE_TO_ID")
DATA_URL = "https://script.google.com/macros/s/AKfycbxflVoeKNYwHDhMFqoZkeKUR0AG5GI4jwfqefySHxXa6MnDdBn7NbTkT4NjN-WbgYQrMQ/exec"

def send_message(text):
    url = 'https://api.line.me/v2/bot/message/push'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_TOKEN}'
    }
    payload = {
        "to": LINE_TO_ID,
        "messages": [{"type": "text", "text": text[:5000]}]
    }
    try:
        res = requests.post(url, headers=headers, json=payload)
        res.raise_for_status()
    except Exception as e:
        print(f"❌ ส่ง LINE ไม่สำเร็จ: {e}")

def get_fuel_data():
    print("🔍 เริ่มต้นการดึงข้อมูล (Headless Chrome)...")
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
        
        # ด่านที่ 1: รอ Sandbox Frame
        try:
            iframe1 = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, "sandboxFrame")))
            driver.switch_to.frame(iframe1)
            print("➡️ เข้าสู่ชั้นที่ 1 (Sandbox) สำเร็จ")
        except TimeoutException:
            print("⚠️ Error: หา sandboxFrame ไม่เจอ (หน้าเว็บอาจโหลดช้าหรือเปลี่ยนโครงสร้าง)")
            return {}

        # ด่านที่ 2: รอ Iframe เนื้อหาภายใน
        try:
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
            iframe2 = driver.find_element(By.TAG_NAME, "iframe")
            driver.switch_to.frame(iframe2)
            print("➡️ เข้าสู่ชั้นที่ 2 (Content) สำเร็จ")
        except (TimeoutException, NoSuchElementException):
            print("⚠️ Error: หา Content Iframe ไม่เจอ")
            return {}

        # ด่านที่ 3: รอข้อมูลตาราง
        try:
            WebDriverWait(driver, 40).until(EC.presence_of_element_located((By.ID, "tbody-dash")))
            time.sleep(3) # ให้เวลาระบบ Render ตารางเล็กน้อย
            print("✅ พบตารางข้อมูลแล้ว กำลังประมวลผล...")
        except TimeoutException:
            print("⚠️ Error: ตารางข้อมูล (#tbody-dash) ไม่แสดงผลภายในเวลาที่กำหนด")
            return {}
        
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
            print(f"📊 ดึงข้อมูลเสร็จสิ้น พบปั๊มในอินทร์บุรีทั้งหมด {len(stations)} แห่ง")
    except Exception as e:
        print(f"🧨 เกิดข้อผิดพลาดที่ไม่คาดคิด: {e}")
    finally:
        driver.quit()
    return stations

def main():
    # ตั้งค่าเวลาไทย
    tz = pytz.timezone('Asia/Bangkok')
    thai_now = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
    print("-" * 30)
    print(f"🚀 Bot Start Time (Thai): {thai_now}")
    print("-" * 30)

    current_data = get_fuel_data()
    
    if not current_data:
        print("🛑 ไม่มีข้อมูลถูกดึงมาได้ในรอบนี้ ข้ามการทำงานเพื่อป้องกันข้อมูลเดิมเสียหาย")
        return
        
    old_data = {}
    if os.path.exists("data.json"):
        with open("data.json", "r", encoding="utf-8") as f:
            try: old_data = json.load(f)
            except: old_data = {}
            
    updates = []
    for station, d in current_data.items():
        if station not in old_data or current_data[station] != old_data[station]:
            
            def get_icon(status):
                return "✅" if "มี" in status else "❌" if "หมด" in status else "⚪"

            msg = f"📍 {station}\n"
            msg += f"⛽ ดีเซล:{get_icon(d['ดีเซล'])} {d['ดีเซล']} | G95:{get_icon(d['G95'])} {d['G95']}\n"
            msg += f"⛽ G91:{get_icon(d['G91'])} {d['G91']} | E20:{get_icon(d['E20'])} {d['E20']}\n"
            
            trans_icon = "🚚" if "จัดส่ง" in d['รถขนส่ง'] else "✅"
            msg += f"{trans_icon} รถขนส่ง: {d['รถขนส่ง']}\n"
            msg += f"🕒 อัปเดตล่าสุด: {d['อัปเดตล่าสุด']}"
            
            updates.append(msg)
            
    if updates:
        print(f"🔔 พบการเปลี่ยนแปลง {len(updates)} แห่ง กำลังส่งการแจ้งเตือน...")
        for i in range(0, len(updates), 5):
            chunk = updates[i:i+5]
            final_msg = f"🔔 แจ้งอัปเดตน้ำมัน (อินทร์บุรี)\n⏰ ตรวจสอบเมื่อ: {thai_now}\n\n" + "\n\n".join(chunk)
            send_message(final_msg)
            time.sleep(2)
            
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(current_data, f, ensure_ascii=False, indent=2)
    else:
        print("✅ ข้อมูลยังเป็นปัจจุบัน (ไม่มีการเปลี่ยนแปลง)")

if __name__ == "__main__":
    main()
