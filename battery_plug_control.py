# -*- coding: utf-8 -*-
"""
Battery-controlled smart plug for Xiaomi DianXiaoKu Max 2500W.
Turns plug ON when battery <= LOW_BATTERY%, OFF when >= HIGH_BATTERY%.
Only notifies on state changes (start/stop charging).

Sensitive config via environment variables:
  XIAOMI_DEVICE_ID   - Mi device ID
  XIAOMI_OWNER_ID    - Mi account user ID
  XIAOMI_SSECURITY   - Mi cloud ssecurity token
  XIAOMI_SERVICE_TOKEN - Mi cloud service token
  WIFI_SSID          - Required WiFi SSID to run
  FEISHU_OPEN_ID      - (optional) Feishu open_id for notifications
"""
import sys, os, io, json, time, subprocess, psutil

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# === Config from env ===
def env(key, required=True, default=None):
    val = os.environ.get(key, default)
    if required and not val:
        print(f"ERROR: Missing required env var: {key}")
        sys.exit(1)
    return val

DEVICE_ID     = env("XIAOMI_DEVICE_ID")
OWNER_ID      = env("XIAOMI_OWNER_ID")
SSECURITY     = env("XIAOMI_SSECURITY")
SERVICE_TOKEN = env("XIAOMI_SERVICE_TOKEN")
REQUIRED_WIFI = env("WIFI_SSID", default="RWifi")
FEISHU_OPEN_ID = env("FEISHU_OPEN_ID", required=False, default="")
HIGH_BATTERY  = int(env("HIGH_BATTERY", default="90"))
LOW_BATTERY   = int(env("LOW_BATTERY", default="30"))
STATE_FILE    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plug_state.json")

# === Init connector ===
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "token_extractor", "token_extractor"))
from token_extractor import QrCodeXiaomiCloudConnector

connector = QrCodeXiaomiCloudConnector()
connector._ssecurity   = SSECURITY
connector._serviceToken = SERVICE_TOKEN
connector.userId       = OWNER_ID

# === Helpers ===
def call_api(path, data):
    url = connector.get_api_url("cn") + path
    params = {"data": json.dumps(data, separators=(",", ":"))}
    return connector.execute_api_call_encrypted(url, params)

def check_wifi():
    try:
        r = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, timeout=10,
            encoding="utf-8", errors="replace"
        )
        for line in r.stdout.splitlines():
            line = line.strip()
            if "SSID" in line and "BSSID" not in line:
                ssid = line.split(":", 1)[1].strip() if ":" in line else ""
                return ssid == REQUIRED_WIFI
    except Exception as e:
        print(f"WARNING: WiFi check failed: {e}")
    return False

def get_battery():
    try:
        b = psutil.sensors_battery()
        return b.percent if b else None
    except:
        return None

def get_plug():
    try:
        r = call_api("/miotspec/prop/get", {"params": [{"did": DEVICE_ID, "siid": 2, "piid": 1}]})
        if r.get("code") == 0 and r.get("result"):
            return bool(r["result"][0]["value"])
    except:
        pass
    return None

def set_plug(state):
    try:
        r = call_api("/miotspec/prop/set", {"params": [{"did": DEVICE_ID, "siid": 2, "piid": 1, "value": state}]})
        return r.get("code") == 0
    except:
        return False

def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# === Main ===
print("=" * 60)
print("Battery Smart Plug Controller")
print(f"ON <= {LOW_BATTERY}%  |  OFF >= {HIGH_BATTERY}%")
print("=" * 60)

# 1. WiFi
print("\n[1] Checking WiFi...")
if not check_wifi():
    print(f"   ABORT: Not on '{REQUIRED_WIFI}'.")
    sys.exit(1)
print(f"   OK: '{REQUIRED_WIFI}'")

# 2. Battery
print("\n[2] Reading battery...")
bat = get_battery()
if bat is None:
    print("   ABORT: Cannot read battery.")
    sys.exit(1)
print(f"   Battery: {bat}%")

# 3. Plug state
print("\n[3] Reading plug...")
plug = get_plug()
if plug is None:
    print("   ABORT: Cannot read plug.")
    sys.exit(1)
print(f"   Plug: {'ON' if plug else 'OFF'}")

# 4. Decision
print("\n[4] Decision...")
prev = load_state()
prev_plug = prev.get("plug_on")
action = None  # "start_charging" | "stop_charging" | None

if bat >= HIGH_BATTERY and plug:
    target = False
    if prev_plug is True or prev_plug is None:
        action = "stop_charging"
    print(f"   Battery {bat}% >= {HIGH_BATTERY}% -> Turn OFF")
elif bat <= LOW_BATTERY and not plug:
    target = True
    if prev_plug is False or prev_plug is None:
        action = "start_charging"
    print(f"   Battery {bat}% <= {LOW_BATTERY}% -> Turn ON")
else:
    target = plug
    if bat > LOW_BATTERY and bat < HIGH_BATTERY:
        print(f"   Battery {bat}% in range, no action")
    elif bat >= HIGH_BATTERY and not plug:
        print(f"   Battery {bat}% but plug already OFF")
    elif bat <= LOW_BATTERY and plug:
        print(f"   Battery {bat}% but plug already ON")

# 5. Act
if target != plug:
    print(f"\n[5] Turning {'ON' if target else 'OFF'}...")
    if set_plug(target):
        print("   SUCCESS")
    else:
        print("   FAILED")
        sys.exit(1)
else:
    print(f"\n[5] No change needed.")

# 6. Save state
final_plug = target if target != plug else plug
save_state({
    "plug_on": final_plug,
    "battery": bat,
    "last_check": time.strftime("%Y-%m-%d %H:%M:%S")
})

# 7. Output result
print(f"\n[RESULT]")
print(f"Battery: {bat}%")
print(f"Plug: {'ON' if final_plug else 'OFF'}")
if action == "start_charging":
    print(f"STATUS: START_CHARGING")
    print(f"MSG: Battery low ({bat}%), plug turned ON")
elif action == "stop_charging":
    print(f"STATUS: STOP_CHARGING")
    print(f"MSG: Battery full ({bat}%), plug turned OFF")
else:
    print(f"STATUS: NO_CHANGE")
    print(f"MSG: No action needed")

print("\nDone.")
