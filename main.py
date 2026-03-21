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
    print("กำลังเริ่มระบบกวาดข้อมูลระดับลึก (Hybrid Extraction)...")
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
        print("รอระบบโหลดข้อมูล 25 วินาที (เพื่อให้ตารางขึ้นครบตามรูป debug)...")
        time.sleep(25) 
        
        # 📸 เก็บรูปไว้ดูอีกรอบเผื่อพลาด
        driver.save_screenshot("debug_current_run.png")
        
        # 💡 ไม้ตาย: ใช้ JavaScript ค้นหาทั้งตัวแปร และอ่านข้อความจากตาราง HTML พร้อมกันในทุก Frame
        print("กำลังควานหาข้อมูลในทุกชั้นของหน้าเว็บ...")
        script = """
            function findEverything(win) {
                // 1. ลองหาจากตัวแปรข้อมูลโดยตรง
                if (win.stationsData && win.stationsData.length > 0) return win.stationsData;
                
                // 2. ถ้าไม่เจอ ให้ลองอ่านตัวหนังสือจากตาราง tbody-dash
                let tbody = win.document.getElementById('tbody-dash');
                if (tbody) {
                    let rows = [];
                    for (let tr of tbody.querySelectorAll('tr')) {
                        let tds = tr.querySelectorAll('td');
                        if (tds.length >= 9) {
                            rows.push({
                                StationName: tds[0].innerText.trim(),
                                Diesel: tds[1].innerText.trim(),
                                Gas95: tds[2].innerText.trim(),
                                Gas91: tds[3].innerText.trim(),
                                E20: tds[4].innerText.trim(),
                                TransportStatus: tds[5].innerText.trim(),
                                District: tds[8].innerText.trim()
                            });
                        }
                    }
                    if (rows.length > 0) return rows;
                }
                
                // 3. วนหาในกล่องย่อย (iframes)
                for (let i = 0; i < win.frames.length; i++) {
                    try {
                        let res = findEverything(win.frames[i]);
                        if (res) return res;
                    } catch (e) {}
                }
                return null;
            }
            return findEverything(window);
        """
        raw_data = driver.execute_script(script)
        
        if raw_data:
            print(f"✅ สำเร็จ! กวาดข้อมูลมาได้ {len(raw_data)} ปั๊ม")
            for item in raw_data:
                name = str(item.get('StationName', '')).strip()
                district = str(item.get('District', '')).strip()
                
                # กรองเฉพาะอำเภออินทร์บุรีตามที่พี่ต้องการ
                if name and "อินทร์บุรี" in district:
                    stations[name] = {
                        "ดีเซล": str(item.get('Diesel', '-')).strip(),
                        "G95": str(item.get('Gas95', '-')).strip(),
                        "G91": str(item.get('Gas91', '-')).strip(),
                        "E20": str(item.get('E20', '-')).strip(),
                        "รถขนส่ง": str(item.get('TransportStatus', 'ปกติ')).replace('\\n', ' ').strip(),
                        "อำเภอ": district
                    }
        else:
            print("❌ ไม่พบข้อมูลในทุกชั้นของหน้าเว็บ")

    except Exception as e:
        print(f"⚠️ Error: {e}")
    finally:
        driver.quit()
        
    return stations

def main():
    current_data = get_fuel_data()
    if not current_data:
        return
        
    print(f"พบข้อมูลอินทร์บุรี {len(current_data)} ปั๊ม")
    
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
            msg = f"📍 {station}\\nดีเซล: {d_icon} {details['ดีเซล']} | G95: {g_icon} {details['G95']}\\n🚚 {details['รถขนส่ง']}"
            changed_stations.append(msg)
            
    if changed_stations:
        print("กำลังส่งแจ้งเตือนเข้า LINE...")
        final_msg = "🔔 อัปเดตสถานะน้ำมัน อินทร์บุรี!\\n\\n" + "\\n\\n".join(changed_stations)
        send_message(final_msg)
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(current_data, f, ensure_ascii=False, indent=2)
    else:
        print("✅ ข้อมูลยังเหมือนเดิม")

if __name__ == "__main__":
    main()
