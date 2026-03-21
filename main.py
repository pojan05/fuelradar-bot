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
    print("กำลังเปิดเบราว์เซอร์...")
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
        # จากรูปวงจรปิด เราเห็นว่า 5-10 วิ ข้อมูลก็มาแล้ว เราจะให้มันรอชัวร์ๆ 15 วิ
        print("รอให้หน้าเว็บโหลดข้อมูลให้เสร็จสมบูรณ์ (15 วินาที)...")
        time.sleep(15) 
        
        print("กำลังค้นหาตารางข้อมูลจากทุกกล่อง (iframe) บนหน้าจอ...")
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        print(f"พบ iframe บนหน้าเว็บทั้งหมด {len(iframes)} กล่อง")
        
        found_table = False
        
        # ค้นหาทุกกล่อง กล่องไหนมีตารางให้หยุดที่กล่องนั้น
        for index, iframe in enumerate(iframes):
            driver.switch_to.default_content() # กลับมาตั้งหลักที่หน้าแรก
            driver.switch_to.frame(iframe)     # มุดเข้ากล่อง
            
            elements = driver.find_elements(By.ID, "tbody-dash")
            if len(elements) > 0:
                print(f"✅ โป๊ะเชะ! เจอเป้าหมายในกล่องที่ {index + 1}")
                found_table = True
                break
                
        if not found_table:
            print("❌ หาตารางไม่เจอในทุกกล่องเลย")
            return stations

        # พออยู่ในกล่องที่ถูกต้อง ก็ดึงข้อมูลเลย!
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        tbody = soup.find('tbody', id='tbody-dash')

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
                
                # กรองเฉพาะอินทร์บุรี
                if "อินทร์บุรี" in district:
                    stations[name] = {
                        "ดีเซล": diesel,
                        "G95": g95,
                        "G91": g91,
                        "E20": e20,
                        "รถขนส่ง": transport,
                        "อำเภอ": district
                    }

    except Exception as e:
        print(f"⚠️ เกิดข้อผิดพลาดในการดึงข้อมูล: {e}")
        
    finally:
        driver.quit()
        
    return stations

def main():
    current_data = get_fuel_data()
    if not current_data:
        print("⚠️ ไม่พบข้อมูลปั๊มในอินทร์บุรี")
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
