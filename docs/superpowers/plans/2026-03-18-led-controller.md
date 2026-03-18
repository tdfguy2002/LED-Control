# ESP32 WS2812 LED Controller Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a web-controlled WS2812 LED strip controller on an ESP32-WROOM-32 with per-LED color and brightness control, state persistence, and a browser UI.

**Architecture:** ESP32 serves a single-page web UI via ESPAsyncWebServer. The UI POSTs JSON LED state to the ESP32, which applies it via FastLED and persists it to LittleFS. WiFi credentials are read from `wifi.json` on LittleFS at boot.

**Tech Stack:** PlatformIO, Arduino framework, FastLED, ESPAsyncWebServer, AsyncTCP, ArduinoJson, LittleFS

---

## File Map

| File | Purpose |
|------|---------|
| `platformio.ini` | PlatformIO project config, dependencies, partition scheme |
| `src/main.cpp` | All firmware: WiFi init, LED control, web server, state persistence, HTML as PROGMEM |
| `data/wifi.json` | WiFi credentials — uploaded to LittleFS once |

---

## Task 1: Project Scaffold

**Files:**
- Create: `platformio.ini`
- Create: `src/main.cpp`
- Create: `data/wifi.json`

- [ ] **Step 1: Create `platformio.ini`**

```ini
[env:esp32dev]
platform = espressif32
board = esp32dev
framework = arduino
board_build.filesystem = littlefs
board_build.partitions = min_spiffs.csv
monitor_speed = 115200
lib_deps =
    fastled/FastLED
    me-no-dev/ESPAsyncWebServer
    me-no-dev/AsyncTCP
    bblanchon/ArduinoJson
```

- [ ] **Step 2: Create `src/main.cpp` with empty Arduino sketch**

```cpp
#include <Arduino.h>

void setup() {
  Serial.begin(115200);
  Serial.println("Boot");
}

void loop() {}
```

- [ ] **Step 3: Create `data/wifi.json` with placeholder credentials**

```json
{
  "ssid": "YourNetworkName",
  "password": "YourPassword"
}
```

- [ ] **Step 4: Build to verify dependencies resolve**

In PlatformIO terminal:
```
pio run
```
Expected: `SUCCESS` — no compile errors. Libraries download automatically.

- [ ] **Step 5: Commit**

```bash
git add platformio.ini src/main.cpp data/wifi.json
git commit -m "feat: project scaffold with PlatformIO config and empty sketch"
```

---

## Task 2: FastLED — LED State Struct and Strip Apply

**Files:**
- Modify: `src/main.cpp`

This task wires up FastLED and defines the in-memory LED state. No WiFi or web server yet.

- [ ] **Step 1: Add FastLED setup to `main.cpp`**

Replace the empty sketch with:

```cpp
#include <Arduino.h>
#include <FastLED.h>

#define DATA_PIN    13
#define NUM_LEDS    8
#define LED_TYPE    WS2812
#define COLOR_ORDER GRB

// In-memory LED state
struct LedState {
  uint8_t r, g, b, brightness;
};

LedState ledStates[NUM_LEDS];
CRGB leds[NUM_LEDS];

// Apply in-memory state to the physical strip
void applyLeds() {
  for (int i = 0; i < NUM_LEDS; i++) {
    leds[i] = CRGB(ledStates[i].r, ledStates[i].g, ledStates[i].b);
    leds[i].nscale8(ledStates[i].brightness);
  }
  FastLED.show();
}

void setup() {
  Serial.begin(115200);

  // Initialize all LEDs off
  for (int i = 0; i < NUM_LEDS; i++) {
    ledStates[i] = {0, 0, 0, 0};
  }

  FastLED.addLeds<LED_TYPE, DATA_PIN, COLOR_ORDER>(leds, NUM_LEDS);
  FastLED.setBrightness(255);  // Global brightness max; per-LED brightness via nscale8
  applyLeds();

  Serial.println("FastLED ready");
}

void loop() {}
```

- [ ] **Step 2: Build to verify FastLED compiles**

```
pio run
```
Expected: `SUCCESS`

- [ ] **Step 3: Upload and verify LEDs are off at boot**

```
pio run --target upload
pio device monitor
```
Expected Serial output: `Boot` then `FastLED ready`. LEDs should all be off.

