import subprocess
import time
import sys

import requests
import uvicorn

from config import TELEGRAM_BOT_TOKEN  # loads .env


PORT = 8000
NGROK_API = "http://127.0.0.1:4040/api/tunnels"

print("=== run_with_ngrok.py: script started ===")


# ---------- start ngrok and get public URL ----------
try:
    print("[runner] Launching ngrok...")
    ngrok_proc = subprocess.Popen(
        ["ngrok", "http", str(PORT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    print(f"[runner] ngrok PID: {ngrok_proc.pid}")
except FileNotFoundError:
    print("[runner] ERROR: 'ngrok' command not found. Is it installed and in PATH?")
    sys.exit(1)

public_url = None
for attempt in range(15):
    try:
        print(f"[runner] Polling ngrok API (attempt {attempt + 1})...")
        resp = requests.get(NGROK_API, timeout=3)
        print(f"[runner] 4040 status: {resp.status_code}")
        data = resp.json()
        tunnels = data.get("tunnels", [])
        print(f"[runner] tunnels: {tunnels}")
        for t in tunnels:
            if t.get("proto") == "https":
                public_url = t["public_url"]
                break
        if public_url:
            break
    except Exception as e:
        print(f"[runner] ngrok API not ready yet: {e}")
    time.sleep(1)

if not public_url:
    print("[runner] ERROR: No https tunnel found from ngrok; exiting.")
    ngrok_proc.terminate()
    sys.exit(1)

print(f"[runner] ngrok public URL: {public_url}")


# ---------- set Telegram webhook + print getWebhookInfo ----------
if TELEGRAM_BOT_TOKEN:
    webhook_url = f"{public_url}/webhooks/telegram"
    base_api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

    # setWebhook
    set_url = f"{base_api}/setWebhook"
    print(f"[telegram] Setting webhook to: {webhook_url}")
    try:
        r = requests.post(set_url, data={"url": webhook_url}, timeout=10)
        print(f"[telegram] setWebhook status: {r.status_code}")
        print(f"[telegram] setWebhook response: {r.text}")
    except Exception as e:
        print(f"[telegram] ERROR setting webhook: {e}")

    # getWebhookInfo (Python version of your curl command)
    info_url = f"{base_api}/getWebhookInfo"
    try:
        info_resp = requests.get(info_url, timeout=10)
        print(f"[telegram] getWebhookInfo status: {info_resp.status_code}")
        print(f"[telegram] getWebhookInfo JSON: {info_resp.json()}")
    except Exception as e:
        print(f"[telegram] ERROR getWebhookInfo: {e}")
else:
    print("[telegram] TELEGRAM_BOT_TOKEN not set; skipping webhook setup.")


# ---------- start uvicorn ----------
print("[uvicorn] Starting FastAPI app on 0.0.0.0:8000 ...")
try:
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=False)
except KeyboardInterrupt:
    print("\n[runner] KeyboardInterrupt, shutting down...")
finally:
    try:
        ngrok_proc.terminate()
    except Exception:
        pass
