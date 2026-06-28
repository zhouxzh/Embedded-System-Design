from __future__ import annotations

import threading
import time
import webbrowser
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import serial
import serial.tools.list_ports
from flask import Flask, jsonify, render_template, request


APP_DIR = Path(__file__).resolve().parent
PC_BAUDRATE = 115200  # USB CDC line coding only; the physical transport is USB.
SERIAL_TIMEOUT = 0.05
LOG_LIMIT = 1200

DEFAULT_NAME = "SmartWatch"
DEFAULT_PIN = "1234"
DEFAULT_ROLE = "0"
DEFAULT_DATA_BAUD = "9600"


@dataclass
class LogEntry:
    seq: int
    source: str
    text: str
    ts: float


class SerialBridge:
    def __init__(self) -> None:
        self._serial: serial.Serial | None = None
        self._reader: threading.Thread | None = None
        self._running = False
        self._command_lock = threading.Lock()
        self._lock = threading.RLock()
        self._logs: deque[LogEntry] = deque(maxlen=LOG_LIMIT)
        self._seq = 0
        self._port = ""
        self._status = "Disconnected"

    def list_ports(self) -> list[dict[str, str]]:
        ports = []
        for port in serial.tools.list_ports.comports():
            ports.append(
                {
                    "device": port.device,
                    "description": port.description,
                    "hwid": port.hwid,
                    "label": f"{port.device} - {port.description}",
                }
            )
        return ports

    def state(self) -> dict[str, Any]:
        with self._lock:
            connected = self._serial is not None and self._serial.is_open
            return {
                "connected": connected,
                "port": self._port,
                "status": self._status,
                "baudrate": PC_BAUDRATE,
                "last_seq": self._seq,
            }

    def connect(self, port: str) -> tuple[bool, str]:
        port = port.strip()
        if not port:
            return False, "No COM port selected"

        with self._lock:
            if self._serial and self._serial.is_open:
                return False, f"Already connected to {self._port}"

            try:
                self._serial = serial.Serial(port, PC_BAUDRATE, timeout=SERIAL_TIMEOUT)
            except serial.SerialException as exc:
                self._serial = None
                self._status = f"Open {port} failed"
                self._append_log_locked("host", f"Open {port} failed: {exc}\n")
                return False, str(exc)

            self._port = port
            self._running = True
            self._status = f"Connected {port} (STM32 USB VCP)"
            self._append_log_locked("host", f"Connected {port} (STM32 USB VCP, line coding {PC_BAUDRATE})\n")

            self._reader = threading.Thread(target=self._read_loop, daemon=True)
            self._reader.start()
            return True, self._status

    def disconnect(self) -> tuple[bool, str]:
        reader: threading.Thread | None
        with self._lock:
            self._running = False
            reader = self._reader

        if reader:
            reader.join(timeout=1.0)

        with self._lock:
            if self._serial:
                try:
                    self._serial.close()
                except serial.SerialException:
                    pass
            self._serial = None
            self._reader = None
            old_port = self._port
            self._port = ""
            self._status = "Disconnected"
            self._append_log_locked("host", f"Disconnected {old_port}\n" if old_port else "Disconnected\n")
            return True, self._status

    def send_line(self, line: str, source: str = "host") -> tuple[bool, str]:
        if not self._command_lock.acquire(blocking=False):
            return False, "Another command is running"
        try:
            return self._send_line_unlocked(line, source=source)
        finally:
            self._command_lock.release()

    def _send_line_unlocked(self, line: str, source: str = "host") -> tuple[bool, str]:
        line = line.strip()
        if not line:
            return False, "Empty command"

        with self._lock:
            if not self._serial or not self._serial.is_open:
                return False, "Not connected"
            try:
                self._serial.write((line + "\r\n").encode("utf-8"))
            except serial.SerialException as exc:
                self._append_log_locked("host", f"Write failed: {exc}\n")
                return False, str(exc)

            self._append_log_locked(source, f"{line}\n")
            return True, "sent"

    def logs_since(self, after: int) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"seq": item.seq, "source": item.source, "text": item.text, "ts": item.ts}
                for item in self._logs
                if item.seq > after
            ]

    def clear_logs(self) -> None:
        with self._lock:
            self._logs.clear()

    def shutdown(self) -> None:
        self.disconnect()

    def _read_loop(self) -> None:
        while True:
            with self._lock:
                running = self._running
                ser = self._serial
            if not running or not ser or not ser.is_open:
                break

            try:
                data = ser.read(max(1, ser.in_waiting))
                if data:
                    text = data.decode("utf-8", errors="replace")
                    with self._lock:
                        self._append_log_locked("stm32", text)
                else:
                    time.sleep(0.01)
            except serial.SerialException as exc:
                with self._lock:
                    self._running = False
                    self._status = "Serial error"
                    self._append_log_locked("host", f"Serial error: {exc}\n")
                break

        with self._lock:
            self._running = False

    def _append_log_locked(self, source: str, text: str) -> None:
        self._seq += 1
        self._logs.append(LogEntry(seq=self._seq, source=source, text=text, ts=time.time()))


bridge = SerialBridge()
app = Flask(__name__, template_folder=str(APP_DIR / "templates"), static_folder=str(APP_DIR / "static"))


@app.get("/")
def index():
    return render_template(
        "index.html",
        default_name=DEFAULT_NAME,
        default_pin=DEFAULT_PIN,
        default_role=DEFAULT_ROLE,
        default_baud=DEFAULT_DATA_BAUD,
    )


@app.get("/api/ports")
def api_ports():
    return jsonify({"ports": bridge.list_ports(), "state": bridge.state()})


@app.get("/api/state")
def api_state():
    return jsonify(bridge.state())


@app.post("/api/connect")
def api_connect():
    data = request.get_json(silent=True) or {}
    ok, msg = bridge.connect(str(data.get("port", "")))
    return jsonify({"ok": ok, "message": msg, "state": bridge.state()}), 200 if ok else 400


@app.post("/api/disconnect")
def api_disconnect():
    ok, msg = bridge.disconnect()
    return jsonify({"ok": ok, "message": msg, "state": bridge.state()})


@app.post("/api/send")
def api_send():
    data = request.get_json(silent=True) or {}
    ok, msg = bridge.send_line(str(data.get("line", "")), source="host")
    return jsonify({"ok": ok, "message": msg, "state": bridge.state()}), 200 if ok else 400


@app.get("/api/logs")
def api_logs():
    after = request.args.get("after", "0")
    try:
        after_seq = int(after)
    except ValueError:
        after_seq = 0
    logs = bridge.logs_since(after_seq)
    return jsonify({"logs": logs, "state": bridge.state()})


@app.post("/api/logs/clear")
def api_logs_clear():
    bridge.clear_logs()
    return jsonify({"ok": True, "state": bridge.state()})


def open_browser() -> None:
    time.sleep(0.8)
    webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()
    try:
        app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
    finally:
        bridge.shutdown()
