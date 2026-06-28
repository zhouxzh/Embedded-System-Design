"""
SmartWatch Phase 3 — Web-based Bluetooth Host (Linux + BlueZ)

Run on Orange Pi / Ascend 310B:
    python web_host.py

Then open in PC browser:
    http://<device-ip>:5000

Uses HC-05 as an RFCOMM serial device, usually /dev/rfcomm0.
Pair HC-05 once with bluetoothctl, bind it with rfcomm, then run this app.
"""

from __future__ import annotations

import logging
import math
import os
import struct
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import serial

from bt_protocol import (
    BT_CMD_SENSOR_DATA, BT_CMD_TIME_SYNC,
    FrameParser, parse_sensor_data, build_time_sync_cmd,
    HC05_DEFAULTS, STM32_PINS,
)

# ── Config ──────────────────────────────────────────────────
APP_DIR = Path(__file__).resolve().parent
LOG_FILE = APP_DIR / "web_host.log"

# HC-05 MAC 地址（bluetoothctl devices 查看，必须设置）
BT_MAC = os.environ.get("BT_MAC", "4B:63:DA:3A:2C:DB")
BT_CHANNEL = int(os.environ.get("BT_CHANNEL", "1"))
RFCOMM_DEVICE = os.environ.get("RFCOMM_DEVICE", "/dev/rfcomm0")
BAUDRATE = int(os.environ.get("BT_BAUDRATE", "38400"))
WEB_PORT = int(os.environ.get("WEB_PORT", "5000"))
READ_TIMEOUT = 0.1         # serial read timeout
RECONNECT_DELAY = 2.0      # seconds between reconnect attempts
EMIT_INTERVAL = 0.1        # throttle WebSocket emits

# ── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)-7s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("web_host")

# ── Flask + SocketIO ────────────────────────────────────────
app = Flask(__name__)
app.config["SECRET_KEY"] = "smartwatch-bt-host"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading",
                    logger=False, engineio_logger=False)

# ── Global state ────────────────────────────────────────────
STATE_LOCK = threading.Lock()
state = {
    "connected": False,
    "device": RFCOMM_DEVICE,
    "baudrate": BAUDRATE,
    "frame_count": 0,
    "sensor": None,
    "pitch": 0.0,
    "roll": 0.0,
    "last_sync": "",
    "error": "",
}

_ser: serial.Serial | None = None
_running = False
_thread: threading.Thread | None = None


# ═══════════════════════════════════════════════════════════
#  RFCOMM SERIAL CONNECTION
# ═══════════════════════════════════════════════════════════

def _connect_serial():
    """Open the rfcomm serial device created by BlueZ."""
    try:
        ser = serial.Serial(
            RFCOMM_DEVICE,
            BAUDRATE,
            timeout=READ_TIMEOUT,
            write_timeout=1.0,
        )
        log.info(f"Connected via RFCOMM serial → {RFCOMM_DEVICE} @ {BAUDRATE}")
        return ser
    except serial.SerialException as e:
        log.error(f"Cannot open {RFCOMM_DEVICE}: {e}")
        log.error(
            f"Bind first: sudo rfcomm bind {RFCOMM_DEVICE} {BT_MAC} {BT_CHANNEL}"
        )
        return None


def _close_serial():
    global _ser
    if _ser:
        try:
            _ser.close()
        except Exception:
            pass
        _ser = None


# ═══════════════════════════════════════════════════════════
#  SERIAL READ THREAD
# ═══════════════════════════════════════════════════════════

def _serial_loop():
    global _ser, _running, state
    log.info("Serial thread starting (RFCOMM serial mode)")
    parser = FrameParser()
    last_emit = 0.0
    err_count = 0

    while _running and _ser:
        try:
            chunk = _ser.read(64)
            if chunk:
                frames = parser.feed(chunk)
                for cmd, data in frames:
                    state["frame_count"] += 1
                    if cmd == BT_CMD_SENSOR_DATA:
                        try:
                            s = parse_sensor_data(data)
                            denom_p = math.sqrt(max(s["ay"]**2 + s["az"]**2, 1e-9))
                            pitch = math.atan2(s["ax"], denom_p) * 180.0 / math.pi
                            denom_r = math.sqrt(max(s["ax"]**2 + s["az"]**2, 1e-9))
                            roll  = math.atan2(s["ay"], denom_r) * 180.0 / math.pi
                            with STATE_LOCK:
                                state["sensor"] = s
                                state["pitch"] = pitch
                                state["roll"] = roll
                        except (ValueError, struct.error) as e:
                            log.debug(f"Bad frame: {e}")

            now = time.monotonic()
            if now - last_emit >= EMIT_INTERVAL:
                _emit_state()
                last_emit = now
            err_count = 0

        except serial.SerialException as e:
            err_count += 1
            log.error(f"Serial error (count={err_count}): {e}")
            if err_count >= 3:
                break
            time.sleep(0.5)
        except Exception:
            log.critical(f"Fatal:\n{traceback.format_exc()}")
            break

    log.info("Serial thread exited")
    _cleanup()


