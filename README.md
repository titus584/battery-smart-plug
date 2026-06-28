# Battery Smart Plug Controller

Battery-controlled smart plug for Xiaomi DianXiaoKu Max 2500W.

## Logic

- **Battery <= 30%** → Plug ON (start charging)
- **Battery >= 90%** → Plug OFF (stop charging)
- Only notifies on state changes (start/stop charging)
- Only runs when connected to specified WiFi network

## Setup

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Fill in your values in `.env`:
   ```
   XIAOMI_DEVICE_ID=your_device_id
   XIAOMI_OWNER_ID=your_user_id
   XIAOMI_SSECURITY=your_ssecurity_token
   XIAOMI_SERVICE_TOKEN=your_service_token
   WIFI_SSID=YourWiFiName
   FEISHU_OPEN_ID=your_feishu_open_id
   ```

3. Install dependencies:
   ```bash
   pip install psutil pycryptodome
   pip install -r token_extractor/token_extractor/requirements.txt
   ```

4. Run:
   ```bash
   python battery_plug_control.py
   ```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| XIAOMI_DEVICE_ID | Yes | - | Mi device ID |
| XIAOMI_OWNER_ID | Yes | - | Mi account user ID |
| XIAOMI_SSECURITY | Yes | - | Mi cloud ssecurity token |
| XIAOMI_SERVICE_TOKEN | Yes | - | Mi cloud service token |
| WIFI_SSID | No | RWifi | Required WiFi SSID |
| FEISHU_OPEN_ID | No | - | Feishu open_id for notifications |
| HIGH_BATTERY | No | 90 | Battery % to turn plug OFF |
| LOW_BATTERY | No | 30 | Battery % to turn plug ON |

## Files

- `battery_plug_control.py` — Main control script
- `token_extractor/` — Mi cloud API connector library
- `.env.example` — Config template (copy to `.env`)
- `plug_state.json` — Runtime state tracking (gitignored)
