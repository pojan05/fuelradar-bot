import os
import json
import time
import requests
from datetime import datetime
import pytz
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# ดึงค่า Secrets
LINE_TOKEN = os.environ.get("LINE_TOKEN")
LINE_TO_ID = os.environ.get("LINE_TO_ID")
LINE_TOKEN_2 = os.environ.get("LINE_TOKEN_2")
LINE_TO_ID_2 = os.environ.get("LINE_TO_ID_2")

DATA_URL = "https://script.google.com/macros/s/AKfycbxflVoeKNYwHDhMFqoZkeKUR0AG5GI4jwfqefySHxXa6MnDdBn7NbTkT4NjN-WbgYQrMQ/exec"

def send_message(text):
    url = 'https://api.line.me/v2/bot/message/push'
    targets = [
        {"token": LINE_TOKEN, "to_id": LINE_TO_ID, "name": "Bot 1"},
        {"token": LINE_TOKEN_2, "to_id": LINE_TO_ID_2, "name": "Bot 2 (Alieninburi)"} 
    ]
    
    for target in targets:
        token = target["token"]
        to_id = target["to_id"]
        if not token or not to_id: continue
            
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
        payload = {"to": to_id, "messages": [{"type": "text", "text": text[:5000]}]}
        try:
            res = requests.post(url, headers=headers, json=payload)
            res.raise_for_status()
        except Exception as e:
            print(f"❌ ส่ง LINE ไม่สำเร็จ ({target['name']}): {e}")

def get_price_diff(new_val, old_val):
    """ฟังก์ชันคำนวณส่วนต่างราคาน้ำมัน"""
    if not old_val: return " (ใหม่)"
    try:
        # พยายามแปลงเป็นตัวเลขเพื่อคำนวณ
        n = float(new_val.replace(',', ''))
        o = float(old_val.replace(',', ''))
        diff = n - o
        if diff > 0: return f" (⬆️+{diff:.2f})"
        elif diff < 0: return f" (⬇️{diff:.2f})"
        else: return " (คงเดิม)"
    except ValueError:
        # กรณีข้อมูลเป็นตัวหนังสือ เช่น "หมด" 
        if new_val != old_val:
            return f" (🔄เปลี่ยนจาก {old_val})"
        return " (คงเดิม)"

def scrape_logic():
    """ฟังก์ชันหลักในการดึงข้อมูลจากเว็บ"""
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    stations = {}
    
    try:
        driver.get(DATA_URL)
        # รอ Sandbox Frame
        iframe1 = WebDriverWait(driver, 40).until(EC.presence_of_element_located((By.ID, "sandboxFrame")))
        driver.switch_to.frame(iframe1)
        
        # รอ Content Iframe
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
        iframe2 = driver.find_element(By.TAG_NAME, "iframe")
        driver.switch_to.frame(iframe2)
        
        # รอข้อมูลตาราง
        WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.ID, "tbody-dash")))
        time.sleep(5) 
        
        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        tbody = soup.find('tbody', id='tbody-dash')
        
        if tbody:
            rows = tbody.find_all('tr')
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
                            "อัปเดตล่าสุด": tds[6].text.strip(),
                            "อำเภอ": district
                        }
    finally:
        driver.quit()
    return stations

def get_fuel_data_with_retry(max_retries=3):
    """ระบบ Retry หากดึงข้อมูลได้ 0 แห่ง"""
    for i in range(max_retries):
        print(f"🔍 พยายามดึงข้อมูล ครั้งที่ {i+1}/{max_retries}...")
        data = scrape_logic()
        if data:
            print(f"✅ ดึงข้อมูลสำเร็จ! พบปั๊ม {len(data)} แห่ง")
            return data
        print("⚠️ รอบนี้ไม่พบข้อมูล (อาจเพราะเว็บโหลดไม่ทัน) กำลังรอเพื่อลองใหม่...")
        time.sleep(10)
    return {}

def main():
    tz = pytz.timezone('Asia/Bangkok')
    now = datetime.now(tz)
    thai_now_str = now.strftime('%Y-%m-%d %H:%M:%S')
    
    # 🕒 เงื่อนไขส่งสรุปตอน 6 โมงเช้า (เช็คว่าเวลาอยู่ช่วง 06:00 - 06:09 น.)
    is_summary_time = (now.hour == 6 and now.minute < 10)
    
    print("-" * 30)
    print(f"🚀 Bot Start: {thai_now_str} (Summary Mode: {is_summary_time})")
    
    current_data = get_fuel_data_with_retry()
    
    if not current_data:
        print("🛑 ดึงข้อมูลไม่ได้ครบตามจำนวนครั้งที่กำหนด ข้ามการทำงาน")
        return
        
    old_data = {}
    if os.path.exists("data.json"):
        with open("data.json", "r", encoding="utf-8") as f:
            try: old_data = json.load(f)
            except: old_data = {}
            
    updates = []
    for station, d in current_data.items():
        old = old_data.get(station, {})
        has_changed = (station not in old_data) or (d != old)
        
        # ตรวจสอบการเปลี่ยนแปลง หรือ ถ้าเป็นโหมดสรุปตอนเช้า ให้ดึงข้อมูลมาทำข้อความเลย
        if is_summary_time or has_changed:
            def get_icon(status):
                if "มี" in status: return "✅"
                if "หมด" in status: return "❌"
                return "⚪"

            # ถ้าเป็นรอบ 6 โมงเช้า ให้แสดงส่วนต่างราคาด้วย
            diff_diesel = get_price_diff(d['ดีเซล'], old.get('ดีเซล')) if is_summary_time else ""
            diff_g95 = get_price_diff(d['G95'], old.get('G95')) if is_summary_time else ""
            diff_g91 = get_price_diff(d['G91'], old.get('G91')) if is_summary_time else ""
            diff_e20 = get_price_diff(d['E20'], old.get('E20')) if is_summary_time else ""

            icon = "📊" if is_summary_time else "📍"
            msg = f"{icon} {station}\n"
            msg += f"⛽ ดีเซล:{get_icon(d['ดีเซล'])} {d['ดีเซล']}{diff_diesel}\n"
            msg += f"⛽ G95:{get_icon(d['G95'])} {d['G95']}{diff_g95}\n"
            msg += f"⛽ G91:{get_icon(d['G91'])} {d['G91']}{diff_g91}\n"
            msg += f"⛽ E20:{get_icon(d['E20'])} {d['E20']}{diff_e20}\n"
            
            trans_icon = "🚚" if "ลงน้ำมัน" in d['รถขนส่ง'] or "จัดส่ง" in d['รถขนส่ง'] else "✅"
            msg += f"{trans_icon} รถขนส่ง: {d['รถขนส่ง']}\n"
            msg += f"🕒 อัปเดตล่าสุด: {d['อัปเดตล่าสุด']}"
            updates.append(msg)
            
    if updates:
        print(f"🔔 ส่งข้อมูล: {len(updates)} แห่ง")
        header_title = "📊 รายงานสรุปราคาน้ำมันเช้านี้" if is_summary_time else "🔔 แจ้งอัปเดตน้ำมัน"
        
        for i in range(0, len(updates), 5):
            chunk = updates[i:i+5]
            final_msg = f"{header_title} (อินทร์บุรี)\n⏰ ตรวจสอบเมื่อ: {thai_now_str}\n\n" + "\n\n".join(chunk)
            send_message(final_msg)
            time.sleep(2)
            
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(current_data, f, ensure_ascii=False, indent=2)
    else:
        print("✅ ข้อมูลยังเป็นปัจจุบัน")

if __name__ == "__main__":
    main()
