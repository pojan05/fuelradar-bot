import os
import json
import time
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
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
    print("กำลังเปิดระบบดึงข้อมูลระดับลึก (Direct JavaScript Execution)...")
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    stations = {}
    
    try:
        driver.get(DATA_URL)
        print("รอระบบหลังบ้านโหลดข้อมูล 20 วินาที...")
        time.sleep(20) 
        
        # 💡 ไม้ตาย: สั่งให้เบราว์เซอร์ส่งคำสั่ง JavaScript ไปล้วงตัวแปร stationsData ออกมาตรงๆ 
        # ไม่ว่าจะอยู่ใน iframe หรือหน้าหลัก วิธีนี้จะข้ามผ่านการหาตาราง HTML ที่มักจะพังไปได้เลย
        print("กำลังล้วงข้อมูลจากระบบ...")
        script = """
            function findData(win) {
                if (win.stationsData) return win.stationsData;
                for (let i = 0; i < win.frames.length; i++) {
                    try {
                        let data = findData(win.frames[i]);
                        if (data) return data;
                    } catch (e) {}
                }
                return null;
            }
            return findData(window);
        """
        raw_data = driver.execute_script(script)
        
        if raw_data:
            print(f"✅ สำเร็จ! ล้วงข้อมูลดิบได้ทั้งหมด {len(raw_data)} ปั๊ม")
            for item in raw_data:
                name = str(item.get('StationName', '')).strip()
                district = str(item.get('District', '')).strip()
                
                if name and "อินทร์บุรี" in district:
                    stations[name] = {
                        "ดีเซล": str(item.get('Diesel', '-')).strip(),
                        "G95": str(item.get('Gas95', '-')).strip(),
                        "G91": str(item.get('Gas91', '-')).strip(),
                        "E20": str(item.get('E20', '-')).strip(),
                        "รถขนส่ง": str(item.get('TransportStatus', 'ปกติ')).strip(),
                        "อำเภอ": district
                    }
        else:
            print("❌ ไม่สามารถดึงตัวแปรข้อมูลได้ ระบบอาจมีการป้องกันเพิ่มเติม")

    except Exception as e:
        print(f"⚠️ Error: {e}")
    finally:
        driver.quit()
        
    return stations

def main():
    current_data = get_fuel_data()
    if not current_data:
        print("❌ ไม่ได้ข้อมูลกลับมา")
        return
        
    print(f"พบปั๊มในอินทร์บุรี {len(current_data)} แห่ง")
    
    # เช็คข้อมูลเก่าเพื่อแจ้งเตือนเฉพาะตอนเปลี่ยนสถานะ
    old_data = {}
    if os.path.exists("data.json"):
        with open("data.json", "r", encoding="utf-8") as f:
            try: old_data = json.load(f)
            except: old_data = {}
            
    changed_stations = []
    for station, details in current_data.items():
        if station not in old_data or current_data[station] != old_data[station]:
            diesel_icon = "❌" if "หมด" in details['ดีเซล'] else "✅"
            g95_icon = "❌" if "หมด" in details['G95'] else "✅"
            msg = f"📍 {station}\nดีเซล: {diesel_icon} {details['ดีเซล']} | G95: {g95_icon} {details['G95']}\nสถานะ: 🚚 {details['รถขนส่ง']}"
            changed_stations.append(msg)
            
    if changed_stations:
        print("พบการเปลี่ยนแปลง! กำลังแจ้งเตือน...")
        final_msg = "🔔 อัปเดตน้ำมัน อินทร์บุรี!\n\n" + "\n\n".join(changed_stations)
        send_message(final_msg)
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(current_data, f, ensure_ascii=False, indent=2)
    else:
        print("✅ สถานะน้ำมันยังเหมือนเดิม")

if __name__ == "__main__":
    main()
