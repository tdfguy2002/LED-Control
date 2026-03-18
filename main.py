import gc
import network
import neopixel
import machine
import json
import time
import socket

# NOTE: const N in INDEX_HTML JavaScript must match NUM_LEDS — update both together
NUM_LEDS = 8
DATA_PIN = 13

# Initialize NeoPixel strip
np = neopixel.NeoPixel(machine.Pin(DATA_PIN), NUM_LEDS)

# In-memory LED state: list of dicts with r, g, b, brightness
led_states = [{"r": 0, "g": 0, "b": 0, "brightness": 0} for _ in range(NUM_LEDS)]


def apply_leds():
    """Apply led_states to the physical strip. Scales r/g/b by brightness."""
    for i, s in enumerate(led_states):
        bv = s["brightness"] / 255
        np[i] = (
            int(s["r"] * bv),
            int(s["g"] * bv),
            int(s["b"] * bv),
        )
    np.write()


def save_state():
    """Save led_states to state.json."""
    try:
        with open("state.json", "w") as f:
            json.dump({"leds": led_states}, f)
    except Exception as e:
        print("WARNING: could not save state:", e)


def load_state():
    """Load state.json into led_states. Returns True on success."""
    global led_states
    try:
        with open("state.json") as f:
            data = json.load(f)
        leds = data.get("leds", [])
        if len(leds) != NUM_LEDS:
            return False
        for led in leds:
            if not all(k in led for k in ("r", "g", "b", "brightness")):
                return False
            if not all(isinstance(led[k], int) for k in ("r", "g", "b", "brightness")):
                return False
        led_states = leds
        return True
    except Exception:
        return False


def load_wifi_config():
    """Read wifi.json. Returns (ssid, password) or raises on failure."""
    try:
        with open("wifi.json") as f:
            cfg = json.load(f)
        ssid = cfg.get("ssid", "")
        password = cfg.get("password", "")
        if not ssid:
            raise ValueError("ssid is empty")
        return ssid, password
    except Exception as e:
        raise RuntimeError("wifi.json missing or malformed: " + str(e))


def connect_wifi():
    """Connect to WiFi. On failure, sets all LEDs dim red and halts — never returns."""
    try:
        ssid, password = load_wifi_config()
    except RuntimeError as e:
        print("ERROR:", e)
        for i in range(NUM_LEDS):
            np[i] = (10, 0, 0)
        np.write()
        while True:
            time.sleep(1)

    print("Connecting to", ssid, end="")
    wlan = network.WLAN(network.STA_IF)
    try:
        wlan.active(False)
        time.sleep(0.5)
    except Exception:
        pass
    gc.collect()
    wlan.active(True)
    wlan.connect(ssid, password)

    start = time.ticks_ms()
    while not wlan.isconnected():
        if time.ticks_diff(time.ticks_ms(), start) > 10000:
            print("\nERROR: WiFi connection failed")
            for i in range(NUM_LEDS):
                np[i] = (10, 0, 0)
            np.write()
            while True:
                time.sleep(1)
        print(".", end="")
        time.sleep(0.5)

    ip = wlan.ifconfig()[0]
    print("\nWiFi connected. IP:", ip)
    return ip


