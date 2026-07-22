import base64
import hashlib
import hmac
import struct
import time
import json
import os
import requests
from playwright.sync_api import sync_playwright

ALLOWED_PLATFORMS = {
    "BG",
    "CHOICE",
    "DB CASINO",
    "EVOLUTION",
    "EZUGI",
    "HOTROAD",
    "PP LIVE",
    "PRETTY GAMING",
    "PT LIVE",
    "SEXY"
}

def generate_totp(secret: str) -> str:
    secret = secret.strip().replace(" ", "").upper()
    missing_padding = len(secret) % 8
    if missing_padding != 0:
        secret += "=" * (8 - missing_padding)
    key = base64.b32decode(secret, casefold=True)
    time_step = int(time.time()) // 30
    msg = struct.pack(">Q", time_step)
    mac = hmac.new(key, msg, hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    binary = struct.unpack(">I", mac[offset : offset + 4])[0] & 0x7FFFFFFF
    code = binary % 1000000
    return f"{code:06d}"

def send_whatsapp_report(data, target_number="120363426571241502@g.us"):
    api_url = 'https://deswa.io7.my/api/external/send-message'
    
    # Filter data to keep only specified platforms
    filtered_data = [item for item in data if item["game_platform"].strip().upper() in ALLOWED_PLATFORMS]
    
    lines = [
        "📊 Winbox Live Casino Rebate List",
        "----------------------------------------",
        "Platform | Curr | Shareholder | Sup. Cash | Cash",
        "----------------------------------------"
    ]
    
    for item in filtered_data:
        lines.append(f"{item['game_platform']} | {item['currency']} | {item['shareholder']} | {item['superior_cash_player']} | {item['cash_player']}")
        
    message_text = "\n".join(lines)
    
    payload = {
        'number': target_number,
        'message': message_text
    }
    
    print(f"Sending formatted WhatsApp report ({len(filtered_data)} items) to {target_number}...")
    try:
        response = requests.post(api_url, json=payload, timeout=15)
        print(f"WhatsApp API Response Status: {response.status_code}")
        print(f"WhatsApp API Response Body: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Failed to send WhatsApp message: {e}")
        return False

def run():
    secret_key = os.environ.get("TOTP_SECRET", "IQ4TQMRSHBCTMNBVHFDDGNRUG43EMOCBGA4TARJUGI2UKRKFGRDA")
    username = os.environ.get("SCRAPER_USERNAME", "neuron226688")
    password = os.environ.get("SCRAPER_PASSWORD", "Aaaa8888")
    whatsapp_target = os.environ.get("WHATSAPP_TARGET", "120363426571241502@g.us")

    # Run headless by default for cloud servers (Render / Docker)
    headless_mode = os.environ.get("HEADLESS", "true").lower() == "true"

    with sync_playwright() as p:
        print(f"1. Launching browser (headless={headless_mode})...")
        browser = p.chromium.launch(headless=headless_mode)
        context = browser.new_context()
        page = context.new_page()
        
        print("2. Navigating to login page...")
        page.goto("https://www.agent4u.cc/Account/Login")
        page.wait_for_load_state("networkidle")
        
        print("3. Filling username and password...")
        page.locator("#UserName").fill(username)
        page.locator("#Password").fill(password)
        
        sms_field = page.locator("#smsCode")
        btn_submit = page.locator("#btnSubmit")

        if not sms_field.is_visible():
            btn_submit.click()
            try:
                page.wait_for_selector("#smsCode", timeout=5000)
            except Exception:
                pass

        if sms_field.is_visible():
            code = generate_totp(secret_key)
            print(f"4. Entering 2FA Code: {code}")
            sms_field.fill(code)
            page.wait_for_timeout(500)
            
            if btn_submit.is_visible():
                btn_submit.click()
            else:
                sms_field.press("Enter")
            
        print("5. Waiting for login authentication & redirect...")
        try:
            page.wait_for_url("**/AgentHome*", timeout=20000)
        except Exception:
            page.wait_for_timeout(5000)
            
        print("Logged in! Current URL:", page.url)

        # Trigger commission modal via direct JS function call
        print("6. Triggering GetCurrentAccountCommission()...")
        try:
            page.evaluate("if (typeof GetCurrentAccountCommission === 'function') { GetCurrentAccountCommission(); }")
            page.wait_for_timeout(2000)
        except Exception as e:
            print("Notice on JS evaluate:", e)

        # Wait for modal table
        try:
            page.wait_for_selector("#modal-body table tbody tr", timeout=10000)
        except Exception:
            trigger = page.locator("text=Return Commission List")
            if trigger.is_visible():
                trigger.click(force=True)
                page.wait_for_timeout(2000)
            page.wait_for_selector("#modal-body table tbody tr", timeout=15000)

        print("7. Scraping Return Commission List table...")
        rows = page.locator("#modal-body table tbody tr").all()
        
        commission_data = []
        for row in rows:
            cols = row.locator("td").all_text_contents()
            if len(cols) >= 5:
                def parse_num(val_str):
                    val_str = val_str.strip()
                    try:
                        val = float(val_str)
                        return int(val) if val.is_integer() else val
                    except ValueError:
                        return val_str

                item = {
                    "game_platform": cols[0].strip(),
                    "currency": cols[1].strip(),
                    "shareholder": parse_num(cols[2]),
                    "superior_cash_player": parse_num(cols[3]),
                    "cash_player": parse_num(cols[4])
                }
                commission_data.append(item)

        print(f"8. Successfully scraped {len(commission_data)} records total.")
        
        # Save full data
        output_filename = "commission_list.json"
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(commission_data, f, indent=2, ensure_ascii=False)

        # Save filtered data
        filtered_data = [item for item in commission_data if item["game_platform"].strip().upper() in ALLOWED_PLATFORMS]
        filtered_filename = "filtered_commission_list.json"
        with open(filtered_filename, "w", encoding="utf-8") as f:
            json.dump(filtered_data, f, indent=2, ensure_ascii=False)
        
        # Send formatted report to WhatsApp
        send_whatsapp_report(commission_data, whatsapp_target)
        
        context.close()
        browser.close()
        print("Done!")

if __name__ == "__main__":
    run()
