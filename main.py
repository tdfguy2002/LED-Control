import network
import neopixel
import machine
import json
import time

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
    """Connect to WiFi. On failure, set all LEDs dim red and halt."""
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


# Boot sequence
apply_leds()   # start with all LEDs off
connect_wifi()

print("Boot complete")
