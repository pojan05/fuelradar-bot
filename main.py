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
    requests.post(url, headers=headers, json=payload)

def get_fuel_data():
    print("กำลังเริ่มระบบเจาะข้อมูล 2 ชั้น...")
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
        print("1. มุดเข้า iframe ชั้นแรก (sandboxFrame)...")
        iframe1 = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "sandboxFrame"))
        )
        driver.switch_to.frame(iframe1)
        
        print("2. มุดเข้า iframe ชั้นที่สอง (ห้องลับของ Google)...")
        # รอให้ iframe ตัวที่สองโผล่มา แล้วมุดเข้าไป
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
        iframe2 = driver.find_element(By.TAG_NAME, "iframe")
        driver.switch_to.frame(iframe2)
        
        print("3. คอยตารางข้อมูลปรากฏบนหน้าจอ...")
        # รอจนกว่าตารางจะขึ้นจริงๆ (เหมือนในรูป debug ของพี่)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "tbody-dash"))
        )
        time.sleep(3) # เผื่อเวลาให้ตัวหนังสือโหลดครบ
        
        # กวาดข้อมูลออกมา
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        tbody = soup.find('tbody', id='tbody-dash')
        
        if tbody:
            rows = tbody.find_all('tr')
            print(f"✅ สำเร็จ! พบข้อมูลทั้งหมด {len(rows)} ปั๊ม")
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
                            "อำเภอ": district
                        }
        else:
            print("❌ ยังหาตารางไม่เจอแม้จะมุดเข้ามาแล้ว")

    except Exception as e:
        print(f"⚠️ เกิดข้อผิดพลาด: {e}")
        driver.save_screenshot("error_at_the_end.png")
    finally:
        driver.quit()
        
    return stations

def main():
    current_data = get_fuel_data()
    if not current_data:
        return
        
    print(f"พบปั๊มในอินทร์บุรี {len(current_data)} แห่ง")
    
    old_data = {}
    if os.path.exists("data.json"):
        with open("data.json", "r", encoding="utf-8") as f:
            try: old_data = json.load(f)
            except: old_data = {}
            
    changed_stations = []
    for station, details in current_data.items():
        if station not in old_data or current_data[station] != old_data[station]:
            d_icon = "❌" if "หมด" in details['ดีเซล'] else "✅"
            g_icon = "❌" if "หมด" in details['G95'] else "✅"
            msg = f"📍 {station}\nดีเซล: {d_icon} {details['ดีเซล']} | G95: {g_icon} {details['G95']}\n🚚 {details['รถขนส่ง']}"
            changed_stations.append(msg)
            
    if changed_stations:
        print("กำลังส่งแจ้งเตือนเข้า LINE...")
        final_msg = "🔔 อัปเดตสถานะน้ำมัน อินทร์บุรี!\n\n" + "\n\n".join(changed_stations)
        send_message(final_msg)
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(current_data, f, ensure_ascii=False, indent=2)
    else:
        print("✅ ข้อมูลยังเหมือนเดิม")

if __name__ == "__main__":
    main()
