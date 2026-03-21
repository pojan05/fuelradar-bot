import os
import json
import time
import requests
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

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
    print("กำลังเปิดเบราว์เซอร์ (โหมดทะลวงบอท + ปรับเวอร์ชันอัตโนมัติ)...")
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    
    # 🌟 พระเอกขี่ม้าขาว: ดาวน์โหลด Driver ให้ตรงกับเวอร์ชันของ Chrome บน GitHub เป๊ะๆ
    driver_path = ChromeDriverManager().install()
    
    # 🌟 ส่ง Driver ที่ถูกต้องเป๊ะๆ ให้ระบบเจาะเกราะทำงาน
    driver = uc.Chrome(options=options, driver_executable_path=driver_path)
    stations = {}
    
    try:
        driver.get(DATA_URL)
        print("กำลังรอและมุดเข้า iframe...")
        
        try:
            iframe = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.ID, "sandboxFrame"))
            )
        except:
            iframe = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "iframe"))
            )
            
        driver.switch_to.frame(iframe)
        print("มุดเข้า iframe สำเร็จ! กำลังรอตารางน้ำมันโหลด (รอสูงสุด 45 วินาที)...")

        try:
            WebDriverWait(driver, 45).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#tbody-dash tr"))
            )
        except Exception as e:
            print("⚠️ ตารางไม่โหลด! Google อาจจะยังบล็อกอยู่")
            raise e
        
        time.sleep(3)
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        tbody = soup.find('tbody', id='tbody-dash')
        
        if not tbody:
            print("❌ ไม่พบตารางข้อมูลใน iframe")
            return stations

        rows = tbody.find_all('tr')
        print(f"ดึงข้อมูลสำเร็จ พบทั้งหมด {len(rows)} ปั๊มบนหน้าเว็บ")

        for tr in rows:
            tds = tr.find_all('td')
            if len(tds) >= 9:
                name = tds[0].text.strip()
                diesel = tds[1].text.strip()
                g95 = tds[2].text.strip()
                g91 = tds[3].text.strip()
                e20 = tds[4].text.strip()
                transport = tds[5].text.strip().replace('\n', ' ')
                district = tds[8].text.strip()
                
                # กรองเอาเฉพาะ "อินทร์บุรี"
                if "อินทร์บุรี" in district:
                    stations[name] = {
                        "ดีเซล": diesel,
                        "G95": g95,
                        "G91": g91,
                        "E20": e20,
                        "รถขนส่ง": transport,
                        "อำเภอ": district
                    }
        print(f"✅ คัดกรองเหลือเฉพาะปั๊มในอินทร์บุรีได้ {len(stations)} แห่ง")

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
