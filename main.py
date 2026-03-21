import os
import json
import time
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

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
    options.add_argument('--headless') # ทำงานแบบซ่อนหน้าต่าง
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=options)
    driver.get(DATA_URL)
    
    # ให้บอทรอ 8 วินาที เพื่อให้ข้อมูลน้ำมันโหลดจนครบ
    time.sleep(8) 
    
    html = driver.page_source
    driver.quit()
    
    # ใช้ BeautifulSoup แกะข้อมูล HTML ตามภาพที่คุณส่งมา
    soup = BeautifulSoup(html, 'html.parser')
    tbody = soup.find('tbody', id='tbody-dash')
    
    stations = {}
    if not tbody:
        print("❌ ไม่พบตารางข้อมูล (หน้าเว็บอาจจะยังโหลดไม่เสร็จ)")
        return stations
        
    for tr in tbody.find_all('tr'):
        tds = tr.find_all('td')
        if len(tds) >= 9:
            name = tds[0].text.strip()
            diesel = tds[1].text.strip()
            g95 = tds[2].text.strip()
            g91 = tds[3].text.strip()
            e20 = tds[4].text.strip()
            # จัดรูปแบบตัวหนังสือรถขนส่งให้สวยงาม
            transport = tds[5].text.strip().replace('\n', ' ') 
            
            stations[name] = {
                "ดีเซล": diesel, "G95": g95, "G91": g91, "E20": e20, "รถขนส่ง": transport
            }
    return stations

def main():
    current_data = get_fuel_data()
    if not current_data:
        return
        
    # โหลดข้อมูลเก่ามาเช็ค
    old_data = {}
    if os.path.exists("data.json"):
        with open("data.json", "r", encoding="utf-8") as f:
            old_data = json.load(f)
            
    changed_stations = []
    
    # เทียบข้อมูลปั๊มต่อปั๊มว่ามีอะไรเปลี่ยนไปบ้าง
    for station, details in current_data.items():
        if station not in old_data or current_data[station] != old_data[station]:
            
            # ตกแต่งไอคอนให้ดูง่าย
            diesel_icon = "❌" if "หมด" in details['ดีเซล'] else "✅"
            g95_icon = "❌" if "หมด" in details['G95'] else "✅"
            
            msg = f"📍 {station}\n"
            msg += f"ดีเซล: {diesel_icon} {details['ดีเซล']} | G95: {g95_icon} {details['G95']}\n"
            msg += f"รถขนส่ง: 🚚 {details['รถขนส่ง']}"
            changed_stations.append(msg)
            
    if changed_stations:
        print(f"พบปั๊มที่สถานะเปลี่ยน {len(changed_stations)} แห่ง! กำลังส่งเข้า LINE...")
        
        # เอาข้อมูลที่เปลี่ยนมารวมกันเป็น 1 ข้อความ
        final_msg = "🔔 อัปเดตสถานะน้ำมันสิงห์บุรี!\n\n" + "\n\n".join(changed_stations)
        
        # ส่งข้อความ
        send_message(final_msg)
        
        # บันทึกข้อมูลล่าสุดทับลงไป
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(current_data, f, ensure_ascii=False, indent=2)
    else:
        print("✅ ข้อมูลสถานะน้ำมันยังเหมือนเดิม ไม่มีอัปเดตใหม่")

if __name__ == "__main__":
    main()
