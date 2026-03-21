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
    payload = {
        "to": LINE_TO_ID,
        "messages": [{"type": "text", "text": text}]
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        print(f"❌ แจ้งเตือน LINE ไม่สำเร็จ: {response.text}")

def get_fuel_data():
    print("กำลังเริ่มระบบเจาะข้อมูลระดับลึกพร้อมแผนที่...")
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
        # มุดเข้าห้องลับ 2 ชั้นตามแผนเดิมที่เสถียรแล้ว
        iframe1 = WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.ID, "sandboxFrame")))
        driver.switch_to.frame(iframe1)
        
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
        iframe2 = driver.find_element(By.TAG_NAME, "iframe")
        driver.switch_to.frame(iframe2)
        
        WebDriverWait(driver, 35).until(EC.presence_of_element_located((By.ID, "tbody-dash")))
        time.sleep(5) # เผื่อเวลาให้ตารางขึ้นครบตามรูป debug ของพี่
        
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        tbody = soup.find('tbody', id='tbody-dash')
        
        if tbody:
            rows = tbody.find_all('tr')
            for tr in rows:
                tds = tr.find_all('td')
                if len(tds) >= 10: # ตรวจสอบคอลัมน์แผนที่
                    name = tds[0].text.strip()
                    district = tds[8].text.strip()
                    
                    if "อินทร์บุรี" in district:
                        # 🌟 ไม้ตาย: สั่งให้บอทแกะลิงก์ Google Maps จากปุ่มแผนที่ในคอลัมน์สุดท้าย
                        map_cell = tds[-1] # คอลัมน์ "แผนที่" สุดท้าย
                        map_a_tag = map_cell.find('a', href=True) # หา tag 'a' ที่มีhref
                        map_url = ""
                        if map_a_tag:
                            map_url = map_a_tag['href'] # ดึงลิงก์ Google Maps ออกมาตรงๆ ตามรูป `image_fd63ab.png`
                            print(f"✅ แกะลิงก์แผนที่สำเร็จ: {name}")

                        # เก็บข้อมูล (รวมเวลาอัปเดตและแผนที่)
                        stations[name] = {
                            "ดีเซล": tds[1].text.strip(),
                            "G95": tds[2].text.strip(),
                            "อัปเดตล่าสุด": tds[6].text.strip(),
                            "อำเภอ": district,
                            "แผนที่": map_url # เก็บลิงก์แผนที่ไว้ในข้อมูลชุดนี้
                        }
    except Exception as e:
        print(f"⚠️ Error: {e}")
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
            
    changed_stations = []
    for station, details in current_data.items():
        # ตรวจสอบว่าข้อมูลมีการเปลี่ยนแปลงหรือไม่ (รวมถึงเวลาอัปเดต)
        if station not in old_data or current_data[station] != old_data[station]:
            d_icon = "❌" if "หมด" in details['ดีเซล'] else "✅"
            g_icon = "❌" if "หมด" in details['G95'] else "✅"
            
            # จัดรูปแบบข้อความแจ้งเตือน (รวมเวลาอัปเดตและ Google Maps)
            msg = f"📍 {station}\n"
            msg += f"ดีเซล: {d_icon} {details['ดีเซล']} | G95: {g_icon} {details['G95']}\n"
            msg += f"🕒 อัปเดตเมื่อ: {details['อัปเดตล่าสุด']}" # แสดงเวลาจากหน้าเว็บ
            
            # เพิ่มลิงก์แผนที่นำทางต่อท้ายปั๊ม ถ้าแกะสำเร็จ
            if details.get('แผนที่'):
                msg += f"\n🗺️ แผนที่นำทาง: {details['แผนที่']}" # แสดงลิงก์ Google Maps ใน LINE
                
            changed_stations.append(msg)
            
    if changed_stations:
        print(f"พบข้อมูลเปลี่ยนแปลง {len(changed_stations)} แห่ง")
        final_msg = "🔔 อัปเดตใหม่! สถานะน้ำมันอินทร์บุรี\n\n" + "\n\n".join(changed_stations)
        send_message(final_msg)
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(current_data, f, ensure_ascii=False, indent=2)
    else:
        print("✅ ข้อมูลยังเป็นปัจจุบัน ไม่มีการเปลี่ยนแปลง")

if __name__ == "__main__":
    main()
