#!/usr/bin/python3
import json
import logging
import os
import re
import tkinter as tk

import config
import TFT_3_5inch

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "colors_config.json")
SWATCH_SIZE = 48
HEX_RE = re.compile(r'^#?([0-9a-fA-F]{6})$')

logging.basicConfig(level=logging.INFO)


class TFTColorControl(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TFT Color Control")
        self.resizable(False, False)

        self.disp = TFT_3_5inch.TFT_3_5inch()
        self.disp.Init()
        self.disp.set_benchmark(False)

        self.config_data = self._load_config()
        self._current_hex = self.config_data["predefined"][0]["hex"]
        self._current_name = self.config_data["predefined"][0]["name"]

        self._brightness = self.config_data.get("brightness", 80)
        config.pwm_init(self._brightness)

        self._build_gui()
        self.disp.FillColor(self._current_hex)
        self._update_current_display()
        self._brightness_slider.set(self._brightness)

        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    # ------------------------------------------------------------------ config
    def _load_config(self):
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logging.warning("Config unreadable, using defaults: %s", e)
            return {
                "brightness": 80,
                "predefined": [
                    {"name": "Blue 1", "hex": "0062ac"},
                    {"name": "Blue 2", "hex": "17388c"},
                    {"name": "Blue 3", "hex": "0083c9"},
                    {"name": "Blue 4", "hex": "0079ba"},
                    {"name": "Blue 5", "hex": "0063ac"},
                    {"name": "Blue 6", "hex": "006bb5"},
                    {"name": "Blue 7", "hex": "00599f"},
                ],
                "custom": [],
            }

    def _save_config(self):
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump(self.config_data, f, indent=2)
        except OSError as e:
            logging.error("Failed to write config: %s", e)

    # ------------------------------------------------------------------ apply
    def apply_color(self, hex_color, name=""):
        self._current_hex = hex_color
        self._current_name = name or f"#{hex_color}"
        self.disp.FillColor(hex_color)
        self._update_current_display()

    # ------------------------------------------------------------------ custom
    def _on_hex_keyrelease(self, event=None):
        raw = self._hex_var.get().strip()
        m = HEX_RE.match(raw)
        if m:
            hex6 = m.group(1)
            self._preview_canvas.configure(bg=f"#{hex6}")
            self._apply_btn.configure(state=tk.NORMAL)
        else:
            self._preview_canvas.configure(bg="lightgray")
            self._apply_btn.configure(state=tk.DISABLED)

    def _save_custom_color(self):
        raw = self._hex_var.get().strip()
        m = HEX_RE.match(raw)
        if not m:
            return
        hex6 = m.group(1)
        new_entry = {"name": f"Custom #{hex6}", "hex": hex6}
        if new_entry not in self.config_data["custom"]:
            self.config_data["custom"].append(new_entry)
            self._save_config()
            self._rebuild_custom_list()
        self.apply_color(hex6, new_entry["name"])

    # ------------------------------------------------------------------ brightness
    def _on_brightness_change(self, val):
        pct = int(float(val))
        self._brightness = pct
        self._brightness_label.configure(text=f"{pct}%")
        config.pwm_set_brightness(pct)
        self.config_data["brightness"] = pct
        self._save_config()

    def _build_brightness_section(self):
        sec = tk.LabelFrame(self, text="Brightness", padx=6, pady=6)
        sec.pack(fill=tk.X, padx=8, pady=(4, 0))

        inner = tk.Frame(sec)
        inner.pack(fill=tk.X)

        tk.Label(inner, text="  0%").pack(side=tk.LEFT)
        self._brightness_slider = tk.Scale(inner, from_=0, to=100,
                                           orient=tk.HORIZONTAL,
                                           command=self._on_brightness_change,
                                           showvalue=False, length=200)
        self._brightness_slider.pack(side=tk.LEFT, padx=4, fill=tk.X, expand=True)
        self._brightness_label = tk.Label(inner, text="100%", width=4,
                                          font=("TkFixedFont", 10))
        self._brightness_label.pack(side=tk.LEFT)

    # ------------------------------------------------------------------ gui
    def _build_gui(self):
        self._build_brightness_section()
        self._build_predefined_section()
        self._build_custom_section()
        self._build_custom_list_section()
        self._build_current_section()

    def _make_color_button(self, parent, hex_color, name):
        frame = tk.Frame(parent, relief=tk.RAISED, bd=1)
        cvs = tk.Canvas(frame, width=SWATCH_SIZE, height=SWATCH_SIZE,
                        bg=f"#{hex_color}", highlightthickness=0, cursor="hand2")
        cvs.pack(padx=2, pady=(2, 0))
        cvs.bind("<Button-1>", lambda e, h=hex_color, n=name: self.apply_color(h, n))
        lbl = tk.Label(frame, text=hex_color, font=("TkFixedFont", 9), cursor="hand2")
        lbl.pack()
        lbl.bind("<Button-1>", lambda e, h=hex_color, n=name: self.apply_color(h, n))
        frame.pack(side=tk.LEFT, padx=4, pady=4)
        return frame

    def _build_predefined_section(self):
        sec = tk.LabelFrame(self, text="Predefined Colors", padx=6, pady=6)
        sec.pack(fill=tk.X, padx=8, pady=(8, 0))
        row_frame = tk.Frame(sec)
        row_frame.pack()
        for i, col in enumerate(self.config_data["predefined"]):
            if i > 0 and i % 4 == 0:
                row_frame = tk.Frame(sec)
                row_frame.pack()
            self._make_color_button(row_frame, col["hex"], col["name"])

    def _build_custom_section(self):
        sec = tk.LabelFrame(self, text="Custom Color", padx=6, pady=6)
        sec.pack(fill=tk.X, padx=8, pady=(4, 0))

        top = tk.Frame(sec)
        top.pack(fill=tk.X)

        tk.Label(top, text="Hex:").pack(side=tk.LEFT)
        self._hex_var = tk.StringVar()
        entry = tk.Entry(top, textvariable=self._hex_var, width=10, font=("TkFixedFont", 11))
        entry.pack(side=tk.LEFT, padx=(4, 8))
        entry.bind("<KeyRelease>", self._on_hex_keyrelease)
        entry.bind("<Return>", lambda e: self._save_custom_color())

        self._preview_canvas = tk.Canvas(top, width=SWATCH_SIZE, height=SWATCH_SIZE,
                                         bg="lightgray", highlightthickness=1,
                                         highlightbackground="#aaa")
        self._preview_canvas.pack(side=tk.LEFT)

        self._apply_btn = tk.Button(sec, text="Save as custom color",
                                    command=self._save_custom_color,
                                    state=tk.DISABLED)
        self._apply_btn.pack(pady=(6, 0))

    def _rebuild_custom_list(self):
        for w in self._custom_list_frame.winfo_children():
            w.destroy()
        self._populate_custom_list()

    def _populate_custom_list(self):
        custom = self.config_data.get("custom", [])
        if not custom:
            lbl = tk.Label(self._custom_list_frame, text="(none yet)",
                           fg="gray", font=("TkDefaultFont", 9))
            lbl.pack()
            return
        row_frame = tk.Frame(self._custom_list_frame)
        row_frame.pack()
        for i, col in enumerate(custom):
            if i > 0 and i % 4 == 0:
                row_frame = tk.Frame(self._custom_list_frame)
                row_frame.pack()
            self._make_color_button(row_frame, col["hex"], col["name"])

    def _build_custom_list_section(self):
        sec = tk.LabelFrame(self, text="Saved Custom Colors", padx=6, pady=6)
        sec.pack(fill=tk.X, padx=8, pady=(4, 0))
        self._custom_list_frame = tk.Frame(sec)
        self._custom_list_frame.pack()
        self._populate_custom_list()

    def _update_current_display(self):
        self._current_canvas.configure(bg=f"#{self._current_hex}")
        name_part = f" ({self._current_name})" if self._current_name else ""
        self._current_label.configure(text=f"#{self._current_hex}{name_part}")

    def _build_current_section(self):
        sec = tk.Frame(self, relief=tk.SUNKEN, bd=1, padx=8, pady=6)
        sec.pack(fill=tk.X, padx=8, pady=(8, 8))

        tk.Label(sec, text="Current Display Color:", font=("TkDefaultFont", 10, "bold")
                 ).pack(side=tk.LEFT)

        self._current_canvas = tk.Canvas(sec, width=SWATCH_SIZE, height=SWATCH_SIZE,
                                         bg=f"#{self._current_hex}", highlightthickness=1,
                                         highlightbackground="#555")
        self._current_canvas.pack(side=tk.LEFT, padx=(8, 4))

        self._current_label = tk.Label(sec, font=("TkFixedFont", 10))
        self._current_label.pack(side=tk.LEFT)

    # ------------------------------------------------------------------ close
    def _on_closing(self):
        config.module_exit()
        self.destroy()


if __name__ == "__main__":
    app = TFTColorControl()
    app.mainloop()
