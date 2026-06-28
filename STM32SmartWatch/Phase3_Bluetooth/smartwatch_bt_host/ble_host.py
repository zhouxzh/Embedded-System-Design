"""
BLE host for hc05V2.3_le-style modules.

This keeps the STM32 frame protocol unchanged, but replaces the Windows COM
port path with BLE GATT notifications/writes via bleak.
"""

from __future__ import annotations

import asyncio
import json
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
from tkinter import ttk
import tkinter as tk
from queue import Empty, Queue

from bleak import BLEDevice, BleakClient, BleakScanner

from bt_protocol import (
    BT_STX,
    BT_CMD_SENSOR_DATA,
    FrameParser,
    build_time_sync_cmd,
    parse_sensor_data,
)


APP_DIR = Path(__file__).resolve().parent
LOG_FILE = APP_DIR / "ble_host.log"
LAST_DEVICE_FILE = APP_DIR / ".ble_last_device.json"

TARGET_NAME = os.getenv("BLE_TARGET_NAME", "SMARTWATCH")
SCAN_WINDOW = float(os.getenv("BLE_SCAN_TIMEOUT", "10.0"))
CONNECT_SCAN_TIMEOUT = float(os.getenv("BLE_CONNECT_SCAN_TIMEOUT", "6.0"))
POLL_MS = 80

C_BG = "#1e1e2e"
C_BG2 = "#2a2a3c"
C_FG = "#cdd6f4"
C_ACCENT = "#89b4fa"
C_GREEN = "#a6e3a1"
C_RED = "#f38ba8"
C_YELLOW = "#f9e2af"
C_GRAY = "#6c7086"
C_BORDER = "#45475a"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-7s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("ble_host")


