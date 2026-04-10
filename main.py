import os
import re
import json
import random
import requests
import math
import time
from datetime import datetime, timedelta, timezone
import pytz
import ee
from google import genai
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# ==========================================
# ⚙️ ดึง Secrets สำหรับส่ง LINE
# ==========================================
LINE_TOKEN = os.environ.get("LINE_TOKEN")
LINE_TOKEN_2 = os.environ.get("LINE_TOKEN_2")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") 

tz = pytz.timezone('Asia/Bangkok')
now = datetime.now(tz)
THAI_MONTHS = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
date_str = f"{now.day} {THAI_MONTHS[now.month - 1]} {now.year + 543}"
time_str = now.strftime("%H:%M น.")

# ตรวจสอบว่าเป็นช่วง 6 โมงเช้าหรือไม่
is_morning = now.hour == 6

# ==========================================
# 🟢 ฟังก์ชันส่ง LINE
# ==========================================
def send_line_message(text):
    url = 'https://api.line.me/v2/bot/message/broadcast'
    targets = [
        {"token": LINE_TOKEN, "name": "Bot 1"},
        {"token": LINE_TOKEN_2, "name": "Bot 2 (Alieninburi)"} 
    ]
    for target in targets:
        token = target["token"]
        if not token: continue
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
        payload = {"messages": [{"type": "text", "text": text[:5000]}]}
        try:
            res = requests.post(url, headers=headers, json=payload)
            if res.status_code == 200:
                print(f"✅ ส่ง LINE สำเร็จ ({target['name']})")
        except Exception as e:
            print(f"❌ ส่ง LINE ล้มเหลว ({target['name']}): {e}")

# ==========================================
# ⛽ ส่วนที่ 1: ระบบราคาน้ำมัน (เฉพาะเช้า)
# ==========================================
DATA_URL = "https://script.google.com/macros/s/AKfycbxflVoeKNYwHDhMFqoZkeKUR0AG5GI4jwfqefySHxXa6MnDdBn7NbTkT4NjN-WbgYQrMQ/exec"

def get_price_diff(new_val, old_val):
    if not old_val: return " (ใหม่)"
    try:
        n, o = float(new_val.replace(',', '')), float(old_val.replace(',', ''))
        diff = n - o
        if diff > 0: return f" (⬆️+{diff:.2f})"
        elif diff < 0: return f" (⬇️{diff:.2f})"
        else: return " (คงเดิม)"
    except ValueError:
        return f" (🔄เปลี่ยนจาก {old_val})" if new_val != old_val else " (คงเดิม)"

def scrape_fuel_data():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    stations = {}
    try:
        driver.get(DATA_URL)
        iframe1 = WebDriverWait(driver, 40).until(EC.presence_of_element_located((By.ID, "sandboxFrame")))
        driver.switch_to.frame(iframe1)
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))
        iframe2 = driver.find_element(By.TAG_NAME, "iframe")
        driver.switch_to.frame(iframe2)
        WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.ID, "tbody-dash")))
        time.sleep(5) 
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        tbody = soup.find('tbody', id='tbody-dash')
        if tbody:
            for tr in tbody.find_all('tr'):
                tds = tr.find_all('td')
                if len(tds) >= 9 and "อินทร์บุรี" in tds[8].text.strip():
                    stations[tds[0].text.strip()] = {
                        "ดีเซล": tds[1].text.strip(), "G95": tds[2].text.strip(),
                        "G91": tds[3].text.strip(), "E20": tds[4].text.strip(),
                        "รถขนส่ง": tds[5].text.strip().replace('\n', ' '), "อัปเดตล่าสุด": tds[6].text.strip()
                    }
    except Exception as e: print(f"Error scraping fuel: {e}")
    finally: driver.quit()
    return stations

def process_fuel_report():
    print("🔍 กำลังดึงข้อมูลราคาน้ำมัน (โหมดสรุปเช้า)...")
    current_data = scrape_fuel_data()
    if not current_data: return
    old_data = {}
    if os.path.exists("data.json"):
        with open("data.json", "r", encoding="utf-8") as f:
            try: old_data = json.load(f)
            except: pass
    updates = []
    for station, d in current_data.items():
        old = old_data.get(station, {})
        def get_icon(s): return "✅" if "มี" in s else "❌" if "หมด" in s else "⚪"
        msg = f"📊 {station}\n"
        msg += f"⛽ ดีเซล:{get_icon(d['ดีเซล'])} {d['ดีเซล']}{get_price_diff(d['ดีเซล'], old.get('ดีเซล'))}\n"
        msg += f"⛽ G95:{get_icon(d['G95'])} {d['G95']}{get_price_diff(d['G95'], old.get('G95'))}\n"
        msg += f"⛽ G91:{get_icon(d['G91'])} {d['G91']}{get_price_diff(d['G91'], old.get('G91'))}\n"
        msg += f"⛽ E20:{get_icon(d['E20'])} {d['E20']}{get_price_diff(d['E20'], old.get('E20'))}\n"
        updates.append(msg)
            
    if updates:
        for i in range(0, len(updates), 5):
            chunk = updates[i:i+5]
            final_msg = f"📊 สรุปราคาน้ำมันอินทร์บุรี\n⏰ {now.strftime('%d/%m/%Y %H:%M')}\n\n" + "\n\n".join(chunk)
            send_line_message(final_msg)
            time.sleep(2)
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(current_data, f, ensure_ascii=False, indent=2)

