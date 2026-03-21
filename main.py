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
    print("กำลังเปิดเบราว์เซอร์จำลอง...")
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    # ขยายหน้าต่างบอทให้กว้างสุด เพื่อป้องกันเว็บซ่อนคอลัมน์ "อำเภอ" ในโหมดมือถือ
    options.add_argument('--window-size=1920,1080') 
    
    driver = webdriver.Chrome(options=options)
    stations = {}
    
    try:
        driver.get(DATA_URL)
        print("กำลังรอโหลดหน้าเว็บหลัก...")
        
        # 1. รอและมุดเข้า iframe
        print("กำลังค้นหา iframe...")
        iframe = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "iframe"))
        )
        driver.switch_to.frame(iframe)
        print("มุดเข้า iframe สำเร็จ! กำลังจ้องตารางข้อมูล...")
        
        # 2. หัวใจสำคัญ: สั่งให้บอทรอจนกว่า <tr> (แถวข้อมูล) จะโผล่ขึ้นมาในตาราง (รอได้สูงสุด 30 วินาที)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#tbody-dash tr"))
        )
        
        # ให้เวลาข้อมูลเรนเดอร์ลงตารางให้ครบอีกนิด
        time.sleep(3)
        
        # 3. ดึง HTML มาแกะ
        print("ข้อมูลโผล่แล้ว! กำลังดึงข้อมูลมาแกะ...")
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        tbody = soup.find('tbody', id='tbody-dash')
        
        if not tbody:
            print("❌ หา tbody ไม่เจอ")
            return stations
            
        rows = tbody.find_all('tr')
        print(f"พบข้อมูลปั๊มน้ำมันในตารางทั้งหมด {len(rows)} แถว")
        
        for tr in rows:
            tds = tr.find_all('td')
            # ตรวจสอบว่าคอลัมน์มาครบ 9 ช่อง
            if len(tds) >= 9:
                name = tds[0].text.strip()
                diesel = tds[1].text.strip()
                g95 = tds[2].text.strip()
                g91 = tds[3].text.strip()
                e20 = tds[4].text.strip()
                
                # ทำความสะอาดข้อความรถขนส่ง (เอาเว้นบรรทัดออก)
                transport_raw = tds[5].text.strip()
                transport = transport_raw.replace('\n', ' ').strip()
                
                district = tds[8].text.strip()
                
                # กรองเฉพาะปั๊มใน "อินทร์บุรี"
                if "อินทร์บุรี" in district:
                    stations[name] = {
                        "ดีเซล": diesel,
                        "G95": g95,
                        "G91": g91,
                        "E20": e20,
                        "รถขนส่ง": transport,
                        "อำเภอ": district
                    }
                    print(f"✅ ดึงข้อมูลสำเร็จ: {name}")

    except Exception as e:
        print(f"⚠️ เกิดข้อผิดพลาดในการรอข้อมูล: {e}")
        
    finally:
        driver.quit()
        
    return stations

def main():
    current_data = get_fuel_data()
    if not current_data:
        print("⚠️ ไม่พบข้อมูลปั๊มในอินทร์บุรีเลย อาจจะโหลดข้อมูลไม่ทัน")
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
            
            transport_status = details['รถขนส่ง']
            if not transport_status or transport_status == "ปกติ" or transport_status == "null":
                msg += "รถขนส่ง: ✅ ปกติ"
            else:
                 msg += f"รถขนส่ง: 🚚 {transport_status}"
                 
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
