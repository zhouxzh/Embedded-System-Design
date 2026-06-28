"""
SmartWatch Phase 3 — Bluetooth Host PC (tkinter + matplotlib)

Features:
  - Serial connection to HC-05 over Bluetooth virtual COM port
  - Real-time scrolling line charts for accelerometer & gyroscope
  - Attitude display (pitch / roll computed from accelerometer)
  - HC-05 / STM32 pinout settings panel
  - One-click PC-to-watch time sync
  - Dark theme
  - Log file output for debugging
"""

from __future__ import annotations

import collections
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

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import serial
import serial.tools.list_ports

from bt_protocol import (
    BT_STX, BT_ETX,
    BT_CMD_SENSOR_DATA, BT_CMD_TIME_SYNC,
    FrameParser, parse_sensor_data, build_time_sync_cmd,
    HC05_DEFAULTS, STM32_PINS,
)

# ── Paths ────────────────────────────────────────────────────
APP_DIR = Path(__file__).resolve().parent
LOG_FILE = APP_DIR / "bt_host.log"

# ── Logging Setup ────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)-7s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("bt_host")

# ── Constants ───────────────────────────────────────────────
BAUDRATE       = 38400
CHART_HISTORY  = 120          # number of samples kept per chart line
CHART_YLIM_ACC = (-20, 20)    # m/s²
CHART_YLIM_GYR = (-500, 500)  # deg/s
SERIAL_TIMEOUT = 0.05
POLL_MS        = 50           # UI update timer interval

# ── Color Palette (dark theme) ──────────────────────────────
C_BG        = "#1e1e2e"
C_BG2       = "#2a2a3c"
C_FG        = "#cdd6f4"
C_ACCENT    = "#89b4fa"
C_GREEN     = "#a6e3a1"
C_RED       = "#f38ba8"
C_YELLOW    = "#f9e2af"
C_ORANGE    = "#fab387"
C_BLUE      = "#89b4fa"
C_PURPLE    = "#cba6f7"
C_GRAY      = "#6c7086"
C_BORDER    = "#45475a"

LINE_COLORS = {"ax": C_RED, "ay": C_GREEN, "az": C_BLUE,
               "gx": C_RED, "gy": C_GREEN, "gz": C_BLUE}


# ╔═══════════════════════════════════════════════════════════╗
# ║                    APPLICATION CLASS                      ║
# ╚═══════════════════════════════════════════════════════════╝

