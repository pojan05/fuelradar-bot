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
    print("กำลังเปิดเบราว์เซอร์จำลองเพื่อดึงข้อมูล...")
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    # ขยายจอให้กว้างที่สุดเพื่อให้ตารางแสดงผลครบทุกคอลัมน์
    options.add_argument('--window-size=1920,1080')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    stations = {}
    
    try:
        driver.get(DATA_URL)
        print("กำลังรอและมุดเข้า iframe...")
        
        try:
            iframe = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.ID, "sandboxFrame"))
            )
        except:
            iframe = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "iframe"))
            )
            
        driver.switch_to.frame(iframe)
        print("มุดเข้า iframe สำเร็จ! กำลังรอข้อมูลตารางน้ำมัน...")

        # จุดสำคัญ: รอจนกว่าแถวข้อมูล (tr) จะโผล่ขึ้นมาในตารางจริงๆ (รอได้สูงสุด 30 วินาที)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#tbody-dash tr"))
        )
        
        # ให้เวลาข้อมูลโหลดเข้าตารางให้ครบ
        time.sleep(3)
        
        # ดึงหน้าเว็บมาตัดคำ
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        tbody = soup.find('tbody', id='tbody-dash')
        
        if not tbody:
            print("❌ ไม่พบตารางข้อมูลใน iframe")
            return stations

        rows = tbody.find_all('tr')
        print(f"ดึงข้อมูลสำเร็จ พบทั้งหมด {len(rows)} ปั๊ม")

        for tr in rows:
            tds = tr.find_all('td')
            # ตรวจสอบว่าคอลัมน์มาครบ 9 ช่อง
            if len(tds) >= 9:
                name = tds[0].text.strip()
                diesel = tds[1].text.strip()
                g95 = tds[2].text.strip()
                g91 = tds[3].text.strip()
                e20 = tds[4].text.strip()
                transport = tds[5].text.strip().replace('\n', ' ')
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
                    print(f"✅ พบข้อมูล: {name}")

    except Exception as e:
        print(f"⚠️ เกิดข้อผิดพลาดในการดึงข้อมูล: {e}")
        
    finally:
        driver.quit()
        
    return stations

def main():
    current_data = get_fuel_data()
    if not current_data:
        print("⚠️ ไม่พบข้อมูลปั๊มในอินทร์บุรี หรือโหลดข้อมูลไม่สำเร็จ")
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
