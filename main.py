import network
import neopixel
import machine
import json
import time
import uasyncio
from microdot import Microdot, Response

app = Microdot()

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


@app.route("/state", methods=["GET"])
async def get_state(request):
    return Response(
        body=json.dumps({"leds": led_states}),
        headers={"Content-Type": "application/json"}
    )


@app.route("/state", methods=["POST"])
async def post_state(request):
    try:
        data = request.json
        leds = data.get("leds", [])
        if len(leds) != NUM_LEDS:
            return Response(
                body=json.dumps({"error": "expected 8 leds"}),
                status_code=400,
                headers={"Content-Type": "application/json"}
            )
        for i, led in enumerate(leds):
            led_states[i]["r"] = int(led["r"])
            led_states[i]["g"] = int(led["g"])
            led_states[i]["b"] = int(led["b"])
            led_states[i]["brightness"] = int(led["brightness"])
        apply_leds()
        save_state()
        return Response(
            body=json.dumps({"ok": True}),
            headers={"Content-Type": "application/json"}
        )
    except Exception as e:
        return Response(
            body=json.dumps({"error": str(e)}),
            status_code=400,
            headers={"Content-Type": "application/json"}
        )


# Boot sequence
connect_wifi()

if load_state():
    print("State restored from state.json")
else:
    print("No state.json — all LEDs off")

apply_leds()
print("Web server starting on port 80")
uasyncio.run(app.start_server(port=80))