- [ ] **Step 4: Commit**

```bash
git add src/main.cpp
git commit -m "feat: FastLED setup with per-LED state struct and applyLeds()"
```

---

## Task 3: LittleFS — WiFi Config and State Persistence

**Files:**
- Modify: `src/main.cpp`

Add LittleFS mounting, wifi.json reading, and state.json read/write.

- [ ] **Step 1: Add LittleFS + ArduinoJson includes and helper functions**

Add to the top of `main.cpp` after existing includes:

```cpp
#include <LittleFS.h>
#include <ArduinoJson.h>
```

Add these functions before `setup()`:

```cpp
// Read wifi.json and populate ssid/password. Returns false on failure.
bool loadWifiConfig(String &ssid, String &password) {
  File f = LittleFS.open("/wifi.json", "r");
  if (!f) return false;
  JsonDocument doc;
  if (deserializeJson(doc, f) != DeserializationError::Ok) { f.close(); return false; }
  f.close();
  ssid = doc["ssid"].as<String>();
  password = doc["password"].as<String>();
  return ssid.length() > 0;
}

// Save current ledStates[] to /state.json
void saveState() {
  File f = LittleFS.open("/state.json", "w");
  if (!f) return;
  JsonDocument doc;
  JsonArray arr = doc["leds"].to<JsonArray>();
  for (int i = 0; i < NUM_LEDS; i++) {
    JsonObject led = arr.add<JsonObject>();
    led["r"] = ledStates[i].r;
    led["g"] = ledStates[i].g;
    led["b"] = ledStates[i].b;
    led["brightness"] = ledStates[i].brightness;
  }
  serializeJson(doc, f);
  f.close();
}

// Load /state.json into ledStates[]. Returns false if file missing or invalid.
bool loadState() {
  File f = LittleFS.open("/state.json", "r");
  if (!f) return false;
  JsonDocument doc;
  if (deserializeJson(doc, f) != DeserializationError::Ok) { f.close(); return false; }
  f.close();
  JsonArray arr = doc["leds"].as<JsonArray>();
  if (arr.size() != NUM_LEDS) return false;
  for (int i = 0; i < NUM_LEDS; i++) {
    ledStates[i].r          = arr[i]["r"];
    ledStates[i].g          = arr[i]["g"];
    ledStates[i].b          = arr[i]["b"];
    ledStates[i].brightness = arr[i]["brightness"];
  }
  return true;
}
```

- [ ] **Step 2: Update `setup()` to mount LittleFS and load state**

Replace the `setup()` body:

```cpp
void setup() {
  Serial.begin(115200);

  // Mount filesystem
  if (!LittleFS.begin()) {
    Serial.println("ERROR: LittleFS mount failed");
    while (true) delay(1000);
  }
  Serial.println("LittleFS mounted");

  // Initialize FastLED
  FastLED.addLeds<LED_TYPE, DATA_PIN, COLOR_ORDER>(leds, NUM_LEDS);
  FastLED.setBrightness(255);

  // Restore saved state or start with all LEDs off
  if (loadState()) {
    Serial.println("State restored from state.json");
  } else {
    Serial.println("No state.json — all LEDs off");
    for (int i = 0; i < NUM_LEDS; i++) ledStates[i] = {0, 0, 0, 0};
  }
  applyLeds();
}
```

- [ ] **Step 3: Build to verify it compiles**

```
pio run
```
Expected: `SUCCESS`

- [ ] **Step 4: Upload filesystem image (wifi.json)**

```
pio run --target uploadfs
```
Expected: `SUCCESS` — uploads `data/wifi.json` to LittleFS.

- [ ] **Step 5: Upload firmware and verify Serial output**

```
pio run --target upload && pio device monitor
```
Expected:
```
LittleFS mounted
No state.json — all LEDs off
```

- [ ] **Step 6: Commit**

```bash
git add src/main.cpp
git commit -m "feat: LittleFS mount, wifi config reader, state save/load"
```

---

## Task 4: WiFi Connection

**Files:**
- Modify: `src/main.cpp`

Add WiFi connection with 10-second timeout. On failure: dim red LEDs + halt.

- [ ] **Step 1: Add WiFi includes**

Add after existing includes:

```cpp
#include <WiFi.h>
```

