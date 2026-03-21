import os
import json
import time
import requests
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
    
    # When running in environments like GitHub Actions the chromedriver binary may
    # not already be installed on the runner.  Using webdriver‑manager to fetch
    # a matching chromedriver avoids version mismatch issues.  If the environment
    # already provides a bundled driver (e.g. in a Docker container) this will
    # simply return the existing binary.
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    stations = {}
    
    try:
        driver.get(DATA_URL)
        
        print("กำลังรอและมุดเข้า iframe...")
        # Some versions of the FuelRadar web app change the id of the sandbox
        # iframe over time.  Try to locate it by id first; if not found fall
        # back to the first iframe on the page.  Then switch into that frame
        # before executing any scripts.  A generous wait helps with slow
        # network connections.
        try:
            iframe = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.ID, "sandboxFrame"))
            )
        except Exception:
            # fallback: pick the first iframe
            iframe = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "iframe"))
            )
        driver.switch_to.frame(iframe)
        print("มุดเข้า iframe สำเร็จ! กำลังรอข้อมูลโหลด...")

        # รอให้ตัวแปร stationsData มีข้อมูล (ข้อมูลถูกดึงมาแล้ว)
        # เราใช้ JavaScript เพื่อดึงตัวแปรนั้นออกมาตรงๆ เลย จะได้ไม่ต้องแกะ HTML
        # Wait for the stationsData variable to become available and populated.
        # Using a lambda instead of a custom EC class allows us to run a JS
        # snippet repeatedly until it returns a truthy value.  If the page
        # implementation changes and stationsData is not defined the wait will
        # time out after 30 seconds and be handled by the surrounding try/except.
        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script("return (typeof stationsData !== 'undefined') && stationsData.length > 0")
        )
        
        try:
            # Attempt to extract the JavaScript variable stationsData directly
            raw_data = driver.execute_script("return stationsData;")
        except Exception:
            raw_data = None
        if raw_data:
            print(f"ดึงข้อมูลดิบสำเร็จ พบทั้งหมด {len(raw_data)} ปั๊ม")
            # When stationsData is available, iterate over its objects
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
                    print(f"✅ พบข้อมูล: {name}")
        else:
            # Fallback: parse the rendered dashboard table directly if the JS
            # variable is not accessible (e.g. due to cross‑origin policies)
            print("ไม่พบตัวแปร stationsData ใช้การขูดข้อมูลจากตารางแทน")
            # Wait for at least one row to appear in the dashboard table
            rows = WebDriverWait(driver, 30).until(
                lambda d: d.find_elements(By.CSS_SELECTOR, "#table-dash tbody tr")
            )
            print(f"พบตารางข้อมูลจำนวน {len(rows)} แถว กำลังวิเคราะห์...")
            for row in rows:
                cells = row.find_elements(By.TAG_NAME, "td")
                # Expect at least 9 cells: StationName, Diesel, G95, G91, E20, Transport, lastUpdate, Brand, District, (and maybe coordinates)
                if len(cells) < 9:
                    continue
                name = cells[0].text.strip()
                diesel = cells[1].text.strip() or "-"
                g95 = cells[2].text.strip() or "-"
                g91 = cells[3].text.strip() or "-"
                e20 = cells[4].text.strip() or "-"
                transport = cells[5].text.strip() or "ปกติ"
                # If transport column contains warning icon text such as "ล่าช้า", keep it
                district = cells[8].text.strip() if len(cells) > 8 else ""
                if name and "อินทร์บุรี" in district:
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
        # Print the exception for debugging.  Selenium sometimes raises a
        # generic WebDriverException without an informative message; in that case
        # let the caller know that something went wrong extracting the data.
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
        # ถ้าเป็นปั๊มใหม่ที่ไม่เคยมี หรือ ข้อมูลเปลี่ยน
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
        
        # ถ้ายาวเกินไป LINE จะส่งไม่ผ่าน ให้หั่นส่งทีละนิดถ้าจำเป็น (แต่ 15 ปั๊มน่าจะผ่านสบายๆ)
        final_msg = "🔔 อัปเดตสถานะน้ำมัน อินทร์บุรี!\n\n" + "\n\n".join(changed_stations)
        send_message(final_msg)
        
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(current_data, f, ensure_ascii=False, indent=2)
    else:
        print("✅ ข้อมูลสถานะน้ำมันในอินทร์บุรียังเหมือนเดิม ไม่มีอัปเดตใหม่")

if __name__ == "__main__":
    main()
