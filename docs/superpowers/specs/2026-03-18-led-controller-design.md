# ESP32 WS2812 LED Controller — Design Spec

**Date:** 2026-03-18
**Platform:** ESP32-WROOM-32, PlatformIO, Arduino framework
**Hardware:** 8x WS2812 LEDs on GPIO 13 (labeled D13 on the physical board)

---

## Overview

A web-connected LED controller running on an ESP32. Each of the 8 LEDs is individually controllable via color and brightness through a browser-based UI. State persists across reboots. WiFi credentials are stored in an editable config file on the ESP32 filesystem.

---

## Architecture

```
ESP32 (Arduino framework via PlatformIO)
│
├── FastLED → GPIO 13 (DATA_PIN = 13) → WS2812 strip (8 LEDs)
│
├── LittleFS (ESP32 filesystem)
│   ├── wifi.json     ← user edits to set WiFi credentials
│   └── state.json    ← auto-saved on every Send, restored on boot
│
└── ESPAsyncWebServer (port 80)
    ├── GET  /        → serves the web UI (HTML embedded as PROGMEM string in main.cpp)
    ├── GET  /state   → returns current LED state as JSON
    └── POST /state   → receives new LED state JSON, applies to strip, saves to filesystem
```

---

## Hardware

| Parameter | Value |
|-----------|-------|
| Board | ESP32-WROOM-32 (pins labeled Dnn; D13 = GPIO 13) |
| DATA_PIN | 13 (integer, used in FastLED `#define DATA_PIN 13`) |
| LED strip | WS2812, 8 LEDs |
| Framework | Arduino (via PlatformIO) |

---

## File Structure

```
LED Control/
├── platformio.ini
├── src/
│   └── main.cpp          ← firmware + HTML/CSS/JS as PROGMEM string
└── data/
    └── wifi.json         ← uploaded to LittleFS via "Upload Filesystem Image"
```

Note: the web UI HTML is embedded in `main.cpp` as a PROGMEM string, not served from LittleFS. The `data/` directory contains only `wifi.json`. `state.json` is not uploaded — it is created and updated at runtime by the firmware each time a successful POST `/state` is processed.

---

## Data Formats

### `data/wifi.json`
Uploaded once to the ESP32 filesystem via PlatformIO's "Upload Filesystem Image" task. Edit this file to change WiFi credentials.

```json
{
  "ssid": "YourNetworkName",
  "password": "YourPassword"
}
```

### LED State (GET `/state` response body, POST `/state` request body, and `state.json` on filesystem)

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

- `r`, `g`, `b`: 0–255, **raw unscaled color values** — stored and transmitted as-is
- `brightness`: 0–255 — applied via `leds[i].nscale8(brightness)` at LED write time only, never pre-baked into r/g/b

---

## API Endpoints

| Method | Path | Request | Response |
|--------|------|---------|----------|
| GET | `/` | — | `200 text/html` — web UI page |
| GET | `/state` | — | `200 application/json` — current LED state JSON |
| POST | `/state` | LED state JSON body | `200 application/json` — `{"ok": true}` on success; `400` on malformed JSON |

---

## Web UI

Dark-themed single-page app. HTML/CSS/JS embedded as a PROGMEM `const char[]` string in `main.cpp`.

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
- Disabled and shows "Sending…" while a POST is in flight, preventing concurrent requests
- Re-enabled on response (success or error)
- On success: brief "Saved" confirmation text
- On error: brief "Error" text

**Client-side only updates:**
Color picker and brightness slider update the strip visualization and border color in real time with no server round-trip. The server is only contacted on Send.

---

## Firmware Boot Sequence

1. Mount LittleFS — if mount fails, print error to Serial and halt
2. Read `wifi.json` — if missing or malformed, print error to Serial and halt
3. Connect to WiFi with 10-second timeout
   - On success: print IP address to Serial
   - On failure (timeout/wrong credentials): print error to Serial; set all LEDs to dim red as visual indicator; do **not** start web server; halt in loop (LEDs stay red)
4. Read `state.json` if it exists → restore LED state and apply to strip
5. If `state.json` doesn't exist → all LEDs off
6. Start ESPAsyncWebServer, register routes
7. Enter main loop (no polling needed — async server handles requests via callbacks)

---

## Dependencies (`platformio.ini`)

```ini
[env:esp32dev]
platform = espressif32
board = esp32dev
framework = arduino
board_build.filesystem = littlefs
board_build.partitions = min_spiffs.csv
lib_deps =
    fastled/FastLED
    me-no-dev/ESPAsyncWebServer
    me-no-dev/AsyncTCP
    bblanchon/ArduinoJson
```

`min_spiffs.csv` allocates ~1.5MB for the filesystem, which is sufficient for `wifi.json` and `state.json`.

---

## Out of Scope

- OTA firmware updates
- Multiple strip support
- Authentication / access control
- Animations or preset patterns
- AP/captive portal fallback for WiFi setup