- [ ] **Step 2: Add `connectWifi()` function before `setup()`**

```cpp
// Connect to WiFi using credentials from wifi.json.
// On failure: sets all LEDs to dim red and halts.
void connectWifi() {
  String ssid, password;
  if (!loadWifiConfig(ssid, password)) {
    Serial.println("ERROR: wifi.json missing or malformed");
    // Dim red error indicator
    for (int i = 0; i < NUM_LEDS; i++) {
      leds[i] = CRGB(40, 0, 0);
    }
    FastLED.show();
    while (true) delay(1000);
  }

  Serial.printf("Connecting to %s", ssid.c_str());
  WiFi.begin(ssid.c_str(), password.c_str());

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 10000) {
    delay(500);
    Serial.print(".");
  }

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\nERROR: WiFi connection failed");
    for (int i = 0; i < NUM_LEDS; i++) {
      leds[i] = CRGB(40, 0, 0);
    }
    FastLED.show();
    while (true) delay(1000);
  }

  Serial.printf("\nWiFi connected. IP: %s\n", WiFi.localIP().toString().c_str());
}
```

- [ ] **Step 3: Call `connectWifi()` from `setup()` after LittleFS mount and FastLED init**

In `setup()`, after `FastLED.setBrightness(255);` and before the `loadState()` call:

```cpp
  connectWifi();
```

- [ ] **Step 4: Build, upload, verify WiFi connection**

Edit `data/wifi.json` with your real network credentials, then:
```
pio run --target uploadfs
pio run --target upload && pio device monitor
```
Expected Serial output:
```
LittleFS mounted
Connecting to YourNetworkName.....
WiFi connected. IP: 192.168.x.x
No state.json — all LEDs off
```

- [ ] **Step 5: Commit**

```bash
git add src/main.cpp
git commit -m "feat: WiFi connection with 10s timeout and red LED failure indicator"
```

---

## Task 5: Web Server — API Endpoints

**Files:**
- Modify: `src/main.cpp`

Add ESPAsyncWebServer with `GET /state` and `POST /state`. No web UI HTML yet.

- [ ] **Step 1: Add web server includes**

```cpp
#include <ESPAsyncWebServer.h>
```

Add before `setup()`:

```cpp
AsyncWebServer server(80);
```

- [ ] **Step 2: Add `setupRoutes()` function before `setup()`**

```cpp
void setupRoutes() {
  // GET /state — return current LED state as JSON
  server.on("/state", HTTP_GET, [](AsyncWebServerRequest *request) {
    JsonDocument doc;
    JsonArray arr = doc["leds"].to<JsonArray>();
    for (int i = 0; i < NUM_LEDS; i++) {
      JsonObject led = arr.add<JsonObject>();
      led["r"] = ledStates[i].r;
      led["g"] = ledStates[i].g;
      led["b"] = ledStates[i].b;
      led["brightness"] = ledStates[i].brightness;
    }
    String body;
    serializeJson(doc, body);
    request->send(200, "application/json", body);
  });

  // POST /state — apply new LED state and save
  server.on("/state", HTTP_POST,
    [](AsyncWebServerRequest *request) {},
    nullptr,
    [](AsyncWebServerRequest *request, uint8_t *data, size_t len, size_t index, size_t total) {
      JsonDocument doc;
      if (deserializeJson(doc, data, len) != DeserializationError::Ok) {
        request->send(400, "application/json", "{\"error\":\"invalid json\"}");
        return;
      }
      JsonArray arr = doc["leds"].as<JsonArray>();
      if (arr.size() != NUM_LEDS) {
        request->send(400, "application/json", "{\"error\":\"expected 8 leds\"}");
        return;
      }
      for (int i = 0; i < NUM_LEDS; i++) {
        ledStates[i].r          = arr[i]["r"];
        ledStates[i].g          = arr[i]["g"];
        ledStates[i].b          = arr[i]["b"];
        ledStates[i].brightness = arr[i]["brightness"];
      }
      applyLeds();
      saveState();
      request->send(200, "application/json", "{\"ok\":true}");
    }
  );
}
```

- [ ] **Step 3: Call `setupRoutes()` and start server in `setup()`**

At the end of `setup()`, after `applyLeds()`:

```cpp
  setupRoutes();
  server.begin();
  Serial.println("Web server started");
```

