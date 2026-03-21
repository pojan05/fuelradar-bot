import os
import requests

# ดึงรหัสลับจาก GitHub
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

def main():
    print("กำลังดึงข้อมูลจากเว็บ...")
    response = requests.get(DATA_URL)
    current_data = response.text
    
    # อ่านข้อมูลเก่าที่เคยบันทึกไว้
    old_data = ""
    if os.path.exists("data.txt"):
        with open("data.txt", "r", encoding="utf-8") as f:
            old_data = f.read()
            
    # ถ้าข้อมูลใหม่ ไม่เหมือน ข้อมูลเก่า แปลว่ามีการอัปเดต!
    if current_data != old_data:
        print("พบข้อมูลอัปเดต! กำลังแจ้งเตือนผ่าน LINE...")
        send_message("⛽ ระบบ FuelRadar มีการอัปเดตข้อมูลสถานะน้ำมันครับ!")
        
        # บันทึกข้อมูลใหม่ลงไปจำไว้
        with open("data.txt", "w", encoding="utf-8") as f:
            f.write(current_data)
    else:
        print("ข้อมูลเหมือนเดิม ยังไม่มีอะไรเปลี่ยนแปลง")

if __name__ == "__main__":
    main()
