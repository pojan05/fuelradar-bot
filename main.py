import os
import json
import time
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
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
    payload = {
        "to": LINE_TO_ID,
        "messages": [{"type": "text", "text": text}]
    }
    requests.post(url, headers=headers, json=payload)

def get_fuel_data():
    print("กำลังเปิดเบราว์เซอร์จำลองเพื่อดึงข้อมูล...")
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=options)
    driver.get(DATA_URL)
    
    stations = {}
    
    try:
        # 1. รอจนกว่า iframe จะโผล่มา และสลับเข้าไปข้างใน
        print("กำลังรอและมุดเข้า iframe...")
        iframe = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "sandboxFrame"))
        )
        driver.switch_to.frame(iframe)
        
        # 2. รอจนกว่าตารางข้อมูลจะโหลดเสร็จ
        print("มุดเข้า iframe สำเร็จ! กำลังรอข้อมูลตารางน้ำมัน...")
        tbody = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "tbody-dash"))
        )
        
        # ให้เวลามันดึงข้อมูลมาเรียงใส่ตารางนิดนึง
        time.sleep(5)
        
        # 3. ดึง HTML ออกมาแปลง
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        tbody = soup.find('tbody', id='tbody-dash')
        
        if not tbody:
            print("❌ ไม่พบโครงสร้างตารางข้อมูลใน iframe")
            return stations

        print("กำลังอ่านข้อมูลจากตาราง...")
        for tr in tbody.find_all('tr'):
            tds = tr.find_all('td')
            # ตรวจสอบว่าคอลัมน์ครบตามตารางในหน้าเว็บ
            if len(tds) >= 9: 
                name = tds[0].text.strip()
                diesel = tds[1].text.strip()
                g95 = tds[2].text.strip()
                g91 = tds[3].text.strip()
                e20 = tds[4].text.strip()
                transport = tds[5].text.strip().replace('\n', ' ') 
                district = tds[8].text.strip()  # ดึงข้อมูลอำเภอมาเช็ค

                # 4. กรองเอาเฉพาะปั๊มใน 'อินทร์บุรี'
                if "อินทร์บุรี" in district:
                    stations[name] = {
                        "ดีเซล": diesel, "G95": g95, "G91": g91, "E20": e20, "รถขนส่ง": transport, "อำเภอ": district
                    }
                    print(f"✅ พบข้อมูล: {name}")

    except Exception as e:
        print(f"⚠️ เกิดข้อผิดพลาดในการดึงข้อมูล: {e}")
        
    finally:
        driver.quit()
        
    return stations

def main():
    current_data = get_fuel_data()
    if not current_data:
        print("⚠️ ไม่ได้ข้อมูลกลับมาเลย อาจจะมีปัญหาการเชื่อมต่อ")
        return
        
    old_data = {}
    if os.path.exists("data.json"):
        with open("data.json", "r", encoding="utf-8") as f:
            try:
                old_data = json.load(f)
            except:
                old_data = {}
            
    changed_stations = []
    
    for station, details in current_data.items():
        if station not in old_data or current_data[station] != old_data[station]:
            diesel_icon = "❌" if "หมด" in details['ดีเซล'] else "✅"
            g95_icon = "❌" if "หมด" in details['G95'] else "✅"
            
            msg = f"📍 {station}\n"
            msg += f"ดีเซล: {diesel_icon} {details['ดีเซล']} | G95: {g95_icon} {details['G95']}\n"
            msg += f"รถขนส่ง: 🚚 {details['รถขนส่ง']}"
            changed_stations.append(msg)
            
    if changed_stations:
        print(f"พบปั๊มในอินทร์บุรีที่สถานะเปลี่ยน {len(changed_stations)} แห่ง! กำลังส่งเข้า LINE...")
        final_msg = "🔔 อัปเดตสถานะน้ำมัน อินทร์บุรี!\n\n" + "\n\n".join(changed_stations)
        send_message(final_msg)
        
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(current_data, f, ensure_ascii=False, indent=2)
    else:
        print("✅ ข้อมูลสถานะน้ำมันในอินทร์บุรียังเหมือนเดิม ไม่มีอัปเดตใหม่")

if __name__ == "__main__":
    main()