- [ ] **Step 4: Build and upload**

```
pio run --target upload && pio device monitor
```
Expected Serial output includes: `Web server started`

- [ ] **Step 5: Test `GET /state` with curl**

```bash
curl http://<ESP32-IP>/state
```
Expected: JSON with 8 LEDs all zeros, e.g.:
```json
{"leds":[{"r":0,"g":0,"b":0,"brightness":0}, ...]}
```

- [ ] **Step 6: Test `POST /state` with curl**

```bash
curl -X POST http://<ESP32-IP>/state \
  -H "Content-Type: application/json" \
  -d '{"leds":[{"r":255,"g":0,"b":0,"brightness":200},{"r":0,"g":0,"b":255,"brightness":128},{"r":0,"g":255,"b":0,"brightness":200},{"r":255,"g":255,"b":0,"brightness":150},{"r":0,"g":255,"b":255,"brightness":150},{"r":255,"g":0,"b":255,"brightness":150},{"r":255,"g":128,"b":0,"brightness":200},{"r":128,"g":0,"b":255,"brightness":200}]}'
```
Expected: `{"ok":true}` and LEDs light up with the specified colors.

- [ ] **Step 7: Verify state persists across reboot**

Power-cycle the ESP32. LEDs should restore to the colors set in step 6.

- [ ] **Step 8: Commit**

```bash
git add src/main.cpp
git commit -m "feat: web server with GET /state and POST /state endpoints"
```

---

## Task 6: Web UI HTML

**Files:**
- Modify: `src/main.cpp`

Add the HTML/CSS/JS as a PROGMEM string and serve it on `GET /`.

- [ ] **Step 1: Add the PROGMEM HTML constant before `setupRoutes()`**