# ==========================================
# 🌤️ ส่วนที่ 2: ระบบข้อมูลอินทร์บุรี (ส่งเข้า LINE อย่างเดียว)
# ==========================================
def get_dist(lat1, lon1, lat2, lon2):
    R = 6371
    dlat, dlon = math.radians(float(lat2) - float(lat1)), math.radians(float(lon2) - float(lon1))
    a = math.sin(dlat/2)**2 + math.cos(math.radians(float(lat1))) * math.cos(math.radians(float(lat2))) * math.sin(dlon/2)**2
    return R * (2 * math.asin(math.sqrt(a)))

def get_hotspots():
    EE_JSON_KEY = os.environ.get("EE_JSON_KEY")
    if not EE_JSON_KEY: return "N/A"
    try:
        json_key = json.loads(EE_JSON_KEY)
        credentials = ee.ServiceAccountCredentials(json_key['client_email'], key_data=EE_JSON_KEY)
        ee.Initialize(credentials)
        inburi_area = ee.Geometry.Point([100.3273, 15.0076]).buffer(10000)
        end_date = ee.Date(datetime.now())
        start_date = end_date.advance(-24, 'hour')
        fire_col = ee.ImageCollection("FIRMS").filterBounds(inburi_area).filterDate(start_date, end_date)
        return fire_col.size().getInfo()
    except Exception as e:
        print(f"⚠️ ระบบดาวเทียมขัดข้อง: {e}")
        return "N/A"

def get_accurate_pm25():
    lat, lon = 15.0076, 100.3273
    headers = {'User-Agent': 'Mozilla/5.0'}
    all_sources = [] 
    try:
        url = f"https://pm25.gistda.or.th/rest/getPM25byLocation?lat={lat}&lng={lon}&t={int(time.time())}"
        data = requests.get(url, headers=headers, timeout=15, verify=False).json().get('data', {})
        if 'pm25' in data and data['pm25']: all_sources.append({'pm25': float(data['pm25']), 'dist': 0, 'priority': 0})
    except: pass
    try:
        res = requests.get(f"http://air4thai.pcd.go.th/services/getNewAQI_JSON.php?t={int(time.time())}", headers=headers, timeout=15, verify=False)
        for st in res.json().get('stations', []):
            pm25_val = st.get('LastUpdate', {}).get('PM25', {}).get('value')
            if pm25_val and pm25_val != "-":
                dist = get_dist(lat, lon, st.get('lat'), st.get('long'))
                if dist <= 50: all_sources.append({'pm25': float(pm25_val), 'dist': dist, 'priority': 1})
    except: pass
    if not all_sources: return "N/A"
    all_sources.sort(key=lambda x: (x['priority'], x['dist']))
    return f"{all_sources[0]['pm25']:.1f}"

def get_weather():
    TOMORROW_API_KEY = os.environ.get("TOMORROW_API_KEY")
    temp, pm25, rain_prob, humidity, wind, uv = "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"
    if TOMORROW_API_KEY:
        try:
            tmr_url = f"https://api.tomorrow.io/v4/weather/forecast?location=14.9961,100.3253&apikey={TOMORROW_API_KEY}"
            res = requests.get(tmr_url, timeout=10).json()
            current_data = res['timelines']['minutely'][0]['values']
            humidity, wind = round(current_data['humidity'], 1), round(current_data['windSpeed'], 1)
            rain_prob = max([h['values']['precipitationProbability'] for h in res['timelines']['hourly'][:12]])
        except: pass
    try:
        om_url = "https://api.open-meteo.com/v1/forecast?latitude=14.9961&longitude=100.3253&current=temperature_2m,uv_index&timezone=Asia%2FBangkok"
        res = requests.get(om_url, timeout=10).json()
        temp, uv = res['current']['temperature_2m'], res['current'].get('uv_index', 'N/A')
    except: pass
    return temp, pm25, rain_prob, humidity, wind, uv