def _cleanup():
    global _ser, _running, _thread
    _running = False
    _thread = None
    _close_serial()
    with STATE_LOCK:
        state["connected"] = False
        state["error"] = "Connection lost — click Connect to retry"
    _emit_state()


def _emit_state():
    with STATE_LOCK:
        s = dict(state)
    sensor = s.pop("sensor", None)
    socketio.emit("state", s)
    if sensor:
        socketio.emit("sensor", sensor)


def _start():
    global _ser, _running, _thread

    _close_serial()

    ser = _connect_serial()
    if not ser:
        return False

    _ser = ser
    _running = True
    state["frame_count"] = 0
    state["connected"] = True
    state["error"] = ""
    state["device"] = RFCOMM_DEVICE
    state["baudrate"] = BAUDRATE
    _thread = threading.Thread(target=_serial_loop, daemon=True)
    _thread.start()
    log.info(f"Connected to {RFCOMM_DEVICE}")
    return True


def _stop():
    global _ser, _running, _thread
    _running = False
    if _thread:
        _thread.join(timeout=2.0)
        _thread = None
    _close_serial()
    with STATE_LOCK:
        state["connected"] = False
        state["error"] = ""
        state["frame_count"] = 0
    log.info("Stopped")


# ═══════════════════════════════════════════════════════════
#  FLASK ROUTES
# ═══════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html",
                           hc05=HC05_DEFAULTS,
                           pins=STM32_PINS)


@app.route("/api/status")
def api_status():
    with STATE_LOCK:
        return jsonify({
            "connected": state["connected"],
            "device": state["device"],
            "frame_count": state["frame_count"],
            "error": state["error"],
        })


# ═══════════════════════════════════════════════════════════
#  SOCKET.IO EVENTS
# ═══════════════════════════════════════════════════════════

@socketio.on("connect")
def on_connect():
    log.info(f"Client connected: {request.sid}")
    _emit_state()


@socketio.on("disconnect")
def on_disconnect():
    log.info(f"Client disconnected: {request.sid}")


@socketio.on("connect_serial")
def on_connect_serial():
    ok = _start()
    socketio.emit("serial_result", {
        "ok": ok,
        "device": RFCOMM_DEVICE,
        "error": "" if ok else (
            f"Cannot open {RFCOMM_DEVICE}. "
            f"Bind it first: sudo rfcomm bind {RFCOMM_DEVICE} {BT_MAC} {BT_CHANNEL}"
        )
    })


@socketio.on("disconnect_serial")
def on_disconnect_serial():
    _stop()
    socketio.emit("serial_result", {"ok": True, "device": "", "error": ""})


@socketio.on("sync_time")
def on_sync_time():
    global _ser
    if not _ser:
        emit("sync_result", {"ok": False, "msg": "Not connected"})
        return
    now = datetime.now()
    try:
        frame = build_time_sync_cmd(
            hour=now.hour, minute=now.minute, second=now.second,
            year=now.year, month=now.month, day=now.day,
        )
        _ser.write(frame)
        ts = now.strftime("%Y-%m-%d %H:%M:%S")
        state["last_sync"] = ts
        emit("sync_result", {"ok": True, "msg": ts})
        log.info(f"Time sync sent: {ts}")
    except Exception as e:
        log.error(f"Time sync failed: {e}")
        emit("sync_result", {"ok": False, "msg": str(e)})


# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════

def main():
    log.info("=" * 50)
    log.info("SmartWatch Web Host starting (RFCOMM serial mode)")
    log.info(
        f"Target: {BT_MAC}  Channel: {BT_CHANNEL}  "
        f"Device: {RFCOMM_DEVICE}  Baudrate: {BAUDRATE}  Port: {WEB_PORT}"
    )

    # try auto-connect
    if _start():
        log.info("Auto-connected to HC-05")
    else:
        log.warning("Auto-connect failed. Click Connect in browser after binding rfcomm.")
        log.warning(
            f"Current binding command: sudo rfcomm bind {RFCOMM_DEVICE} "
            f"{BT_MAC} {BT_CHANNEL}"
        )

    socketio.run(app, host="0.0.0.0", port=WEB_PORT, debug=False, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()