```cpp
const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LED Controller</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #111; color: #ccc; font-family: monospace; padding: 20px; }
  h1 { text-align: center; letter-spacing: 3px; color: #eee; margin-bottom: 20px; font-size: 16px; }
  #strip {
    display: flex; gap: 8px; justify-content: center;
    padding: 16px; background: #1a1a1a; border-radius: 8px; margin-bottom: 20px;
  }
  .led-block {
    width: 40px; height: 44px; border-radius: 4px;
    display: flex; align-items: center; justify-content: center;
    font-size: 10px; color: rgba(255,255,255,0.7); font-weight: bold;
    background: #333; transition: background 0.2s, box-shadow 0.2s;
  }
  #controls { display: flex; flex-direction: column; gap: 8px; max-width: 500px; margin: 0 auto; }
  .row {
    display: flex; align-items: center; gap: 10px;
    background: #1a1a1a; padding: 8px 12px; border-radius: 6px;
    border-left: 3px solid #444;
  }
  .row label { color: #888; font-size: 12px; width: 38px; flex-shrink: 0; }
  .row input[type=color] { width: 32px; height: 28px; border: none; background: none; cursor: pointer; border-radius: 3px; flex-shrink: 0; }
  .row input[type=range] { flex: 1; accent-color: #27ae60; }
  .row .bval { color: #aaa; font-size: 11px; width: 28px; text-align: right; flex-shrink: 0; }
  #send-area { text-align: center; margin-top: 20px; }
  #send-btn {
    background: #27ae60; color: white; border: none;
    padding: 12px 48px; border-radius: 6px; font-size: 14px;
    cursor: pointer; letter-spacing: 1px; font-family: monospace;
  }
  #send-btn:disabled { background: #555; cursor: default; }
  #status { color: #555; font-size: 11px; margin-top: 6px; min-height: 16px; }
</style>
</head>
<body>
<h1>LED CONTROLLER</h1>
<div id="strip"></div>
<div id="controls"></div>
<div id="send-area">
  <button id="send-btn" onclick="sendState()">SEND</button>
  <div id="status"></div>
</div>
<script>
const N = 8;

function hexToRgb(hex) {
  const r = parseInt(hex.slice(1,3),16);
  const g = parseInt(hex.slice(3,5),16);
  const b = parseInt(hex.slice(5,7),16);
  return {r,g,b};
}
function rgbToHex(r,g,b) {
  return '#' + [r,g,b].map(v => v.toString(16).padStart(2,'0')).join('');
}
function brightness(r,g,b,bv) {
  const s = bv/255;
  return `rgb(${Math.round(r*s)},${Math.round(g*s)},${Math.round(b*s)})`;
}

// Build UI
const strip = document.getElementById('strip');
const controls = document.getElementById('controls');

for (let i = 0; i < N; i++) {
  const block = document.createElement('div');
  block.className = 'led-block';
  block.id = 'block'+i;
  block.textContent = i+1;
  strip.appendChild(block);

  const row = document.createElement('div');
  row.className = 'row';
  row.id = 'row'+i;
  row.innerHTML = `
    <label>LED ${i+1}</label>
    <input type="color" id="color${i}" value="#000000" oninput="update(${i})">
    <input type="range" id="bright${i}" min="0" max="255" value="0" oninput="update(${i})">
    <span class="bval" id="bval${i}">0</span>
  `;
  controls.appendChild(row);
}

function update(i) {
  const hex = document.getElementById('color'+i).value;
  const bv = parseInt(document.getElementById('bright'+i).value);
  document.getElementById('bval'+i).textContent = bv;
  const {r,g,b} = hexToRgb(hex);
  const col = brightness(r,g,b,bv);
  const block = document.getElementById('block'+i);
  block.style.background = col;
  block.style.boxShadow = bv > 0 ? `0 0 12px ${col}` : 'none';
  document.getElementById('row'+i).style.borderLeftColor = col;
}

async function loadState() {
  try {
    const res = await fetch('/state');
    const data = await res.json();
    data.leds.forEach((led, i) => {
      document.getElementById('color'+i).value = rgbToHex(led.r, led.g, led.b);
      document.getElementById('bright'+i).value = led.brightness;
      update(i);
    });
  } catch(e) { console.error('Failed to load state', e); }
}

async function sendState() {
  const btn = document.getElementById('send-btn');
  const status = document.getElementById('status');
  btn.disabled = true;
  btn.textContent = 'Sending...';
  status.textContent = '';

  const leds = [];
  for (let i = 0; i < N; i++) {
    const {r,g,b} = hexToRgb(document.getElementById('color'+i).value);
    const brightness = parseInt(document.getElementById('bright'+i).value);
    leds.push({r,g,b,brightness});
  }

  try {
    const res = await fetch('/state', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({leds})
    });
    if (res.ok) {
      status.textContent = 'Saved';
    } else {
      status.textContent = 'Error: ' + res.status;
    }
  } catch(e) {
    status.textContent = 'Error: ' + e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = 'SEND';
    setTimeout(() => { status.textContent = ''; }, 3000);
  }
}

loadState();
</script>
</body>
</html>
)rawliteral";
```

- [ ] **Step 2: Add `GET /` route inside `setupRoutes()`**

Add at the top of the `setupRoutes()` function body, before the `/state` routes:

```cpp
  server.on("/", HTTP_GET, [](AsyncWebServerRequest *request) {
    request->send_P(200, "text/html", INDEX_HTML);
  });
```

- [ ] **Step 3: Build and upload**

```
pio run --target upload && pio device monitor
```
Expected: no compile errors, `Web server started` in Serial output.

- [ ] **Step 4: Open browser and verify UI**

Open `http://<ESP32-IP>` in a browser.
Expected:
- Dark page with "LED CONTROLLER" header
- 8 dim LED blocks in a row
- 8 control rows with color pickers and brightness sliders
- Controls populated from the last saved state (or all zero if first boot)

- [ ] **Step 5: Test full flow**
  1. Set LED 1 to red, brightness 200
  2. Set LED 2 to blue, brightness 128
  3. Click SEND — button shows "Sending..." then "Saved"
  4. Verify physical LEDs change color
  5. Strip visualization at top should reflect the colors
  6. Power-cycle ESP32, reload page — LEDs and UI should restore previous state

- [ ] **Step 6: Commit**

```bash
git add src/main.cpp
git commit -m "feat: web UI with strip visualization, color pickers, brightness sliders"
```

---

## Done

All tasks complete. The controller is fully functional:
- Individual color and brightness control for each of 8 WS2812 LEDs
- Dark web UI served from ESP32, accessible at its IP address
- State persists across reboots via `state.json` on LittleFS
- WiFi credentials configured via `data/wifi.json`