class SmartWatchHost(tk.Tk):
    """Main application window."""

    def __init__(self):
        super().__init__()
        log.info("=" * 50)
        log.info("SmartWatch Bluetooth Host starting")
        log.info(f"Log file: {LOG_FILE}")

        self.title("SmartWatch Bluetooth Host")
        self.geometry("920x680")
        self.minsize(860, 600)
        self.configure(bg=C_BG)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # ── State ───────────────────────────────────────
        self._ser: serial.Serial | None = None
        self._running = False
        self._frame_count = 0

        # ring buffers for chart data
        self._acc_hist = {k: collections.deque(maxlen=CHART_HISTORY)
                          for k in ("ax", "ay", "az")}
        self._gyr_hist = {k: collections.deque(maxlen=CHART_HISTORY)
                          for k in ("gx", "gy", "gz")}

        # thread-safe latest sensor snapshot
        self._sensor_lock = threading.Lock()
        self._latest_sensor: dict | None = None

        self._parser = FrameParser()
        self._thread: threading.Thread | None = None
        self._poll_id: str | None = None

        self._setup_theme()
        self._build_toolbar()
        self._build_body()
        self._build_bottom_bar()
        self._safe_refresh_ports()

        # periodic UI refresh
        self._schedule_poll()

    # ── Dark Theme ──────────────────────────────────────
    def _setup_theme(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        self.option_add("*Font", ("Segoe UI", 9))

        style.configure(".", background=C_BG, foreground=C_FG,
                        fieldbackground=C_BG2, borderwidth=0)
        style.configure("TLabel", background=C_BG, foreground=C_FG)
        style.configure("TButton", background=C_BG2, foreground=C_FG,
                        borderwidth=1, focusthickness=0, padding=(8, 3))
        style.map("TButton",
                  background=[("active", C_BORDER), ("disabled", C_BG2)],
                  foreground=[("disabled", C_GRAY)])
        style.configure("TCombobox",
                        fieldbackground=C_BG2, background=C_BG2,
                        foreground=C_FG, arrowcolor=C_FG)
        style.map("TCombobox",
                  fieldbackground=[("readonly", C_BG2)],
                  foreground=[("readonly", C_FG)])
        style.configure("TLabelframe", background=C_BG, foreground=C_ACCENT,
                        borderwidth=1, relief="solid")
        style.configure("TLabelframe.Label", background=C_BG, foreground=C_ACCENT,
                        font=("Segoe UI", 9, "bold"))
        style.configure("TEntry", fieldbackground=C_BG2, foreground=C_FG,
                        insertcolor=C_FG)
        style.configure("TSeparator", background=C_BORDER)

        style.configure("Accent.TButton", background=C_GREEN, foreground="#1e1e2e")
        style.map("Accent.TButton",
                  background=[("active", "#8bd88b"), ("disabled", C_BG2)],
                  foreground=[("disabled", C_GRAY)])

    # ── Toolbar ─────────────────────────────────────────
    def _build_toolbar(self):
        bar = tk.Frame(self, bg=C_BG2, height=44)
        bar.pack(fill=tk.X, padx=0, pady=0)
        bar.pack_propagate(False)

        inner = tk.Frame(bar, bg=C_BG2)
        inner.pack(fill=tk.BOTH, padx=10, pady=5)

        ttk.Label(inner, text="COM Port:", background=C_BG2).pack(side=tk.LEFT, padx=(0, 4))
        self._port_var = tk.StringVar()
        self._port_cb = ttk.Combobox(inner, textvariable=self._port_var,
                                     width=42, state="readonly")
        self._port_cb.pack(side=tk.LEFT, padx=(0, 4))

        ttk.Button(inner, text="⟳", width=3, command=self._safe_refresh_ports).pack(side=tk.LEFT, padx=(0, 8))

        self._conn_btn = ttk.Button(inner, text="Connect", style="Accent.TButton",
                                    command=self._safe_toggle_connect, width=10)
        self._conn_btn.pack(side=tk.LEFT, padx=(0, 10))

        self._conn_dot = tk.Canvas(inner, width=12, height=12, bg=C_BG2, highlightthickness=0)
        self._conn_dot.pack(side=tk.LEFT, padx=(0, 4))
        self._draw_dot(C_GRAY)
        self._conn_lbl = ttk.Label(inner, text="Disconnected", background=C_BG2,
                                   font=("Segoe UI", 9, "bold"))
        self._conn_lbl.pack(side=tk.LEFT)

        self._frame_lbl = ttk.Label(inner, text="Frames: 0", background=C_BG2,
                                    font=("Consolas", 10))
        self._frame_lbl.pack(side=tk.RIGHT)

    def _draw_dot(self, color: str):
        self._conn_dot.delete("all")
        self._conn_dot.create_oval(1, 1, 11, 11, fill=color, outline="")

    # ── Body ────────────────────────────────────────────
    def _build_body(self):
        body = tk.Frame(self, bg=C_BG)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 0))
        self._build_settings_panel(body)
        right = tk.Frame(body, bg=C_BG)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self._build_charts(right)
        self._build_value_panel(right)

    # ── Settings panel (left) ───────────────────────────
    def _build_settings_panel(self, parent: tk.Frame):
        left = ttk.Labelframe(parent, text="HC-05 / STM32 Settings", padding=8)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))

        ttk.Label(left, text="Module Parameters",
                  font=("Segoe UI", 9, "bold"), foreground=C_ACCENT).pack(anchor=tk.W, pady=(0, 4))
        for key, val in HC05_DEFAULTS.items():
            row = tk.Frame(left, bg=C_BG)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=f"{key}:", width=9, anchor=tk.W,
                      font=("Consolas", 9), foreground=C_GRAY).pack(side=tk.LEFT)
            ttk.Label(row, text=val, font=("Consolas", 9, "bold")).pack(side=tk.LEFT)

        ttk.Separator(left, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        ttk.Label(left, text="STM32 Pin Mapping",
                  font=("Segoe UI", 9, "bold"), foreground=C_ACCENT).pack(anchor=tk.W, pady=(0, 4))
        for key, desc in STM32_PINS.items():
            row = tk.Frame(left, bg=C_BG)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=f"{key}:", width=7, anchor=tk.W,
                      font=("Consolas", 9), foreground=C_GRAY).pack(side=tk.LEFT)
            ttk.Label(row, text=desc, font=("Consolas", 8)).pack(side=tk.LEFT)

        ttk.Separator(left, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        ttk.Label(left, text="Binary Frame Protocol",
                  font=("Segoe UI", 9, "bold"), foreground=C_ACCENT).pack(anchor=tk.W, pady=(0, 4))
        proto_text = (
            f"STX 0x{BT_STX:02X}  CMD  LEN  DATA…  CHK  ETX 0x{BT_ETX:02X}\n"
            f"CHK = CMD ^ LEN ^ DATA[0] ^ …\n"
            f"CMD 0x{BT_CMD_SENSOR_DATA:02X} = Sensor (6×float LE)\n"
            f"CMD 0x{BT_CMD_TIME_SYNC:02X} = Time Sync (7B)"
        )
        ttk.Label(left, text=proto_text, font=("Consolas", 7),
                  foreground=C_GRAY, justify=tk.LEFT).pack(anchor=tk.W)

    # ── Real-time charts ────────────────────────────────
    def _build_charts(self, parent: tk.Frame):
        try:
            self._fig = Figure(figsize=(6, 4), dpi=100, facecolor=C_BG)
            self._fig.subplots_adjust(left=0.08, right=0.97, top=0.94, bottom=0.10, hspace=0.35)

            self._ax_acc = self._fig.add_subplot(2, 1, 1, facecolor=C_BG2)
            self._ax_gyr = self._fig.add_subplot(2, 1, 2, facecolor=C_BG2)

            for ax, title, ylim in [
                (self._ax_acc, "Accelerometer (m/s²)", CHART_YLIM_ACC),
                (self._ax_gyr, "Gyroscope (deg/s)",       CHART_YLIM_GYR),
            ]:
                ax.set_facecolor(C_BG2)
                ax.set_ylim(*ylim)
                ax.set_xlim(0, CHART_HISTORY - 1)
                ax.set_title(title, color=C_FG, fontsize=9, fontweight="bold", pad=4)
                ax.tick_params(colors=C_GRAY, labelsize=7)
                ax.spines["bottom"].set_color(C_BORDER)
                ax.spines["left"].set_color(C_BORDER)
                ax.spines["top"].set_visible(False)
                ax.spines["right"].set_visible(False)
                ax.grid(True, color=C_BORDER, linewidth=0.5, alpha=0.5)

            for ax, labels in [(self._ax_acc, ["ax", "ay", "az"]),
                                (self._ax_gyr, ["gx", "gy", "gz"])]:
                ax.legend(labels, loc="upper right", fontsize=6,
                          facecolor=C_BG2, edgecolor=C_BORDER,
                          labelcolor=C_FG, ncol=3)

            self._acc_lines = {}
            self._gyr_lines = {}
            for k, ax, d in [("acc", self._ax_acc, self._acc_lines),
                               ("gyr", self._ax_gyr, self._gyr_lines)]:
                for lbl in (("ax","ay","az") if k == "acc" else ("gx","gy","gz")):
                    (d[lbl],) = ax.plot([], [], color=LINE_COLORS[lbl],
                                        linewidth=1.0, label=lbl)

            self._canvas = FigureCanvasTkAgg(self._fig, master=parent)
            self._canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            log.info("Charts initialized")
        except Exception:
            log.error(f"Failed to init charts:\n{traceback.format_exc()}")
            tk.Label(parent, text="Chart init failed — see log", fg=C_RED, bg=C_BG).pack()

    # ── Current values + attitude ──────────────────────
    def _build_value_panel(self, parent: tk.Frame):
        panel = tk.Frame(parent, bg=C_BG2)
        panel.pack(fill=tk.X, pady=(6, 0))

        cols = [
            ("Accel (m/s²)", ("ax", "ay", "az")),
            ("Gyro (deg/s)", ("gx", "gy", "gz")),
            ("Attitude",    ("pitch", "roll")),
        ]

        self._val_labels: dict[str, tk.Label] = {}

        for col_title, keys in cols:
            f = tk.Frame(panel, bg=C_BG2)
            f.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=6, pady=4)
            ttk.Label(f, text=col_title, font=("Segoe UI", 8, "bold"),
                      foreground=C_ACCENT, background=C_BG2).pack(anchor=tk.W, pady=(0, 2))
            for key in keys:
                row = tk.Frame(f, bg=C_BG2)
                row.pack(fill=tk.X, pady=1)
                ttk.Label(row, text=f"{key}:", width=7, anchor=tk.E,
                          font=("Consolas", 10), foreground=C_GRAY,
                          background=C_BG2).pack(side=tk.LEFT, padx=(0, 4))
                lbl = tk.Label(row, text="---", font=("Consolas", 13, "bold"),
                               fg=C_FG, bg=C_BG2, anchor=tk.W, width=8)
                lbl.pack(side=tk.LEFT)
                self._val_labels[key] = lbl

    # ── Bottom bar ──────────────────────────────────────
    def _build_bottom_bar(self):
        bar = tk.Frame(self, bg=C_BG2)
        bar.pack(fill=tk.X, padx=8, pady=(4, 6))

        inner = tk.Frame(bar, bg=C_BG2)
        inner.pack(fill=tk.BOTH, padx=6, pady=4)

        ttk.Label(inner, text="Time Sync:",
                  background=C_BG2).pack(side=tk.LEFT, padx=(0, 4))
        self._sync_btn = ttk.Button(inner, text="Send PC Time to Watch",
                                    command=self._safe_send_time_sync)
        self._sync_btn.pack(side=tk.LEFT, padx=(0, 8))
        self._sync_lbl = ttk.Label(inner, text="", background=C_BG2,
                                   font=("Consolas", 9))
        self._sync_lbl.pack(side=tk.LEFT)

        # log file path hint
        ttk.Label(inner, text=f"Log: {LOG_FILE.name}",
                  background=C_BG2, font=("", 7), foreground=C_GRAY).pack(side=tk.RIGHT)

        self._status_var = tk.StringVar(value="Ready")
        ttk.Label(inner, textvariable=self._status_var,
                  background=C_BG2, font=("", 8), foreground=C_GRAY).pack(side=tk.RIGHT, padx=(0, 10))

    # ╔═══════════════════════════════════════════════════╗
    # ║         SAFETY WRAPPERS (never crash UI)          ║
    # ╚═══════════════════════════════════════════════════╝

    def _safe_refresh_ports(self):
        try:
            self._refresh_ports()
        except Exception:
            log.error(f"refresh_ports crashed:\n{traceback.format_exc()}")
            self._status("Port scan failed — see log")

    def _safe_toggle_connect(self):
        try:
            self._toggle_connect()
        except Exception:
            log.error(f"toggle_connect crashed:\n{traceback.format_exc()}")
            self._status("Connection error — see log")
            self._safe_disconnect()

    def _safe_send_time_sync(self):
        try:
            self._send_time_sync()
        except Exception:
            log.error(f"send_time_sync crashed:\n{traceback.format_exc()}")
            self._status("Time sync error — see log")
            self._sync_lbl.config(text="Error — see log", foreground=C_RED)

    def _safe_disconnect(self):
        try:
            self._disconnect()
        except Exception:
            log.error(f"disconnect crashed:\n{traceback.format_exc()}")
            self._ser = None
            self._running = False

    # ╔═══════════════════════════════════════════════════╗
    # ║                  SERIAL CONTROL                   ║
    # ╚═══════════════════════════════════════════════════╝

    def _refresh_ports(self):
        log.debug("Scanning COM ports...")
        all_ports = list(serial.tools.list_ports.comports())
        entries = [f"{p.device}  —  {p.description}" for p in all_ports]
        self._port_cb["values"] = entries
        self._port_map = {e: p.device for e, p in zip(entries, all_ports)}

        if entries:
            bt_entries = [e for e in entries if "bluetooth" in e.lower()]
            self._port_var.set(bt_entries[0] if bt_entries else entries[0])
            log.info(f"Found {len(entries)} COM port(s): {[p.device for p in all_ports]}")
        else:
            self._port_var.set("")
            log.warning("No COM ports found")

    def _toggle_connect(self):
        if self._ser and self._ser.is_open:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        entry = self._port_var.get()
        if not entry:
            self._status("No COM port selected")
            log.warning("Connect attempted but no COM port selected")
            return

        port = self._port_map.get(entry, entry.split("  —  ")[0].strip())
        log.info(f"Connecting to {port} @ {BAUDRATE} baud...")

        try:
            self._ser = serial.Serial(port, BAUDRATE, timeout=SERIAL_TIMEOUT)
        except serial.SerialException as e:
            log.error(f"Serial open failed for {port}: {e}")
            self._status(f"Open {port} failed — see log")
            return
        except Exception as e:
            log.error(f"Unexpected error opening {port}:\n{traceback.format_exc()}")
            self._status(f"Open {port} failed — see log")
            return

        self._running = True
        self._frame_count = 0
        self._parser = FrameParser()
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

        self._port_cb.config(state="disabled")
        self._conn_btn.config(text="Disconnect", style="TButton")
        self._draw_dot(C_GREEN)
        self._conn_lbl.config(text="Connected", foreground=C_GREEN)
        self._status(f"Connected {port} @ {BAUDRATE} baud")
        log.info(f"Connected to {port}, read thread started")

    def _disconnect(self):
        log.info("Disconnecting...")
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            if self._thread.is_alive():
                log.warning("Read thread did not exit within 1s")
            self._thread = None

        if self._ser:
            try:
                self._ser.close()
                log.info("Serial port closed")
            except Exception as e:
                log.error(f"Error closing serial port: {e}")
            self._ser = None

        # reset UI safely
        try:
            self._port_cb.config(state="readonly")
            self._conn_btn.config(text="Connect", style="Accent.TButton")
        except Exception:
            pass
        self._draw_dot(C_GRAY)
        self._conn_lbl.config(text="Disconnected", foreground=C_GRAY)
        self._status("Disconnected")

    # ╔═══════════════════════════════════════════════════╗
    # ║                 BACKGROUND THREAD                 ║
    # ╚═══════════════════════════════════════════════════╝

    def _read_loop(self):
        log.info("Read loop started")
        err_count = 0
        while self._running and self._ser and self._ser.is_open:
            try:
                n = self._ser.in_waiting
                if n > 0:
                    chunk = self._ser.read(n)
                    frames = self._parser.feed(chunk)
                    for cmd, data in frames:
                        self._frame_count += 1
                        if cmd == BT_CMD_SENSOR_DATA:
                            try:
                                s = parse_sensor_data(data)
                                with self._sensor_lock:
                                    self._latest_sensor = s
                                for k in ("ax", "ay", "az"):
                                    self._acc_hist[k].append(s[k])
                                for k in ("gx", "gy", "gz"):
                                    self._gyr_hist[k].append(s[k])
                            except (ValueError, struct.error) as e:
                                log.debug(f"Bad sensor frame (len={len(data)}): {e}")
                            except Exception:
                                log.error(f"Unexpected frame error:\n{traceback.format_exc()}")
                    err_count = 0  # reset on success
                else:
                    time.sleep(0.01)
            except serial.SerialException as e:
                err_count += 1
                log.error(f"Serial error in read loop (count={err_count}): {e}")
                if err_count >= 3:
                    log.critical("Too many serial errors, exiting read loop")
                    break
                time.sleep(0.1)
            except OSError as e:
                err_count += 1
                log.error(f"OS error in read loop (count={err_count}): {e}")
                if err_count >= 3:
                    break
                time.sleep(0.1)
            except Exception:
                log.critical(f"Fatal error in read loop:\n{traceback.format_exc()}")
                break

        log.info(f"Read loop exited (frame_count={self._frame_count})")
        self.after(0, self._safe_on_serial_error)

    # ╔═══════════════════════════════════════════════════╗
    # ║                  UI UPDATE LOOP                   ║
    # ╚═══════════════════════════════════════════════════╝

    def _schedule_poll(self):
        self._poll_id = self.after(POLL_MS, self._poll)

    def _poll(self):
        try:
            self._do_poll()
        except Exception:
            log.error(f"Poll crashed:\n{traceback.format_exc()}")
        finally:
            # always reschedule, even on error
            self._poll_id = self.after(POLL_MS, self._poll)

    def _do_poll(self):
        self._frame_lbl.config(text=f"Frames: {self._frame_count}")

        with self._sensor_lock:
            s = dict(self._latest_sensor) if self._latest_sensor else None

        if s:
            for k in ("ax", "ay", "az", "gx", "gy", "gz"):
                try:
                    self._val_labels[k].config(text=f"{s[k]:.2f}", fg=LINE_COLORS[k])
                except Exception:
                    pass

            # compute attitude (guard against NaN / division by zero)
            try:
                denom_p = math.sqrt(max(s["ay"]**2 + s["az"]**2, 1e-9))
                pitch = math.atan2(s["ax"], denom_p) * 180.0 / math.pi
                denom_r = math.sqrt(max(s["ax"]**2 + s["az"]**2, 1e-9))
                roll  = math.atan2(s["ay"], denom_r) * 180.0 / math.pi
                self._val_labels["pitch"].config(text=f"{pitch:.1f}°")
                self._val_labels["roll"].config(text=f"{roll:.1f}°")
            except Exception:
                pass

        # redraw charts safely
        try:
            self._redraw_chart(self._ax_acc, self._acc_lines, self._acc_hist)
            self._redraw_chart(self._ax_gyr, self._gyr_lines, self._gyr_hist)
            self._canvas.draw_idle()
        except Exception:
            pass  # chart redraw failure is not fatal

    def _redraw_chart(self, ax, lines, hist):
        for lbl, line in lines.items():
            d = hist[lbl]
            try:
                if d:
                    line.set_data(range(len(d)), list(d))
                else:
                    line.set_data([], [])
            except Exception:
                pass

    # ╔═══════════════════════════════════════════════════╗
    # ║                    TIME SYNC                      ║
    # ╚═══════════════════════════════════════════════════╝

    def _send_time_sync(self):
        if not self._ser:
            self._status("Not connected — no serial port")
            log.warning("Time sync: not connected")
            return
        if not self._ser.is_open:
            self._status("Serial port closed")
            log.warning("Time sync: serial port not open")
            return

        now = datetime.now()
        try:
            frame = build_time_sync_cmd(
                hour=now.hour, minute=now.minute, second=now.second,
                year=now.year, month=now.month, day=now.day,
            )
        except Exception:
            log.error(f"Time sync frame build failed:\n{traceback.format_exc()}")
            self._sync_lbl.config(text="Frame error — see log", foreground=C_RED)
            return

        try:
            n = self._ser.write(frame)
            ts = now.strftime("%Y-%m-%d %H:%M:%S")
            self._sync_lbl.config(text=f"Sent: {ts}", foreground=C_GREEN)
            self._status(f"Time sync sent {n}B: {ts}")
            log.info(f"Time sync sent {n} bytes: {ts}")
        except serial.SerialException as e:
            log.error(f"Time sync write failed: {e}")
            self._sync_lbl.config(text=f"Write error — see log", foreground=C_RED)
            self._status("Time sync write failed")
        except Exception:
            log.error(f"Time sync unexpected error:\n{traceback.format_exc()}")
            self._sync_lbl.config(text="Error — see log", foreground=C_RED)
            self._status("Time sync failed")

    # ╔═══════════════════════════════════════════════════╗
    # ║                    HELPERS                        ║
    # ╚═══════════════════════════════════════════════════╝

    def _safe_on_serial_error(self):
        try:
            self._on_serial_error()
        except Exception:
            log.error(f"serial_error handler crashed:\n{traceback.format_exc()}")
            self._status("Serial error — see log")

    def _on_serial_error(self):
        log.warning("Serial error handler triggered, disconnecting")
        self._status("Serial error — disconnected")
        self._safe_disconnect()

    def _status(self, msg: str):
        self._status_var.set(msg)

    def _on_close(self):
        log.info("Window close requested, shutting down")
        self._safe_disconnect()
        try:
            self.destroy()
        except Exception:
            pass
        log.info("Application exited normally")


# ── Entry Point ──────────────────────────────────────────────
if __name__ == "__main__":
    app = SmartWatchHost()
    app.mainloop()