INDEX_HTML = b"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LED Controller</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #111; color: #ccc; font-family: monospace; padding: 20px; }
  h1 { text-align: center; letter-spacing: 3px; color: #eee; margin-bottom: 20px; font-size: 16px; }
  #strip { display: flex; gap: 8px; justify-content: center; padding: 16px; background: #1a1a1a; border-radius: 8px; margin-bottom: 20px; }
  .led-block { width: 40px; height: 44px; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-size: 10px; color: rgba(255,255,255,0.7); font-weight: bold; background: #333; transition: background 0.2s, box-shadow 0.2s; }
  #controls { display: flex; flex-direction: column; gap: 8px; max-width: 500px; margin: 0 auto; }
  .row { display: flex; align-items: center; gap: 10px; background: #1a1a1a; padding: 8px 12px; border-radius: 6px; border-left: 3px solid #444; }
  .row label { color: #888; font-size: 12px; width: 38px; flex-shrink: 0; }
  .row input[type=color] { width: 32px; height: 28px; border: none; background: none; cursor: pointer; border-radius: 3px; flex-shrink: 0; }
  .row input[type=range] { flex: 1; accent-color: #27ae60; }
  .row .bval { color: #aaa; font-size: 11px; width: 28px; text-align: right; flex-shrink: 0; }
  #send-area { text-align: center; margin-top: 20px; }
  #send-btn { background: #27ae60; color: white; border: none; padding: 12px 48px; border-radius: 6px; font-size: 14px; cursor: pointer; letter-spacing: 1px; font-family: monospace; }
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
function hexToRgb(hex) { return { r: parseInt(hex.slice(1,3),16), g: parseInt(hex.slice(3,5),16), b: parseInt(hex.slice(5,7),16) }; }
function rgbToHex(r,g,b) { return '#' + [r,g,b].map(v => v.toString(16).padStart(2,'0')).join(''); }
function scaledColor(r,g,b,bv) { const s=bv/255; return `rgb(${Math.round(r*s)},${Math.round(g*s)},${Math.round(b*s)})`; }
const strip = document.getElementById('strip');
const controls = document.getElementById('controls');
for (let i = 0; i < N; i++) {
  const block = document.createElement('div');
  block.className='led-block'; block.id='block'+i; block.textContent=i+1; strip.appendChild(block);
  const row = document.createElement('div');
  row.className='row'; row.id='row'+i;
  row.innerHTML=`<label>LED ${i+1}</label><input type="color" id="color${i}" value="#000000" oninput="update(${i})"><input type="range" id="bright${i}" min="0" max="255" value="0" oninput="update(${i})"><span class="bval" id="bval${i}">0</span>`;
  controls.appendChild(row);
}
function update(i) {
  const hex=document.getElementById('color'+i).value;
  const bv=parseInt(document.getElementById('bright'+i).value);
  document.getElementById('bval'+i).textContent=bv;
  const {r,g,b}=hexToRgb(hex);
  const col=scaledColor(r,g,b,bv);
  document.getElementById('block'+i).style.background=col;
  document.getElementById('block'+i).style.boxShadow=bv>0?`0 0 12px ${col}`:'none';
  document.getElementById('row'+i).style.borderLeftColor=col;
}
async function loadState() {
  try {
    const data=await (await fetch('/state')).json();
    data.leds.forEach((led,i) => { document.getElementById('color'+i).value=rgbToHex(led.r,led.g,led.b); document.getElementById('bright'+i).value=led.brightness; update(i); });
  } catch(e) { console.error('Failed to load state',e); }
}
async function sendState() {
  const btn=document.getElementById('send-btn');
  const status=document.getElementById('status');
  btn.disabled=true; btn.textContent='Sending...'; status.textContent='';
  const leds=[];
  for (let i=0;i<N;i++) { const {r,g,b}=hexToRgb(document.getElementById('color'+i).value); leds.push({r,g,b,brightness:parseInt(document.getElementById('bright'+i).value)}); }
  try {
    const res=await fetch('/state',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({leds})});
    status.textContent=res.ok?'Saved':'Error: '+res.status;
  } catch(e) { status.textContent='Error: '+e.message; }
  finally { btn.disabled=false; btn.textContent='SEND'; setTimeout(()=>{status.textContent='';},3000); }
}
loadState();
</script>
</body>
</html>"""


def send_response(conn, status, content_type, body):
    if isinstance(body, str):
        body = body.encode()
    header = ("HTTP/1.1 %d OK\r\nContent-Type: %s\r\nContent-Length: %d\r\nConnection: close\r\n\r\n"
              % (status, content_type, len(body))).encode()
    conn.write(header)
    mv = memoryview(body)
    for i in range(0, len(body), 512):
        conn.write(mv[i:i+512])


def handle_request(conn):
    try:
        req = b""
        while b"\r\n\r\n" not in req:
            chunk = conn.recv(256)
            if not chunk:
                break
            req += chunk

        head, _, body_start = req.partition(b"\r\n\r\n")
        lines = head.decode().split("\r\n")
        parts = lines[0].split()
        if len(parts) < 2:
            return
        method, path = parts[0], parts[1]

        # Read body for POST
        body = body_start
        for line in lines[1:]:
            if line.lower().startswith("content-length:"):
                cl = int(line.split(":", 1)[1].strip())
                while len(body) < cl:
                    body += conn.recv(cl - len(body))
                break

        if method == "GET" and path == "/":
            send_response(conn, 200, "text/html; charset=utf-8", INDEX_HTML)

        elif method == "GET" and path == "/state":
            send_response(conn, 200, "application/json", json.dumps({"leds": led_states}))

        elif method == "POST" and path == "/state":
            try:
                data = json.loads(body)
                leds = data.get("leds", [])
                if len(leds) != NUM_LEDS:
                    raise ValueError("expected " + str(NUM_LEDS) + " leds")
                validated = []
                for led in leds:
                    entry = {}
                    for key in ("r", "g", "b", "brightness"):
                        v = int(led[key])
                        if not 0 <= v <= 255:
                            raise ValueError(key + " out of range: " + str(v))
                        entry[key] = v
                    validated.append(entry)
                for i, entry in enumerate(validated):
                    led_states[i].update(entry)
                apply_leds()
                save_state()
                send_response(conn, 200, "application/json", '{"ok":true}')
            except Exception as e:
                send_response(conn, 400, "application/json", json.dumps({"error": str(e)}))

        else:
            conn.write(b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")

    except Exception as e:
        print("Request error:", e)
    finally:
        conn.close()


def start_server():
    gc.collect()
    print("Free mem:", gc.mem_free())
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("", 80))
    srv.listen(5)
    print("Server ready on port 80")
    while True:
        try:
            conn, addr = srv.accept()
            conn.settimeout(5)
            handle_request(conn)
        except Exception as e:
            print("Accept error:", e)


# Boot sequence
apply_leds()  # clear strip immediately (all off) before WiFi connects
connect_wifi()

if load_state():
    print("State restored from state.json")
else:
    print("No state.json — all LEDs off")

apply_leds()
gc.collect()
print("Web server starting on port 80")
start_server()
