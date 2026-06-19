# =============================================================================
# José Herrera Ortiz
# web_controller.py — Flask-based mobile web controller
# Raspberry Pi 3 RC Car
# =============================================================================
# Starts a lightweight HTTP server on port 8080.
# Open http://<RASPBERRY_PI_IP>:8080 in any browser on the same network to
# get a full touch joystick interface with acceleration and reverse controls.
# =============================================================================

from flask import Flask, request, jsonify
import threading
import time

app = Flask(__name__)

_lock = threading.Lock()
_state = {
    "direction": 0.0,
    "acceleration": 0.0,
    "reverse": False,
    "last_update": time.monotonic(),
}


@app.route("/")
def index() -> str:
    """Serve the mobile touch-joystick controller page."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, user-scalable=no">
    <title>RC Car Controller</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            background: #111;
            color: white;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100vh;
            gap: 30px;
            font-family: sans-serif;
            touch-action: none;
            user-select: none;
        }
        canvas {
            border-radius: 50%;
            background: #222;
            touch-action: none;
        }
        #accelerateBtn {
            width: 220px;
            height: 70px;
            background: #222;
            border-radius: 35px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 20px;
            border: 2px solid #444;
            touch-action: none;
            cursor: pointer;
        }
        #accelerateBtn.active {
            background: #2ecc71;
            color: black;
        }
        #reverseBtn {
            padding: 18px 40px;
            font-size: 20px;
            background: #444;
            color: white;
            border: none;
            border-radius: 12px;
            touch-action: none;
            cursor: pointer;
        }
        #reverseBtn.active {
            background: #c0392b;
        }
        #statusTxt {
            font-size: 16px;
            color: #bbb;
            min-height: 20px;
        }
    </style>
</head>
<body>
    <canvas id="joystick" width="220" height="220"></canvas>
    <div id="accelerateBtn">Accelerate</div>
    <button id="reverseBtn" type="button">Reverse</button>
    <div id="statusTxt">Ready</div>

<script>
"use strict";

const canvas        = document.getElementById("joystick");
const ctx           = canvas.getContext("2d");
const statusTxt     = document.getElementById("statusTxt");
const accelerateBtn = document.getElementById("accelerateBtn");
const reverseBtn    = document.getElementById("reverseBtn");

// Joystick geometry constants
const CX          = 110;
const CY          = 110;
const RADIUS      = 85;
const STICK_RADIUS = 28;

let stickX            = CX;
let stickY            = CY;
let pointerJoystick   = null;
let pointerAccelerate = null;
let reverseActive     = false;

// Drawing

function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Base ring
    ctx.beginPath();
    ctx.arc(CX, CY, RADIUS, 0, Math.PI * 2);
    ctx.fillStyle = "#333";
    ctx.fill();

    // Movable knob
    ctx.beginPath();
    ctx.arc(stickX, stickY, STICK_RADIUS, 0, Math.PI * 2);
    ctx.fillStyle = "#e74c3c";
    ctx.fill();
}

// Communication

function setStatus(msg) {
    statusTxt.textContent = msg;
}

async function send(data) {
    try {
        const res = await fetch("/state", {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify(data),
        });
        setStatus(res.ok ? "Connected" : "HTTP error " + res.status);
    } catch {
        setStatus("No connection");
    }
}

// Joystick helpers

function moveStick(clientX, clientY) {
    const rect = canvas.getBoundingClientRect();
    const dx   = clientX - rect.left - CX;
    const dy   = clientY - rect.top  - CY;
    const dist = Math.sqrt(dx * dx + dy * dy);

    // Constrain knob to the base circle
    if (dist > RADIUS) {
        stickX = CX + (dx / dist) * RADIUS;
        stickY = CY + (dy / dist) * RADIUS;
    } else {
        stickX = CX + dx;
        stickY = CY + dy;
    }

    // Normalise horizontal offset to [-1.0, 1.0] and send
    send({ direction: (stickX - CX) / RADIUS });
    draw();
}

function centerStick() {
    stickX = CX;
    stickY = CY;
    send({ direction: 0.0 });
    draw();
}

// Acceleration helpers

function startAcceleration() {
    accelerateBtn.classList.add("active");
    send({ acceleration: 1.0 });
}

function stopAcceleration() {
    accelerateBtn.classList.remove("active");
    send({ acceleration: 0.0 });
}

// Joystick pointer events

canvas.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    pointerJoystick = e.pointerId;
    canvas.setPointerCapture(e.pointerId);
    moveStick(e.clientX, e.clientY);
});
canvas.addEventListener("pointermove", (e) => {
    if (e.pointerId !== pointerJoystick) return;
    e.preventDefault();
    moveStick(e.clientX, e.clientY);
});
canvas.addEventListener("pointerup", (e) => {
    if (e.pointerId !== pointerJoystick) return;
    e.preventDefault();
    pointerJoystick = null;
    centerStick();
});
canvas.addEventListener("pointercancel", (e) => {
    if (e.pointerId !== pointerJoystick) return;
    e.preventDefault();
    pointerJoystick = null;
    centerStick();
});

// Accelerate button pointer events

accelerateBtn.addEventListener("pointerdown", (e) => {
    e.preventDefault();
    pointerAccelerate = e.pointerId;
    accelerateBtn.setPointerCapture(e.pointerId);
    startAcceleration();
});
accelerateBtn.addEventListener("pointerup", (e) => {
    if (e.pointerId !== pointerAccelerate) return;
    e.preventDefault();
    pointerAccelerate = null;
    stopAcceleration();
});
accelerateBtn.addEventListener("pointercancel", (e) => {
    if (e.pointerId !== pointerAccelerate) return;
    e.preventDefault();
    pointerAccelerate = null;
    stopAcceleration();
});

// Reverse button pointer events

reverseBtn.addEventListener("pointerdown", (e) => { e.preventDefault(); });
reverseBtn.addEventListener("pointerup", (e) => {
    e.preventDefault();
    reverseActive = !reverseActive;
    reverseBtn.classList.toggle("active", reverseActive);
    send({ reverse: reverseActive });
});

// Safety: stop the car if the browser tab is hidden or closed

document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
        centerStick();
        stopAcceleration();
    }
});
window.addEventListener("beforeunload", () => {
    centerStick();
    stopAcceleration();
});

// Initial render
draw();
</script>
</body>
</html>"""