def get_inburi_data():
    water_level, bank_level = None, 15.10
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get("https://www.thaiwater.net/api/v1/thaiwater30/public/waterlevel", headers=headers, timeout=20)
        if res.status_code == 200:
            for s in res.json().get('waterlevel_data', []):
                if s.get('station', {}).get('station_old_code', '') == 'C.3': 
                    water_level = float(s.get('water_level', 0))
                    break
    except: pass
    return water_level, bank_level

def fetch_chao_phraya_dam_discharge():
    url = f"https://tiwrm.hii.or.th/DATA/REPORT/php/chart/chaopraya/small/chaopraya.php?cb={random.randint(10000, 99999)}"
    try:
        res = requests.get(url, timeout=20)
        match = re.search(r'var json_data = (\[.*\]);', res.text)
        if match:
            val = json.loads(match.group(1))[0]['itc_water']['C13']['storage']
            return float(val) if isinstance(val, (int, float)) else float(str(val).replace(',', ''))
    except: pass
    return None

def process_inburi_report():
    print("🌍 กำลังดึงข้อมูลสภาพแวดล้อมอินทร์บุรี (เพื่อส่ง LINE)...")
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    temp, _, rain_prob, humidity, wind, uv = get_weather() 
    pm25 = get_accurate_pm25()
    wl, bank_level = get_inburi_data()
    discharge = fetch_chao_phraya_dam_discharge()
    hotspots = get_hotspots()
    
    wl_text = f"ความสูง {wl} ม.รทก. (ห่างจากตลิ่ง {round(bank_level - wl, 2)} เมตร)" if wl else "รออัปเดต"
    discharge_text = f"{discharge} ลบ.ม./วินาที" if discharge else "รออัปเดต"
    
    if hotspots == "N/A": hotspot_text = "ระบบตรวจจับขัดข้องชั่วคราว"
    elif hotspots == 0: hotspot_text = "0 จุด (ไม่พบการเผาไหม้ในพื้นที่ ปลอดภัย)"
    else: hotspot_text = f"ตรวจพบ {hotspots} จุด (เฝ้าระวังการเผาไหม้)"

    prompt = f"""
    ช่วยสรุปข้อมูลเพื่อส่งแจ้งเตือนใน LINE ให้กระชับ อ่านง่าย สบายตา:
    ข้อมูลดิบ: {date_str} {time_str}
    - อากาศ: {temp}°C, แดด(UV): {uv}, ฝน: {rain_prob}%, ลม: {wind} m/s
    - ฝุ่น PM 2.5: {pm25} 
    - ดาวเทียม VIIRS (รัศมี 10 กม.): {hotspot_text}
    - ระดับน้ำอินทร์บุรี: {wl_text}
    - ระบายน้ำเขื่อนเจ้าพระยา: {discharge_text}
    
    ให้สรุปออกมาเป็นหัวข้อสั้นๆ แบบนี้:
    📍 **รายงานสถานการณ์อินทร์บุรี** ({time_str})
    🌡️ อากาศ: ...
    😷 ฝุ่น: ...
    🔥 จุดความร้อน: ...
    🌊 ระดับน้ำ: ...
    🛑 เขื่อนเจ้าพระยา: ...
    """
    
    final_post = ""
    for attempt in range(3):
        try:
            res = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            final_post = res.text.strip()
            break
        except: time.sleep(5)
    
    if not final_post:
        final_post = f"📍 **รายงานสถานการณ์อินทร์บุรี** (ระบบ AI ขัดข้องชั่วคราว)\nอุณหภูมิ: {temp}°C | โอกาสฝน: {rain_prob}%\nระดับน้ำ: {wl_text}\nระบายน้ำ: {discharge_text}"

    # ส่งเข้า LINE เท่านั้น! (ไม่มี Webhook เพจแล้ว)
    send_line_message(final_post)

# ==========================================
# 🚀 ตัวควบคุมหลัก
# ==========================================
if __name__ == "__main__":
    print("="*40)
    print(f"🚀 เริ่มรันระบบ Fuel & Info Bot: {date_str} เวลา {time_str} (โหมดเช้า: {is_morning})")
    print("="*40)
    
    if is_morning:
        process_fuel_report()
    else:
        print("⏭️ ข้ามการเช็กน้ำมัน (ดึงเฉพาะช่วง 6 โมงเช้า)")
        
    print("-"*40)
    process_inburi_report()
    print("="*40)
    print("🎉 ทำงานเสร็จสมบูรณ์")
