import tkinter as tk
from tkinter import ttk
from collections import deque
import threading
import time
import bisect

import serial
import serial.tools.list_ports
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class App:
    MAX_POINTS = 200_000

    def __init__(self, root):
        self.root = root
        self.root.title("STM32 Temperature Monitor  (press Q to quit)")
        self.root.geometry("880x520")
        self.root.protocol("WM_DELETE_WINDOW", self._quit)

        self.ser = None
        self.running = False

        self.t0 = 0.0
        self.times = deque(maxlen=self.MAX_POINTS)
        self.temps = deque(maxlen=self.MAX_POINTS)

        self._build_controls()
        self._build_plot()

        self.root.bind("q", lambda e: self._quit())
        self.root.bind("<Escape>", lambda e: self._quit())

    # ---- UI ----------------------------------------------------------------
    def _build_controls(self):
        bar = ttk.Frame(self.root)
        bar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        ttk.Label(bar, text="COM:").pack(side=tk.LEFT)
        self.port_var = tk.StringVar()
        self.cb = ttk.Combobox(bar, textvariable=self.port_var, width=10, state="readonly")
        self.cb.pack(side=tk.LEFT, padx=3)
        ttk.Button(bar, text="Refresh", command=self._refresh).pack(side=tk.LEFT, padx=2)

        self.btn = ttk.Button(bar, text="Start", command=self._toggle)
        self.btn.pack(side=tk.LEFT, padx=2)

        ttk.Label(bar, text="  Time:").pack(side=tk.LEFT)
        self.range_var = tk.StringVar(value="30")
        vcmd = (bar.register(self._validate_range), "%P")
        self.range_entry = ttk.Entry(
            bar, textvariable=self.range_var, width=8, validate="key",
            validatecommand=vcmd)
        self.range_entry.pack(side=tk.LEFT, padx=2)
        ttk.Label(bar, text="s  (0.001 ~ 60)").pack(side=tk.LEFT)

        self.lbl = ttk.Label(bar, text="Stopped", foreground="red")
        self.lbl.pack(side=tk.LEFT, padx=12)
        self.val_label = ttk.Label(bar, text="--.-- C")
        self.val_label.pack(side=tk.RIGHT, padx=6)

        self._refresh()

    def _build_plot(self):
        self.fig, self.ax = plt.subplots(figsize=(8.6, 4.2))
        self.ax.set_title("Temperature")
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Temperature (C)")
        self.ax.set_ylim(15, 70)
        self.ax.grid(True, linestyle="--", alpha=0.4)

        (self.line,) = self.ax.plot([], [], "r-", linewidth=1.2)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _validate_range(self, v):
        return v == "" or v == "." or v.replace(".", "", 1).isdigit()

    def _window_sec(self):
        try:
            return max(0.001, min(60.0, float(self.range_var.get())))
        except ValueError:
            return 30.0

    # ---- Window close ------------------------------------------------------
    def _quit(self):
        self.running = False
        self.root.destroy()

    # ---- Port / control ----------------------------------------------------
    def _refresh(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.cb["values"] = ports
        if ports:
            self.port_var.set(ports[0])

    def _toggle(self):
        if self.running:
            self._stop()
        else:
            self._start()

    def _start(self):
        port = self.port_var.get()
        if not port:
            return
        try:
            self.ser = serial.Serial(port, 115200, timeout=1)
        except Exception as e:
            self.lbl.config(text=str(e))
            return

        self.running = True
        self.t0 = time.time()
        self.times.clear()
        self.temps.clear()

        self.btn.config(text="Stop")
        self.lbl.config(text="Running", foreground="green")

        th = threading.Thread(target=self._reader, daemon=True)
        th.start()
        self._anim()

    def _stop(self):
        self.running = False
        self.btn.config(text="Start")
        self.lbl.config(text="Stopped", foreground="red")
        self.val_label.config(text="--.-- C")

    # ---- Serial reader (background thread) ----------------------------------
    def _reader(self):
        while self.running:
            try:
                if not self.ser or not self.ser.is_open:
                    break
                raw = self.ser.readline()
            except (serial.SerialException, TypeError):
                break

            if not raw:
                continue

            try:
                adc = int(raw.decode().strip())
            except (ValueError, UnicodeDecodeError):
                continue

            mv = adc * 3300 / 4095
            temp = (1430 - mv) / 4.3 + 25

            self.times.append(time.time() - self.t0)
            self.temps.append(temp)

        if self.ser and self.ser.is_open:
            self.ser.close()

    # ---- Animation loop (main thread) --------------------------------------
    def _anim(self):
        if not self.running:
            return

        t = self.times
        y = self.temps
        if t:
            w = self._window_sec()
            now = t[-1]
            lo = now - w

            xs = list(t)
            ys = list(y)
            n = min(len(xs), len(ys))
            xs, ys = xs[:n], ys[:n]
            i = bisect.bisect_left(xs, lo)

            self.line.set_data(xs[i:], ys[i:])
            self.ax.set_xlim(lo, now if now > lo else lo + w)
            self.val_label.config(text=f"{y[-1]:.2f} C")

        self.canvas.draw_idle()
        self.root.after(100, self._anim)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
