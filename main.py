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
    # หั่นข้อความส่งทีละไม่เกิน 5,000 ตัวอักษร
    payload = {
        "to": LINE_TO_ID,
        "messages": [{"type": "text", "text": text[:5000]}]
    }
    requests.post(url, headers=headers, json=payload)

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
        iframe1 = WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.ID, "sandboxFrame")))
        driver.switch_to.frame(iframe1)
        
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
        iframe2 = driver.find_element(By.TAG_NAME, "iframe")
        driver.switch_to.frame(iframe2)
        
        WebDriverWait(driver, 35).until(EC.presence_of_element_located((By.ID, "tbody-dash")))
        time.sleep(5)
        
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        tbody = soup.find('tbody', id='tbody-dash')
        
        if tbody:
            rows = tbody.find_all('tr')
            for tr in rows:
                tds = tr.find_all('td')
                if len(tds) >= 10:
                    name = tds[0].text.strip()
                    district = tds[8].text.strip()
                    
                    if "อินทร์บุรี" in district:
                        map_url = ""
                        map_a = tds[-1].find('a', href=True)
                        if map_a:
                            map_url = map_a['href']
                        
                        stations[name] = {
                            "ดีเซล": tds[1].text.strip(),
                            "G95": tds[2].text.strip(),
                            "อัปเดตล่าสุด": tds[6].text.strip(),
                            "อำเภอ": district,
                            "แผนที่": map_url
                        }
                        print(f"✅ แกะข้อมูลสำเร็จ: {name}")
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
            
    updates = []
    for station, d in current_data.items():
        if station not in old_data or current_data[station] != old_data[station]:
            d_icon = "❌" if "หมด" in d['ดีเซล'] else "✅"
            g_icon = "❌" if "หมด" in d['G95'] else "✅"
            
            msg = f"📍 {station}\nดีเซล: {d_icon} {d['ดีเซล']} | G95: {g_icon} {d['G95']}\n🕒 อัปเดตเมื่อ: {d['อัปเดตล่าสุด']}"
            if d['แผนที่']:
                msg += f"\n🗺️ แผนที่: {d['แผนที่']}"
            updates.append(msg)
            
    if updates:
        # หั่นส่งครั้งละ 5 ปั๊มเพื่อป้องกันข้อความยาวเกิน limit
        for i in range(0, len(updates), 5):
            chunk = updates[i:i+5]
            final_msg = "🔔 อัปเดตใหม่! สถานะน้ำมันอินทร์บุรี\n\n" + "\n\n".join(chunk)
            send_message(final_msg)
            time.sleep(2) # กัน LINE แบน
            
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(current_data, f, ensure_ascii=False, indent=2)
    else:
        print("✅ ข้อมูลยังเป็นปัจจุบัน")

if __name__ == "__main__":
    main()
