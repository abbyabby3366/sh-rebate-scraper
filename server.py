import os
import threading
from datetime import datetime
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from main import run as run_scraper

app = Flask(__name__)

# Track execution status
status_info = {
    "last_run": None,
    "last_status": "Not started",
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

# Schedule job to run automatically every 6 hours
scheduler.add_job(execute_job, 'interval', hours=6, id='rebate_scraper_6h', replace_existing=True)
scheduler.start()

@app.route("/")
def index():
    job = scheduler.get_job('rebate_scraper_6h')
    next_run = job.next_run_time if job else None
    return jsonify({
        "service": "Winbox/SH Rebate Scraper Web Service",
        "status": "Online",
        "scraper_info": status_info,
        "schedule": "Every 6 hours",
        "next_scheduled_run": next_run.strftime("%Y-%m-%d %H:%M:%S") if next_run else None
    })

@app.route("/trigger", methods=["GET", "POST"])
def manual_trigger():
    if status_info["is_running"]:
        return jsonify({"status": "error", "message": "Scraper is already running!"}), 400

    thread = threading.Thread(target=execute_job)
    thread.start()

    return jsonify({
        "status": "success",
        "message": "Manual scraping job triggered in background!"
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
