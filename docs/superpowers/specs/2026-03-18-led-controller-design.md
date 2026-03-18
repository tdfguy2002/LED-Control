# ESP32 WS2812 LED Controller — Design Spec

**Date:** 2026-03-18
**Platform:** ESP32-WROOM-32, MicroPython
**Hardware:** 8x WS2812 LEDs on GPIO 13 (labeled D13 on the physical board)

---

## Overview

A web-connected LED controller running MicroPython on an ESP32. Each of the 8 LEDs is individually controllable via color and brightness through a browser-based UI. State persists across reboots. WiFi credentials are stored in an editable config file on the ESP32 filesystem.

---

## Architecture

```
ESP32 (MicroPython firmware)
│
├── neopixel module → GPIO 13 → WS2812 strip (8 LEDs)
│
├── Filesystem (MicroPython built-in)
│   ├── wifi.json     ← user edits to set WiFi credentials
│   └── state.json    ← auto-saved on every Send, created at runtime
│
└── microdot web server (port 80)
    ├── GET  /        → serves the web UI (HTML embedded in main.py)
    ├── GET  /state   → returns current LED state as JSON
    └── POST /state   → receives new LED state JSON, applies to strip, saves to filesystem
```

---

## Hardware

| Parameter | Value |
|-----------|-------|
| Board | ESP32-WROOM-32 (pins labeled Dnn; D13 = GPIO 13) |
| Data pin | GPIO 13 (integer) |
| LED strip | WS2812, 8 LEDs |
| Runtime | MicroPython |

---

## File Structure

```
LED Control/           ← project directory (files uploaded to ESP32 root)
├── main.py            ← all logic: WiFi, web server, LED control, HTML
├── wifi.json          ← WiFi credentials (uploaded once, edit to change)
└── (state.json)       ← created at runtime on first POST /state
```

All files live at the root of the ESP32 filesystem. `main.py` runs automatically on boot.

---

## Upload Workflow

```bash
# Install mpremote (once)
pip install mpremote

# Upload files to ESP32
mpremote cp main.py :main.py
mpremote cp wifi.json :wifi.json

# Monitor serial output
mpremote
```

---

## Data Formats

### `wifi.json`
Edit locally, upload to ESP32 root via `mpremote cp wifi.json :wifi.json`.

```json
{
  "ssid": "YourNetworkName",
  "password": "YourPassword"
}
```

### LED State (GET `/state` response, POST `/state` request body, `state.json` on filesystem)

```json
{
  "leds": [
    {"r": 255, "g": 0,   "b": 0,   "brightness": 200},
    {"r": 0,   "g": 128, "b": 255, "brightness": 128},
    {"r": 0,   "g": 200, "b": 80,  "brightness": 230},
    {"r": 240, "g": 200, "b": 0,   "brightness": 102},
    {"r": 155, "g": 89,  "b": 182, "brightness": 153},
    {"r": 230, "g": 126, "b": 34,  "brightness": 217},
    {"r": 26,  "g": 188, "b": 156, "brightness": 64},
    {"r": 0,   "g": 0,   "b": 0,   "brightness": 0}
  ]
}
```

- `r`, `g`, `b`: 0–255, **raw unscaled color values**
- `brightness`: 0–255 — applied by scaling r/g/b at write time: `val = int(channel * brightness / 255)`
- `state.json` is not uploaded — it is created and updated at runtime by `main.py` on every successful POST `/state`

---

## API Endpoints

| Method | Path | Request | Response |
|--------|------|---------|----------|
| GET | `/` | — | `200 text/html` — web UI page |
| GET | `/state` | — | `200 application/json` — current LED state JSON |
| POST | `/state` | LED state JSON body | `200 application/json` — `{"ok": true}` on success; `400` on malformed JSON |

---

## Web UI

Dark-themed single-page app. HTML/CSS/JS embedded as a string constant in `main.py`, served from memory.

**Layout (Strip View):**
- Header: "LED CONTROLLER" title
- Live strip visualization: 8 colored LED blocks at top, updated client-side as controls change
- 8 control rows, each containing:
  - LED label ("LED 1" … "LED 8")
  - Native color picker (`<input type="color">`)
  - Brightness slider (`<input type="range" min="0" max="255">`)
  - Numeric brightness value display
  - Left border color matches the LED color (updated client-side on change)
- SEND button: POSTs all 8 LEDs' current values to `/state`
- On page load: fetches `GET /state` and populates all controls

**Send button behavior:**
- Disabled and shows "Sending…" while a POST is in flight
- Re-enabled on response; shows "Saved" or "Error"
- Status text clears after 3 seconds

---

## Firmware Boot Sequence (`main.py`)

1. Import modules: `network`, `neopixel`, `machine`, `json`, `uasyncio`, `microdot`
2. Initialize NeoPixel strip on GPIO 13, 8 LEDs
3. Read `wifi.json` — if missing or malformed: print error to REPL and halt
4. Connect to WiFi with 10-second timeout
   - On success: print IP address to REPL
   - On failure: set all LEDs to dim red (10, 0, 0); halt in infinite loop
5. Read `state.json` if it exists → restore LED state and apply to strip
6. If `state.json` missing → all LEDs off
7. Start microdot web server on port 80
8. Run uasyncio event loop

---

## Dependencies

- `neopixel` — built into MicroPython, no install needed
- `network` — built into MicroPython ESP32 firmware
- `json` — built into MicroPython
- `uasyncio` — built into MicroPython
- `microdot` — install once on the device:
  ```bash
  mpremote mip install microdot
  ```

---

## Prerequisites (One-Time Setup)

1. Flash MicroPython firmware to ESP32:
   - Download from https://micropython.org/download/ESP32_GENERIC/
   - Flash: `esptool.py --chip esp32 --port <PORT> erase_flash && esptool.py --chip esp32 --port <PORT> write_flash -z 0x1000 ESP32_GENERIC-xxx.bin`
2. Install mpremote: `pip install mpremote`
3. Install microdot on device: `mpremote mip install microdot`

---

## Out of Scope

- OTA firmware updates
- Multiple strip support
- Authentication / access control
- Animations or preset patterns
- AP/captive portal fallback for WiFi setup