@app.route("/state", methods=["POST"])
def set_state():
    """Receive a partial state update from the controller and merge it into
    the shared state dictionary."""
    data = request.get_json(silent=True) or {}

    with _lock:
        if "direction" in data:
            _state["direction"] = max(-1.0, min(1.0, float(data["direction"])))
        if "acceleration" in data:
            _state["acceleration"] = max(0.0, min(1.0, float(data["acceleration"])))
        if "reverse" in data:
            _state["reverse"] = bool(data["reverse"])
        _state["last_update"] = time.monotonic()

    return jsonify({"ok": True})


def read_state(timeout_s: float = 0.5) -> dict:
    """Return a thread-safe snapshot of the current controller state.

    If no update has been received within *timeout_s* seconds the direction
    and acceleration are reset to zero as a fail-safe (e.g. the phone's
    browser was closed or the connection was lost).
    """
    with _lock:
        state = _state.copy()

    if time.monotonic() - state["last_update"] > timeout_s:
        state["direction"] = 0.0
        state["acceleration"] = 0.0

    return state


def start_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    """Start the Flask server in a background daemon thread.

    Parameters
    ----------
    host : Interface to bind. ``"0.0.0.0"`` accepts connections from any
           device on the local network.
    port : TCP port number (default 8080).
    """
    threading.Thread(
        target=lambda: app.run(
            host=host,
            port=port,
            debug=False,
            use_reloader=False,
            threaded=True,
        ),
        daemon=True,
    ).start()


if __name__ == "__main__":
    from time import sleep

    start_server(host="0.0.0.0", port=8080)
    print("Server running — open on your phone: http://<RASPBERRY_PI_IP>:8080")

    while True:
        print(read_state(), end="\r")
        sleep(0.1)
