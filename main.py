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
    print("กำลังเปิดเบราว์เซอร์จำลอง (โหมดปลดล็อคคุกกี้ขั้นสูง)...")
    options = Options()
    options.add_argument('--headless=new') 
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36')
    
    # 🌟 1. ลบป้ายทะเบียนบอท ไม่ให้ Google รู้ว่าใช้โปรแกรมอัตโนมัติ
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # 🌟 2. อนุญาตให้ใช้ Third-Party Cookies (หัวใจสำคัญที่ทำให้ Google Apps Script โหลดข้อมูลได้)
    prefs = {
        "profile.default_content_setting_values.cookies": 1,
        "profile.cookie_controls_mode": 0
    }
    options.add_experimental_option("prefs", prefs)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    # 🌟 3. สคริปต์ลบคำว่า "webdriver" ออกจากเบราว์เซอร์
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    
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
        print("มุดเข้า iframe สำเร็จ! กำลังรอตารางน้ำมันโหลด...")

        try:
            # รอให้แถวข้อมูลโผล่
            WebDriverWait(driver, 45).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#tbody-dash tr"))
            )
        except Exception as wait_error:
            # ถ้าพลาดอีก เราจะให้มันปรินต์ข้อความบนหน้าจอออกมาดูเลยว่าติดอะไร!
            html_check = driver.page_source
            soup_check = BeautifulSoup(html_check, 'html.parser')
            text_on_screen = soup_check.body.text.strip()[:200] if soup_check.body else "หน้าจอว่างเปล่า"
            print(f"⚠️ แจ้งเตือน: โหลดข้อมูลไม่สำเร็จ! ข้อความบนหน้าจอตอนนี้คือ: {text_on_screen}")
            raise wait_error
        
        time.sleep(3)
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
            if len(tds) >= 9:
                name = tds[0].text.strip()
                diesel = tds[1].text.strip()
                g95 = tds[2].text.strip()
                g91 = tds[3].text.strip()
                e20 = tds[4].text.strip()
                transport = tds[5].text.strip().replace('\n', ' ')
                district = tds[8].text.strip()
                
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
