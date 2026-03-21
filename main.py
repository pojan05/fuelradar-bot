import os
import json
import time
import requests
from seleniumwire import webdriver # ใช้ selenium-wire แทน
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
    print("กำลังเปิดเบราว์เซอร์จำลอง (ระบบดักจับ API)...")
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--ignore-certificate-errors') # ข้ามปัญหาใบรับรอง
    
    driver = webdriver.Chrome(options=options)
    stations = {}
    
    try:
        print("กำลังเปิดเว็บและดักจับข้อมูล...")
        driver.get(DATA_URL)
        
        # รอให้เบราว์เซอร์ดาวน์โหลดข้อมูลทั้งหมด 15 วินาที
        time.sleep(15)
        
        # ค้นหาคำร้องขอ (Request) ที่มีข้อมูลน้ำมัน
        found_data = False
        print("กำลังวิเคราะห์ข้อมูลจราจรบนเว็บ...")
        
        for request in driver.requests:
            if request.response:
                # ลองอ่านข้อมูลที่ตอบกลับมา
                try:
                    body_bytes = request.response.body
                    if not body_bytes:
                        continue
                        
                    body_str = body_bytes.decode('utf-8')
                    
                    # เช็คว่าใช่ข้อมูล JSON ของปั๊มน้ำมันไหม (มักจะมีคำว่า StationName)
                    if '"StationName"' in body_str and '"Diesel"' in body_str:
                        raw_data = json.loads(body_str)
                        print(f"✅ ดักจับ API สำเร็จ! พบข้อมูล {len(raw_data)} ปั๊ม")
                        
                        for item in raw_data:
                            district = str(item.get('District', '')).strip()
                            name = str(item.get('StationName', '')).strip()
                            
                            if name and "อินทร์บุรี" in district:
                                stations[name] = {
                                    "ดีเซล": str(item.get('Diesel', '-')).strip(),
                                    "G95": str(item.get('Gas95', '-')).strip(),
                                    "G91": str(item.get('Gas91', '-')).strip(),
                                    "E20": str(item.get('E20', '-')).strip(),
                                    "รถขนส่ง": str(item.get('TransportStatus', 'ปกติ')).strip(),
                                    "อำเภอ": district
                                }
                        found_data = True
                        break # เจอข้อมูลแล้ว หยุดหาได้
                except Exception as e:
                    # บาง request อ่านไม่ได้ ให้ข้ามไป
                    pass
        
        if not found_data:
            print("❌ ไม่พบ API ที่มีข้อมูลน้ำมัน (เว็บอาจจะยังโหลดไม่เสร็จ หรือโดนบล็อก)")
            
    except Exception as e:
        print(f"⚠️ เกิดข้อผิดพลาดในระบบหลัก: {e}")
        
    finally:
        driver.quit()
        
    return stations

def main():
    current_data = get_fuel_data()
    if not current_data:
        print("⚠️ ไม่ได้ข้อมูลกลับมาเลย หยุดการทำงานชั่วคราว")
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
        print(f"พบปั๊มในอินทร์บุรีอัปเดต {len(changed_stations)} แห่ง! กำลังส่งเข้า LINE...")
        final_msg = "🔔 อัปเดตสถานะน้ำมัน อินทร์บุรี!\n\n" + "\n\n".join(changed_stations)
        send_message(final_msg)
        
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(current_data, f, ensure_ascii=False, indent=2)
    else:
        print("✅ ข้อมูลสถานะน้ำมันในอินทร์บุรียังเหมือนเดิม ไม่มีอัปเดตใหม่")

if __name__ == "__main__":
    main()
