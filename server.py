import os
import json
import threading
from datetime import datetime
from flask import Flask, jsonify, render_template, request
from apscheduler.schedulers.background import BackgroundScheduler
from main import run as run_scraper, send_whatsapp_report

app = Flask(__name__)

# Track status
status_info = {
    "last_run": None,
    "last_status": "Ready",
    "is_running": False,
    "run_count": 0
}

scheduler = BackgroundScheduler()

def execute_job():
    if status_info["is_running"]:
        print("Scraper is already running. Skipping duplicate trigger.")
        return

    status_info["is_running"] = True
    status_info["last_status"] = "Running..."
    print(f"[{datetime.now()}] Starting rebate scraper execution...")

    try:
        run_scraper()
        status_info["last_status"] = "Success"
        status_info["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status_info["run_count"] += 1
    except Exception as e:
        status_info["last_status"] = f"Failed: {str(e)}"
        print(f"Error during scraper execution: {e}")
    finally:
        status_info["is_running"] = False

# Schedule 6-hour cron
scheduler.add_job(execute_job, 'interval', hours=6, id='rebate_scraper_6h', replace_existing=True)
scheduler.start()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/status")
def get_status():
    job = scheduler.get_job('rebate_scraper_6h')
    next_run = job.next_run_time if job else None
    return jsonify({
        "service": "Winbox/SH Rebate Scraper Web Service",
        "status": "Online",
        "scraper_info": status_info,
        "next_scheduled_run": next_run.strftime("%Y-%m-%d %H:%M:%S") if next_run else None
    })

@app.route("/api/data")
def get_data():
    file_path = "commission_list.json"
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return jsonify(data)
    return jsonify([])

@app.route("/api/trigger", methods=["GET", "POST"])
def manual_trigger():
    if status_info["is_running"]:
        return jsonify({"status": "error", "message": "Scraper is already running!"}), 400

    thread = threading.Thread(target=execute_job)
    thread.start()

    return jsonify({
        "status": "success",
        "message": "Scraping job started in background!"
    })

@app.route("/api/send-whatsapp", methods=["GET", "POST"])
def manual_whatsapp():
    file_path = "commission_list.json"
    if not os.path.exists(file_path):
        return jsonify({"status": "error", "message": "No scraped data found yet!"}), 404
        
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    whatsapp_target = os.environ.get("WHATSAPP_TARGET", "120363426571241502@g.us")
    success = send_whatsapp_report(data, whatsapp_target)
    
    if success:
        return jsonify({"status": "success", "message": "WhatsApp report sent successfully!"})
    else:
        return jsonify({"status": "error", "message": "Failed to send WhatsApp report."}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
