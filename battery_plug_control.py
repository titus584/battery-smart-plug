# -*- coding: utf-8 -*-
import sys, json, time, os, subprocess, psutil
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "token_extractor", "token_extractor"))
from Crypto.Cipher import ARC4
import base64
from token_extractor import QrCodeXiaomiCloudConnector

BASE = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE, ".env")
STATE_PATH = os.path.join(BASE, "plug_state.json")
SECRET_PATH = os.path.join(BASE, "feishu_bot_secret.json")

# Feishu notify (status change only)
def notify_feishu(text):
 try:
  if not os.path.exists(SECRET_PATH):
   L("Feishu: secret file missing, skip notify")
   return
  with open(SECRET_PATH, "r", encoding="utf-8") as f:
   s = json.load(f)
  import urllib.request, urllib.error
  req_body = json.dumps({"app_id": s["appId"], "app_secret": s["appSecret"]}).encode("utf-8")
  req = urllib.request.Request(
   "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
   data=req_body, headers={"Content-Type": "application/json"})
  with urllib.request.urlopen(req, timeout=15) as resp:
   tok = json.loads(resp.read().decode("utf-8")).get("tenant_access_token")
   if not tok:
    L("Feishu: get token failed")
    return
  msg_body = json.dumps({
   "receive_id": s.get("targetOpenId"),
   "msg_type": "text",
   "content": json.dumps({"text": text})
  }).encode("utf-8")
  req2 = urllib.request.Request(
   "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
   data=msg_body, headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
  with urllib.request.urlopen(req2, timeout=15) as resp2:
   rj = json.loads(resp2.read().decode("utf-8"))
   if rj.get("code") == 0:
    L("Feishu: notified OK")
   else:
    L("Feishu: send failed " + str(rj.get("code")) + " " + str(rj.get("msg")))
 except Exception as e:
  L("Feishu notify error: " + str(e))

# Load env
env = {}
with open(ENV_PATH, "r", encoding="utf-8") as f:
 for line in f:
  if "=" in line and not line.strip().startswith("#"):
   k, v = line.strip().split("=", 1)
   env[k] = v

# Connector
c = QrCodeXiaomiCloudConnector()
c._ssecurity = env.get("XIAOMI_SSECURITY")
c._serviceToken = env.get("XIAOMI_SERVICE_TOKEN")
c.userId = env.get("XIAOMI_OWNER_ID")
for d in [".sts.api.io.mi.com", ".api.io.mi.com"]:
 c._session.cookies.set("serviceToken", c._serviceToken, domain=d)
 c._session.cookies.set("yetAnotherServiceToken", c._serviceToken, domain=d)

# Log
LOG = os.path.join(BASE, "run_now.log")
log = open(LOG, "w", encoding="utf-8", buffering=1)
def L(msg):
 log.write(msg + "\n")
 log.flush()

try:
 L("=== Battery Plug Run ===")
 L(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
 # 1. WiFi
 r = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, timeout=10, encoding="utf-8", errors="replace")
 ssid = ""
 for line in r.stdout.splitlines():
  if "SSID" in line and "BSSID" not in line:
   ssid = line.split(":", 1)[1].strip() if ":" in line else ""
   break
 L(f"WiFi: {ssid}")
 expected_ssid = env.get("WIFI_SSID", "RWifi")
 if ssid != expected_ssid:
  L(f"WARNING: WiFi mismatch (got '{ssid}', expected '{expected_ssid}') -- continue anyway")
  # Do NOT abort; on a laptop the SSID can change (hotspot/reconnect)
 # 2. Battery
 bat = psutil.sensors_battery()
 battery = bat.percent if bat else None
 L(f"Battery: {battery}%")
 if battery is None:
  L("ABORT: Cannot read battery")
  sys.exit(1)
 # 3. Plug state
 url = c.get_api_url("cn") + "/miotspec/prop/get"
 payload = json.dumps({"params": [{"did": "482591436", "siid": 2, "piid": 1}]}, separators=(",", ":"))
 nonce = c.generate_nonce(round(time.time() * 1000))
 signed_nonce = c.signed_nonce(nonce)
 fields = c.generate_enc_params(url, "POST", signed_nonce, nonce, {"data": payload}, c._ssecurity)
 cookies = {
  "userId": str(c.userId),
  "yetAnotherServiceToken": c._serviceToken,
  "serviceToken": c._serviceToken,
  "locale": "en_GB",
  "timezone": "GMT+02:00",
  "is_daylight": "1",
  "dst_offset": "3600000",
  "channel": "MI_APP_STORE"
 }
 headers = {
  "Accept-Encoding": "identity",
  "User-Agent": c._agent,
  "Content-Type": "application/x-www-form-urlencoded",
  "x-xiaomi-protocal-flag-cli": "PROTOCAL-HTTP2",
  "MIOT-ENCRYPT-ALGORITHM": "ENCRYPT-RC4"
 }
 resp = c._session.post(url, headers=headers, cookies=cookies, params=fields)
 L(f"API STATUS: {resp.status_code}")
 if resp.status_code != 200:
  L("ABORT: API failed")
  sys.exit(1)
 r_arc = ARC4.new(base64.b64decode(signed_nonce))
 r_arc.encrypt(bytes(1024))
 decrypted = r_arc.encrypt(base64.b64decode(resp.text))
 body = json.loads(decrypted)
 L(f"API Code: {body.get('code')}")
 value = body.get("result", [{}])[0].get("value")
 plug = bool(value) if value is not None else None
 L(f"Plug state: {'ON' if plug else 'OFF'}")
 # 4. Decision
 action = None
 target = plug
 if battery >= 90 and plug:
  target = False
  action = "stop_charging"
  L(f"Decision: Battery {battery}% >= 90%, turn OFF")
 elif battery <= 30 and not plug:
  target = True
  action = "start_charging"
  L(f"Decision: Battery {battery}% <= 30%, turn ON")
 else:
  L("Decision: NO_CHANGE")
 # 5. Act
 if target != plug:
  L(f"Turning {'ON' if target else 'OFF'}...")
  url_set = c.get_api_url("cn") + "/miotspec/prop/set"
  payload_set = json.dumps({"params": [{"did": "482591436", "siid": 2, "piid": 1, "value": target}]}, separators=(",", ":"))
  nonce2 = c.generate_nonce(round(time.time() * 1000))
  signed_nonce2 = c.signed_nonce(nonce2)
  fields2 = c.generate_enc_params(url_set, "POST", signed_nonce2, nonce2, {"data": payload_set}, c._ssecurity)
  resp2 = c._session.post(url_set, headers=headers, cookies=cookies, params=fields2)
  L(f"Set STATUS: {resp2.status_code}")
  if resp2.status_code == 200:
   r2 = ARC4.new(base64.b64decode(signed_nonce2))
   r2.encrypt(bytes(1024))
   dec2 = r2.encrypt(base64.b64decode(resp2.text))
   body2 = json.loads(dec2)
   L(f"Set Code: {body2.get('code')}")
   if body2.get("code") == 0:
    plug = target
    L("SUCCESS")
   else:
    L("FAILED")
    sys.exit(1)
  else:
   L("FAILED")
   sys.exit(1)
 else:
  L("No action needed")
 # 6. Save state
 state = {"plug_on": plug, "battery": battery, "last_check": time.strftime("%Y-%m-%d %H:%M:%S")}
 with open(STATE_PATH, "w") as f:
  json.dump(state, f)
 L(f"State saved: {json.dumps(state)}")
 # 7. Output
 if action == "start_charging":
  L(f"STATUS: START_CHARGING")
  L(f"MSG: Battery low ({battery}%), plug turned ON")
  notify_feishu(f"🔌 电池 {battery}% 低于 30%，已开启充电插座")
 elif action == "stop_charging":
  L(f"STATUS: STOP_CHARGING")
  L(f"MSG: Battery full ({battery}%), plug turned OFF")
  notify_feishu(f"✅ 电池 {battery}% 已达 90%，已关闭充电插座")
 else:
  L(f"STATUS: NO_CHANGE")
  L("Done.")
except Exception as e:
 L(f"ERROR: {e}")
 import traceback
 L(traceback.format_exc())
 sys.exit(1)
finally:
 log.close()