class BLEWorker:
    def __init__(self, events: Queue):
        self.events = events
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        self.client: BleakClient | None = None
        self.scanned_devices = {}
        self.notify_chars: list[str] = []
        self.write_chars: list[str] = []
        self.write_char: str | None = None
        self.parsers: dict[str, FrameParser] = {}
        self.frame_count = 0
        self.scanner: BleakScanner | None = None
        self.scan_stop_event: asyncio.Event | None = None
        self.scan_task: asyncio.Future | None = None

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def submit(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def scan(self):
        if self.scan_task and not self.scan_task.done():
            return self.scan_task
        self.scan_task = self.submit(self._scan())
        return self.scan_task

    def stop_scan(self):
        return self.submit(self._stop_scan())

    def connect(self, address: str):
        return self.submit(self._connect(address))

    def disconnect(self):
        return self.submit(self._disconnect())

    def send_time_sync(self):
        return self.submit(self._send_time_sync())

    async def _scan(self):
        self.events.put(("scan_state", True))
        self.events.put(("status", "Scanning BLE..."))
        rows_by_addr = {}
        self.scanned_devices.clear()
        self.scan_stop_event = asyncio.Event()

        def emit_devices():
            rows = sorted(
                rows_by_addr.values(),
                key=lambda d: (TARGET_NAME.upper() not in d["name"].upper(), d["name"], d["address"]),
            )
            self.events.put(("devices", rows))
            self.events.put(("status", f"Scanning BLE... found {len(rows)} named device(s)"))

        def on_detect(device, adv):
            name = adv.local_name or device.name or ""
            if not name:
                return
            self.scanned_devices[device.address] = device
            rows_by_addr[device.address] = {
                "name": name,
                "address": device.address,
                "rssi": getattr(adv, "rssi", None),
            }
            emit_devices()

        try:
            while not self.scan_stop_event.is_set():
                self.scanner = BleakScanner(detection_callback=on_detect, scanning_mode="active")
                await self.scanner.start()
                try:
                    await asyncio.wait_for(self.scan_stop_event.wait(), timeout=SCAN_WINDOW)
                except asyncio.TimeoutError:
                    pass
                finally:
                    await self.scanner.stop()
                    self.scanner = None
        finally:
            if self.scanner:
                await self.scanner.stop()
            self.scanner = None
            self.scan_stop_event = None
            self.events.put(("scan_state", False))

        rows = sorted(
            rows_by_addr.values(),
            key=lambda d: (TARGET_NAME.upper() not in d["name"].upper(), d["name"], d["address"]),
        )
        emit_devices()
        self.events.put(("status", f"Found {len(rows)} named BLE device(s)"))
        if not any(TARGET_NAME.upper() in row["name"].upper() for row in rows):
            self.events.put(("raw", f"{TARGET_NAME} not found in named BLE advertisements"))

    async def _stop_scan(self):
        if self.scan_stop_event:
            self.scan_stop_event.set()

        if self.scan_task and not self.scan_task.done():
            try:
                await asyncio.wrap_future(self.scan_task)
            except Exception as exc:
                self.events.put(("raw", f"stop scan warning: {exc}"))

    async def _connect(self, address: str):
        await self._stop_scan()
        await self._disconnect()
        self.parsers = {}
        self.frame_count = 0
        self.notify_chars = []
        self.write_chars = []
        self.write_char = None

        self.events.put(("status", f"Connecting {address}..."))
        target = await self._resolve_connect_target(address)
        self.client = BleakClient(target, disconnected_callback=self._on_disconnected)
        try:
            await asyncio.wait_for(self.client.connect(), timeout=12.0)
        except Exception as exc:
            self.client = None
            self.events.put(("status", f"Connect failed: {type(exc).__name__}"))
            self.events.put(("raw", f"connect failed {address}: {exc}"))
            return

        services = self.client.services
        service_lines = []
        for service in services:
            service_lines.append(f"[S] {service.uuid}")
            for char in service.characteristics:
                props = ",".join(char.properties)
                service_lines.append(f"  [C] {char.uuid}  {props}")
                if "notify" in char.properties or "indicate" in char.properties:
                    self.notify_chars.append(char.uuid)
                if "write" in char.properties or "write-without-response" in char.properties:
                    self.write_chars.append(char.uuid)

        self.write_char = self.write_chars[0] if self.write_chars else None
        self.events.put(("services", "\n".join(service_lines)))
        self.events.put(("connected", True))
        self.events.put(("connected_device", address, self._device_name_for_address(address)))
        self.events.put(("status", "Connected; enabling notifications..."))

        for uuid in self.notify_chars:
            try:
                self.parsers[uuid] = FrameParser()
                await self.client.start_notify(uuid, self._on_notify)
                self.events.put(("raw", f"notify on {uuid}"))
            except Exception as exc:
                self.events.put(("raw", f"notify failed {uuid}: {exc}"))

        if not self.notify_chars:
            self.events.put(("status", "Connected, but no notify characteristic found"))
        else:
            self.events.put(("status", f"Connected; notify={len(self.notify_chars)} write={len(self.write_chars)}"))

    def _cached_device_for_address(self, address: str):
        target = self.scanned_devices.get(address)
        if target:
            return target

        normalized = address.upper()
        for seen_address, device in self.scanned_devices.items():
            if seen_address.upper() == normalized:
                return device
        return None

    async def _resolve_connect_target(self, address: str):
        target = self._cached_device_for_address(address)
        if target:
            return target

        self.events.put(("status", f"Refreshing cached BLE device {address}..."))
        self.events.put(("raw", f"cached device has no live scan object; scanning up to {CONNECT_SCAN_TIMEOUT:.1f}s"))
        try:
            target = await BleakScanner.find_device_by_address(
                address,
                timeout=CONNECT_SCAN_TIMEOUT,
            )
        except Exception as exc:
            self.events.put(("raw", f"cached device refresh failed: {exc}; trying address directly"))
            return address

        if not target:
            if sys.platform == "win32":
                self.events.put(("raw", f"cached device {address} not advertising; trying paired Windows device"))
                return BLEDevice(address, TARGET_NAME, None)
            self.events.put(("raw", f"cached device {address} not seen; trying address directly"))
            return address

        self.scanned_devices[target.address] = target
        self.events.put(("raw", f"refreshed cached BLE device {target.name or TARGET_NAME} {target.address}"))
        return target

    async def _disconnect(self):
        if self.client:
            try:
                if self.client.is_connected:
                    for uuid in list(self.notify_chars):
                        try:
                            await self.client.stop_notify(uuid)
                        except Exception:
                            pass
                    await self.client.disconnect()
            finally:
                self.client = None
                self.notify_chars = []
                self.write_chars = []
                self.write_char = None
                self.parsers = {}
        self.events.put(("connected", False))

    async def _send_time_sync(self):
        if not self.client or not self.client.is_connected:
            self.events.put(("status", "Not connected"))
            return
        if not self.write_char:
            self.events.put(("status", "No writable BLE characteristic found"))
            return
        now = datetime.now()
        frame = build_time_sync_cmd(now.hour, now.minute, now.second, now.year, now.month, now.day)
        await self.client.write_gatt_char(self.write_char, frame, response=False)
        self.events.put(("status", f"Time sync sent via {self.write_char}"))
        self.events.put(("raw", f"tx {frame.hex(' ')}"))

    def _on_disconnected(self, _client):
        self.events.put(("connected", False))
        self.events.put(("status", "Disconnected"))

    def _on_notify(self, char, data: bytearray):
        chunk = bytes(data)
        char_id = str(getattr(char, "uuid", char))
        short_id = char_id.split("-")[0]
        self.events.put(("raw", f"rx {short_id} {chunk.hex(' ')}"))

        parser = self.parsers.setdefault(char_id, FrameParser())
        frames = parser.feed(chunk)
        if not frames:
            if BT_STX not in chunk:
                self.events.put(("raw", "no frame start 0xAA in chunk; check UART baudrate/wiring"))
            return
        for cmd, payload in frames:
            self.frame_count += 1
            if cmd == BT_CMD_SENSOR_DATA:
                try:
                    sensor = parse_sensor_data(payload)
                    pitch, roll = calc_attitude(sensor)
                    self.events.put(("sensor", sensor, pitch, roll, self.frame_count))
                except (ValueError, struct.error) as exc:
                    self.events.put(("raw", f"bad sensor frame: {exc}"))
            else:
                self.events.put(("raw", f"frame cmd=0x{cmd:02X} len={len(payload)}"))

    def _device_name_for_address(self, address: str) -> str:
        for device in self.scanned_devices.values():
            if device.address == address:
                return device.name or TARGET_NAME
        return TARGET_NAME


def calc_attitude(sensor: dict) -> tuple[float, float]:
    denom_p = math.sqrt(max(sensor["ay"] ** 2 + sensor["az"] ** 2, 1e-9))
    pitch = math.atan2(sensor["ax"], denom_p) * 180.0 / math.pi
    denom_r = math.sqrt(max(sensor["ax"] ** 2 + sensor["az"] ** 2, 1e-9))
    roll = math.atan2(sensor["ay"], denom_r) * 180.0 / math.pi
    return pitch, roll


class BLEHostApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SmartWatch BLE Host")
        self.geometry("880x620")
        self.minsize(760, 520)
        self.configure(bg=C_BG)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.events: Queue = Queue()
        self.worker = BLEWorker(self.events)
        self.devices: dict[str, str] = {}
        self.connected = False
        self.scanning = False

        self._setup_theme()
        self._build_ui()
        self._load_last_device()
        self.after(POLL_MS, self._poll)

    def _setup_theme(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background=C_BG, foreground=C_FG, fieldbackground=C_BG2)
        style.configure("TLabel", background=C_BG, foreground=C_FG)
        style.configure("TButton", background=C_BG2, foreground=C_FG, padding=(8, 4))
        style.map("TButton", background=[("active", C_BORDER)])
        style.configure("TCombobox", fieldbackground=C_BG2, background=C_BG2, foreground=C_FG)
        style.map("TCombobox", fieldbackground=[("readonly", C_BG2)], foreground=[("readonly", C_FG)])
        style.configure("TLabelframe", background=C_BG, foreground=C_ACCENT)
        style.configure("TLabelframe.Label", background=C_BG, foreground=C_ACCENT)

    def _build_ui(self):
        top = tk.Frame(self, bg=C_BG2)
        top.pack(fill=tk.X)
        inner = tk.Frame(top, bg=C_BG2)
        inner.pack(fill=tk.X, padx=10, pady=8)

        ttk.Label(inner, text="BLE Device:", background=C_BG2).pack(side=tk.LEFT)
        self.device_var = tk.StringVar()
        self.device_cb = ttk.Combobox(inner, textvariable=self.device_var, width=46, state="readonly")
        self.device_cb.pack(side=tk.LEFT, padx=6)
        self.scan_btn = ttk.Button(inner, text="Scan", command=self._scan)
        self.scan_btn.pack(side=tk.LEFT, padx=4)
        self.stop_scan_btn = ttk.Button(inner, text="Stop Scan", command=self._stop_scan, state=tk.DISABLED)
        self.stop_scan_btn.pack(side=tk.LEFT, padx=4)
        self.conn_btn = ttk.Button(inner, text="Connect", command=self._toggle_connect)
        self.conn_btn.pack(side=tk.LEFT, padx=4)
        ttk.Button(inner, text="Sync Time", command=self._sync_time).pack(side=tk.LEFT, padx=4)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(inner, textvariable=self.status_var, background=C_BG2, foreground=C_GRAY).pack(side=tk.RIGHT)

        main = tk.Frame(self, bg=C_BG)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=8)

        left = ttk.Labelframe(main, text="Sensor", padding=8)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))

        self.frame_var = tk.StringVar(value="Frames: 0")
        ttk.Label(left, textvariable=self.frame_var, font=("Consolas", 12, "bold")).pack(anchor=tk.W, pady=(0, 8))

        self.value_vars = {}
        for key in ("ax", "ay", "az", "gx", "gy", "gz", "pitch", "roll"):
            row = tk.Frame(left, bg=C_BG)
            row.pack(fill=tk.X, pady=3)
            ttk.Label(row, text=f"{key}:", width=7, anchor=tk.E, foreground=C_GRAY).pack(side=tk.LEFT)
            var = tk.StringVar(value="---")
            self.value_vars[key] = var
            ttk.Label(row, textvariable=var, width=12, font=("Consolas", 12, "bold")).pack(side=tk.LEFT)

        right = tk.Frame(main, bg=C_BG)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        svc = ttk.Labelframe(right, text="BLE Services", padding=6)
        svc.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        self.services_text = tk.Text(svc, height=12, bg=C_BG2, fg=C_FG, insertbackground=C_FG, relief=tk.FLAT)
        self.services_text.pack(fill=tk.BOTH, expand=True)

        raw = ttk.Labelframe(right, text="Raw Log", padding=6)
        raw.pack(fill=tk.BOTH, expand=True)
        self.raw_text = tk.Text(raw, height=10, bg=C_BG2, fg=C_FG, insertbackground=C_FG, relief=tk.FLAT)
        self.raw_text.pack(fill=tk.BOTH, expand=True)

    def _scan(self):
        self.worker.scan()

    def _stop_scan(self):
        self.worker.stop_scan()

    def _toggle_connect(self):
        if self.connected:
            self.worker.disconnect()
            return
        item = self.device_var.get()
        address = self.devices.get(item)
        if not address:
            self._set_status("Select a BLE device first")
            return
        self.worker.connect(address)

    def _sync_time(self):
        self.worker.send_time_sync()

    def _poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                self._handle_event(event)
        except Empty:
            pass
        except Exception:
            log.error("UI poll failed:\n%s", traceback.format_exc())
        self.after(POLL_MS, self._poll)

    def _handle_event(self, event):
        kind = event[0]
        if kind == "status":
            self._set_status(event[1])
        elif kind == "devices":
            self._set_devices(event[1])
        elif kind == "connected":
            self.connected = bool(event[1])
            self.conn_btn.config(text="Disconnect" if self.connected else "Connect")
        elif kind == "scan_state":
            self.scanning = bool(event[1])
            self.scan_btn.config(state=tk.DISABLED if self.scanning else tk.NORMAL)
            self.stop_scan_btn.config(state=tk.NORMAL if self.scanning else tk.DISABLED)
        elif kind == "connected_device":
            self._save_last_device(event[1], event[2])
        elif kind == "services":
            self.services_text.delete("1.0", tk.END)
            self.services_text.insert(tk.END, event[1])
        elif kind == "raw":
            self._append_raw(event[1])
        elif kind == "sensor":
            sensor, pitch, roll, frame_count = event[1], event[2], event[3], event[4]
            self.frame_var.set(f"Frames: {frame_count}")
            for key in ("ax", "ay", "az", "gx", "gy", "gz"):
                self.value_vars[key].set(f"{sensor[key]:.2f}")
            self.value_vars["pitch"].set(f"{pitch:.1f}")
            self.value_vars["roll"].set(f"{roll:.1f}")

    def _set_devices(self, rows):
        labels = []
        self.devices.clear()
        for row in rows:
            rssi = "" if row["rssi"] is None else f" RSSI {row['rssi']}"
            label = f"{row['name']}  {row['address']}{rssi}"
            labels.append(label)
            self.devices[label] = row["address"]
        self.device_cb["values"] = labels
        target_label = ""
        for label in labels:
            if TARGET_NAME.upper() in label.upper():
                target_label = label
                break
        if target_label:
            self.device_var.set(target_label)
        elif labels and self.device_var.get() not in labels:
            self.device_var.set(labels[0])
        elif not labels:
            self.device_var.set("")

    def _load_last_device(self):
        try:
            data = json.loads(LAST_DEVICE_FILE.read_text(encoding="utf-8"))
            name = str(data.get("name") or TARGET_NAME)
            address = str(data.get("address") or "")
        except (OSError, json.JSONDecodeError):
            return

        if not address:
            return

        label = f"{name}  {address}  cached"
        self.devices[label] = address
        self.device_cb["values"] = [label]
        self.device_var.set(label)
        self._set_status(f"Loaded cached BLE device: {name}")

    def _save_last_device(self, address: str, name: str):
        if not address:
            return
        try:
            LAST_DEVICE_FILE.write_text(
                json.dumps({"name": name or TARGET_NAME, "address": address}, indent=2),
                encoding="utf-8",
            )
            self._append_raw(f"cached BLE device {name or TARGET_NAME} {address}")
        except OSError as exc:
            self._append_raw(f"cache save failed: {exc}")

    def _set_status(self, text: str):
        self.status_var.set(text)
        log.info(text)

    def _append_raw(self, text: str):
        ts = time.strftime("%H:%M:%S")
        self.raw_text.insert(tk.END, f"[{ts}] {text}\n")
        self.raw_text.see(tk.END)

    def _on_close(self):
        try:
            self.worker.stop_scan().result(timeout=3)
            self.worker.disconnect().result(timeout=3)
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    app = BLEHostApp()
    app.mainloop()
