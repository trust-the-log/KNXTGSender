import asyncio
import sys
import os
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk
from datetime import datetime

from xknx import XKNX
from xknx.io import ConnectionConfig, ConnectionType
from xknx.dpt import (
    DPTArray, DPTBinary,
    # 1.x
    DPTSwitch, DPTBool, DPTEnable, DPTUpDown, DPTOpenClose, DPTStart,
    # 3.x
    DPTControlDimming, DPTControlBlinds,
    # 5.x
    DPTScaling, DPTValue1Ucount,
    # 6.x
    DPTPercentV8, DPTValue1Count,
    # 7.x
    DPT2ByteUnsigned,
    # 8.x
    DPT2ByteSigned, DPTRotationAngle,
    # 9.x
    DPT2ByteFloat, DPTTemperature, DPTTemperatureDifference2Byte,
    DPTLux, DPTHumidity, DPTWsp, DPTPressure2Byte,
    DPTVoltage, DPTCurrent,
    # 10/11
    DPTDate, DPTTime,
    # 12.x
    DPT4ByteUnsigned,
    # 13.x
    DPT4ByteSigned, DPTActiveEnergy, DPTActiveEnergykWh,
    # 14.x
    DPT4ByteFloat,
    # 16.x
    DPTString, DPTLatin1,
    # 17/18
    DPTSceneNumber, DPTSceneControl, SceneControl,
    # 19
    DPTDateTime,
    # 20
    DPTHVACMode,
)
from xknx.dpt.dpt_10 import KNXTime
from xknx.dpt.dpt_11 import KNXDate
from xknx.dpt.dpt_19 import KNXDateTime
from xknx.dpt.dpt_20 import HVACOperationMode
from xknx.dpt.dpt_3 import ControlDimming, ControlBlinds
from xknx.dpt.dpt_1 import Step, UpDown
from xknx.telegram import Telegram, GroupAddress
from xknx.telegram.apci import GroupValueWrite

# ── palette ─────────────────────────────────────────────────────────────────
BG       = "#0f1117"
PANEL    = "#1a1d27"
ACCENT   = "#3DCD58"
ACCENT2  = "#2aa648"
TEXT     = "#e8eaf0"
TEXT_DIM = "#6b7280"
BORDER   = "#2d3148"
ERR      = "#f87171"
WARN     = "#fbbf24"
INFO     = "#60a5fa"

# ── DPT encoders ─────────────────────────────────────────────────────────────

# --- 1.x boolean helpers ---
def _bool_val(v):
    return 1 if v.strip().lower() in ("1", "true", "on", "yes") else 0

def _enc_switch(v):    return DPTBinary(_bool_val(v))   # 1.001
def _enc_bool(v):      return DPTBinary(_bool_val(v))   # 1.002
def _enc_enable(v):    return DPTBinary(_bool_val(v))   # 1.003
def _enc_updown(v):    return DPTBinary(_bool_val(v))   # 1.008  0=Up 1=Down
def _enc_openclose(v): return DPTBinary(_bool_val(v))   # 1.009  0=Open 1=Close
def _enc_start(v):     return DPTBinary(_bool_val(v))   # 1.010  0=Stop 1=Start

# --- 3.x ---
def _enc_dimming(v):
    # "direction step_code"  e.g.  "increase 3"  /  "stop"
    parts = v.strip().lower().split()
    if parts[0] in ("stop", "0"):
        direction, step = Step.DECREASE, 0
    else:
        direction = Step.INCREASE if parts[0] in ("increase", "up", "1") else Step.DECREASE
        step = int(parts[1]) if len(parts) > 1 else 5
    return DPTControlDimming.to_knx(ControlDimming(control=direction, step_code=step))

def _enc_blinds(v):
    # "direction step_code"  e.g.  "down 3"  /  "stop"
    parts = v.strip().lower().split()
    if parts[0] in ("stop", "0"):
        direction, step = UpDown.DOWN, 0
    else:
        direction = UpDown.DOWN if parts[0] in ("down", "close", "1") else UpDown.UP
        step = int(parts[1]) if len(parts) > 1 else 5
    return DPTControlBlinds.to_knx(ControlBlinds(control=direction, step_code=step))

# --- 5.x ---
def _enc_scaling(v):   return DPTArray(DPTScaling.to_knx(float(v)))
def _enc_1byte_u(v):   return DPTArray(DPTValue1Ucount.to_knx(int(v)))

# --- 6.x ---
def _enc_percentV8(v): return DPTArray(DPTPercentV8.to_knx(int(v)))
def _enc_counter(v):   return DPTArray(DPTValue1Count.to_knx(int(v)))

# --- 7.x ---
def _enc_2byte_u(v):   return DPTArray(DPT2ByteUnsigned.to_knx(int(v)))

# --- 8.x ---
def _enc_2byte_s(v):   return DPTArray(DPT2ByteSigned.to_knx(int(v)))
def _enc_rot_angle(v): return DPTArray(DPTRotationAngle.to_knx(int(v)))

# --- 9.x ---
def _enc_temperature(v):    return DPTArray(DPTTemperature.to_knx(float(v)))
def _enc_temp_diff(v):      return DPTArray(DPTTemperatureDifference2Byte.to_knx(float(v)))
def _enc_lux(v):            return DPTArray(DPTLux.to_knx(float(v)))
def _enc_humidity(v):       return DPTArray(DPTHumidity.to_knx(float(v)))
def _enc_wind(v):           return DPTArray(DPTWsp.to_knx(float(v)))
def _enc_pressure(v):       return DPTArray(DPTPressure2Byte.to_knx(float(v)))
def _enc_voltage(v):        return DPTArray(DPTVoltage.to_knx(float(v)))
def _enc_current(v):        return DPTArray(DPTCurrent.to_knx(float(v)))
def _enc_2byte_f(v):        return DPTArray(DPT2ByteFloat.to_knx(float(v)))

# --- 10/11 ---
def _enc_time(v):
    parts = [int(x) for x in v.strip().split(":")]
    h, m, s = parts[0], parts[1], parts[2] if len(parts) > 2 else 0
    return DPTArray(DPTTime.to_knx(KNXTime(hour=h, minutes=m, seconds=s)))

def _enc_date(v):
    v = v.strip()
    if "/" in v:
        d, mo, y = [int(x) for x in v.split("/")]
    else:
        y, mo, d = [int(x) for x in v.split("-")]
    return DPTArray(DPTDate.to_knx(KNXDate(year=y, month=mo, day=d)))

# --- 12.x ---
def _enc_4byte_u(v):  return DPTArray(DPT4ByteUnsigned.to_knx(int(v)))

# --- 13.x ---
def _enc_4byte_s(v):  return DPTArray(DPT4ByteSigned.to_knx(int(v)))
def _enc_energy_wh(v):  return DPTArray(DPTActiveEnergy.to_knx(int(v)))
def _enc_energy_kwh(v): return DPTArray(DPTActiveEnergykWh.to_knx(int(v)))

# --- 14.x ---
def _enc_4byte_f(v):  return DPTArray(DPT4ByteFloat.to_knx(float(v)))

# --- 16.x ---
def _enc_str_ascii(v):  return DPTArray(DPTString.to_knx(v[:14]))
def _enc_str_latin(v):  return DPTArray(DPTLatin1.to_knx(v[:14]))

# --- 17/18 ---
def _enc_scene_nr(v):
    return DPTSceneNumber.to_knx(int(v))

def _enc_scene_ctrl(v):
    # "activate 5"  /  "learn 5"
    parts = v.strip().lower().split()
    learn  = parts[0] == "learn"
    number = int(parts[1]) if len(parts) > 1 else int(parts[0])
    return DPTSceneControl.to_knx(SceneControl(scene_number=number, learn=learn))

# --- 19 ---
def _enc_datetime(v):
    # "DD/MM/YYYY HH:MM:SS"
    parts = v.strip().split()
    date_s = parts[0]
    time_s = parts[1] if len(parts) > 1 else "00:00:00"
    if "/" in date_s:
        d, mo, y = [int(x) for x in date_s.split("/")]
    else:
        y, mo, d = [int(x) for x in date_s.split("-")]
    h, m, s = [int(x) for x in time_s.split(":")]
    return DPTDateTime.to_knx(KNXDateTime(year=y, month=mo, day=d, hour=h, minutes=m, seconds=s))

# --- 20 ---
_HVAC_MAP = {
    "auto": HVACOperationMode.AUTO,
    "comfort": HVACOperationMode.COMFORT,
    "standby": HVACOperationMode.STANDBY,
    "economy": HVACOperationMode.ECONOMY,
    "protection": HVACOperationMode.BUILDING_PROTECTION,
    "0": HVACOperationMode.AUTO,
    "1": HVACOperationMode.COMFORT,
    "2": HVACOperationMode.STANDBY,
    "3": HVACOperationMode.ECONOMY,
    "4": HVACOperationMode.BUILDING_PROTECTION,
}
def _enc_hvac(v):
    mode = _HVAC_MAP.get(v.strip().lower())
    if mode is None:
        raise ValueError(f"Unknown HVAC mode '{v}'. Use: auto/comfort/standby/economy/protection")
    return DPTHVACMode.to_knx(mode)

# --- raw ---
def _enc_raw(v):
    return DPTArray(bytes.fromhex(v.replace(" ", "")))


# ── option list with section separators ─────────────────────────────────────
# Separator entries have encoder=None and are shown greyed-out / non-selectable
SEP = None

DPT_OPTIONS = [
    # label                                   encoder
    ("── DPT 1.x  Binary ──",                SEP),
    ("1.001  Switch  (0=off / 1=on)",         _enc_switch),
    ("1.002  Boolean  (0=false / 1=true)",    _enc_bool),
    ("1.003  Enable  (0=disable / 1=enable)", _enc_enable),
    ("1.008  Up/Down  (0=up / 1=down)",       _enc_updown),
    ("1.009  Open/Close  (0=open / 1=close)", _enc_openclose),
    ("1.010  Start/Stop  (0=stop / 1=start)", _enc_start),

    ("── DPT 3.x  4-bit Control ──",         SEP),
    ("3.007  Dimming  (increase/decrease N)", _enc_dimming),
    ("3.008  Blinds  (up/down N)",            _enc_blinds),

    ("── DPT 5.x  1-Byte Unsigned ──",       SEP),
    ("5.001  Scaling  0–100 %",              _enc_scaling),
    ("5.010  1-Byte unsigned  0–255",        _enc_1byte_u),

    ("── DPT 6.x  1-Byte Signed ──",         SEP),
    ("6.001  Percent V8  -128…127",          _enc_percentV8),
    ("6.010  Counter pulses  -128…127",      _enc_counter),

    ("── DPT 7.x  2-Byte Unsigned ──",       SEP),
    ("7.001  2-Byte unsigned  0–65535",      _enc_2byte_u),

    ("── DPT 8.x  2-Byte Signed ──",         SEP),
    ("8.001  2-Byte signed  -32768…32767",   _enc_2byte_s),
    ("8.011  Rotation angle  °",             _enc_rot_angle),

    ("── DPT 9.x  2-Byte Float ──",          SEP),
    ("9.001  Temperature  °C",               _enc_temperature),
    ("9.002  Temperature difference  °C",    _enc_temp_diff),
    ("9.004  Illuminance  lx",               _enc_lux),
    ("9.007  Humidity  %",                   _enc_humidity),
    ("9.005  Wind speed  m/s",               _enc_wind),
    ("9.006  Pressure  Pa",                  _enc_pressure),
    ("9.020  Voltage  mV",                   _enc_voltage),
    ("9.021  Current  mA",                   _enc_current),
    ("9.xxx  2-Byte float  (generic)",       _enc_2byte_f),

    ("── DPT 10/11  Time & Date ──",         SEP),
    ("10.001  Time  HH:MM:SS",               _enc_time),
    ("11.001  Date  DD/MM/YYYY",             _enc_date),

    ("── DPT 12.x  4-Byte Unsigned ──",      SEP),
    ("12.001  4-Byte unsigned  0–4294967295",_enc_4byte_u),

    ("── DPT 13.x  4-Byte Signed ──",        SEP),
    ("13.001  4-Byte signed",                _enc_4byte_s),
    ("13.010  Active energy  Wh",            _enc_energy_wh),
    ("13.013  Active energy  kWh",           _enc_energy_kwh),

    ("── DPT 14.x  4-Byte Float ──",         SEP),
    ("14.xxx  4-Byte float  (generic)",      _enc_4byte_f),

    ("── DPT 16.x  String ──",               SEP),
    ("16.000  ASCII string  (max 14 chars)", _enc_str_ascii),
    ("16.001  Latin-1 string (max 14 chars)",_enc_str_latin),

    ("── DPT 17/18  Scene ──",               SEP),
    ("17.001  Scene number  1–64",           _enc_scene_nr),
    ("18.001  Scene control  (activate/learn N)", _enc_scene_ctrl),

    ("── DPT 19  DateTime ──",               SEP),
    ("19.001  DateTime  DD/MM/YYYY HH:MM:SS",_enc_datetime),

    ("── DPT 20  HVAC ──",                   SEP),
    ("20.102  HVAC mode",                    _enc_hvac),

    ("── Raw ──",                             SEP),
    ("Raw hex  e.g.  FF 0A 3B",              _enc_raw),
]

HINT = {
    "1.001  Switch  (0=off / 1=on)":              "0  /  1  /  true  /  false",
    "1.002  Boolean  (0=false / 1=true)":         "0  /  1",
    "1.003  Enable  (0=disable / 1=enable)":      "0  /  1",
    "1.008  Up/Down  (0=up / 1=down)":            "0  /  1",
    "1.009  Open/Close  (0=open / 1=close)":      "0  /  1",
    "1.010  Start/Stop  (0=stop / 1=start)":      "0  /  1",
    "3.007  Dimming  (increase/decrease N)":       "increase 5  /  decrease 3  /  stop",
    "3.008  Blinds  (up/down N)":                  "up 5  /  down 3  /  stop",
    "5.001  Scaling  0–100 %":                    "75",
    "5.010  1-Byte unsigned  0–255":              "200",
    "6.001  Percent V8  -128…127":               "-50  /  100",
    "6.010  Counter pulses  -128…127":           "-1  /  10",
    "7.001  2-Byte unsigned  0–65535":            "1000",
    "8.001  2-Byte signed  -32768…32767":        "-500  /  1000",
    "8.011  Rotation angle  °":                   "-180  /  90",
    "9.001  Temperature  °C":                     "21.5",
    "9.002  Temperature difference  °C":          "-2.5  /  3.0",
    "9.004  Illuminance  lx":                     "500.0",
    "9.007  Humidity  %":                         "55.0",
    "9.005  Wind speed  m/s":                     "3.5",
    "9.006  Pressure  Pa":                        "101325.0",
    "9.020  Voltage  mV":                         "230.0",
    "9.021  Current  mA":                         "16.0",
    "9.xxx  2-Byte float  (generic)":             "-3.14",
    "10.001  Time  HH:MM:SS":                     "14:30:00",
    "11.001  Date  DD/MM/YYYY":                   "09/06/2025",
    "12.001  4-Byte unsigned  0–4294967295":      "100000",
    "13.001  4-Byte signed":                      "-50000",
    "13.010  Active energy  Wh":                  "123456",
    "13.013  Active energy  kWh":                 "1234",
    "14.xxx  4-Byte float  (generic)":            "1234.56",
    "16.000  ASCII string  (max 14 chars)":       "Hello KNX",
    "16.001  Latin-1 string (max 14 chars)":      "Hello KNX",
    "17.001  Scene number  1–64":                 "5",
    "18.001  Scene control  (activate/learn N)":  "activate 5  /  learn 5",
    "19.001  DateTime  DD/MM/YYYY HH:MM:SS":      "09/06/2025 14:30:00",
    "20.102  HVAC mode":                          "auto / comfort / standby / economy / protection",
    "Raw hex  e.g.  FF 0A 3B":                    "FF 0A 3B",
}

# first real option (skip separator)
_FIRST_OPT = next(lbl for lbl, enc in DPT_OPTIONS if enc is not None)


class KNXSendApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("KNX Send")
        self.resizable(False, False)
        self.configure(bg=BG)
        try:
            self.iconbitmap(resource_path("knxsend.ico"))
        except Exception:
            pass
        self._build_ui()
        self._tick()

    # ── UI ───────────────────────────────────────────────────────────────────
    def _build_ui(self):
        mono_lg = ("Courier New", 28, "bold")
        sans_sm = ("Segoe UI", 8)

        tk.Frame(self, bg=ACCENT, height=4).pack(fill="x")

        tf = tk.Frame(self, bg=BG)
        tf.pack(fill="x", padx=24, pady=(18, 4))
        tk.Label(tf, text="KNX", font=("Courier New", 22, "bold"),
                 fg=ACCENT, bg=BG).pack(side="left")
        tk.Label(tf, text=" SEND", font=("Courier New", 22),
                 fg=TEXT, bg=BG).pack(side="left")

        tk.Label(self, text="KNX Telegram Sender",
                 font=sans_sm, fg=TEXT_DIM, bg=BG).pack(anchor="w", padx=24)

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x", padx=24, pady=14)

        # clock
        self.clock_var = tk.StringVar(value="--:--:--")
        self.date_var  = tk.StringVar(value="--/--/----")
        cf = tk.Frame(self, bg=PANEL)
        cf.pack(fill="x", padx=24, pady=(0, 14))
        cf.pack_propagate(False)
        cf.configure(height=90)
        inner = tk.Frame(cf, bg=PANEL)
        inner.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(inner, textvariable=self.clock_var,
                 font=mono_lg, fg=ACCENT, bg=PANEL).pack()
        tk.Label(inner, textvariable=self.date_var,
                 font=("Courier New", 13), fg=TEXT_DIM, bg=PANEL).pack()

        # ── Gateway ──────────────────────────────────────────────────────────
        self._section("GATEWAY CONNECTION")

        row_conn = tk.Frame(self, bg=BG)
        row_conn.pack(fill="x", padx=24, pady=(0, 14))

        ip_col = tk.Frame(row_conn, bg=BG)
        ip_col.pack(side="left", expand=True, fill="x", padx=(0, 8))
        tk.Label(ip_col, text="GATEWAY IP", font=("Courier New", 8),
                 fg=TEXT_DIM, bg=BG).pack(anchor="w")
        ef = tk.Frame(ip_col, bg=BORDER, bd=1)
        ef.pack(fill="x", pady=(3, 0))
        self.ip_var = tk.StringVar(value="192.168.0.10")
        tk.Entry(ef, textvariable=self.ip_var, font=("Courier New", 12),
                 fg=TEXT, bg=PANEL, insertbackground=ACCENT,
                 relief="flat", bd=8, highlightthickness=0).pack(fill="x")

        port_col = tk.Frame(row_conn, bg=BG, width=90)
        port_col.pack(side="left")
        port_col.pack_propagate(False)
        tk.Label(port_col, text="PORT", font=("Courier New", 8),
                 fg=TEXT_DIM, bg=BG).pack(anchor="w")
        pf = tk.Frame(port_col, bg=BORDER, bd=1)
        pf.pack(fill="x", pady=(3, 0))
        self.port_var = tk.StringVar(value="3671")
        tk.Entry(pf, textvariable=self.port_var, font=("Courier New", 12),
                 fg=TEXT, bg=PANEL, insertbackground=ACCENT,
                 relief="flat", bd=8, highlightthickness=0).pack(fill="x")

        # ── Telegram ─────────────────────────────────────────────────────────
        self._section("KNX TELEGRAM")

        ga_frame = tk.Frame(self, bg=BG)
        ga_frame.pack(fill="x", padx=24, pady=(0, 6))
        tk.Label(ga_frame, text="GROUP ADDRESS  (e.g. 1/2/3)",
                 font=("Courier New", 8), fg=TEXT_DIM, bg=BG).pack(anchor="w")
        gaf = tk.Frame(ga_frame, bg=BORDER, bd=1)
        gaf.pack(fill="x", pady=(3, 0))
        self.ga_var = tk.StringVar(value="0/0/1")
        tk.Entry(gaf, textvariable=self.ga_var, font=("Courier New", 12),
                 fg=TEXT, bg=PANEL, insertbackground=ACCENT,
                 relief="flat", bd=8, highlightthickness=0).pack(fill="x")

        # DPT combobox
        dpt_frame = tk.Frame(self, bg=BG)
        dpt_frame.pack(fill="x", padx=24, pady=(0, 6))
        tk.Label(dpt_frame, text="DATA TYPE (DPT)",
                 font=("Courier New", 8), fg=TEXT_DIM, bg=BG).pack(anchor="w")

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("KNX.TCombobox",
                        fieldbackground=PANEL, background=PANEL,
                        foreground=TEXT, arrowcolor=ACCENT,
                        selectbackground=PANEL, selectforeground=TEXT,
                        bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                        relief="flat")
        style.map("KNX.TCombobox",
                  fieldbackground=[("readonly", PANEL)],
                  foreground=[("readonly", TEXT)])

        self.dpt_var = tk.StringVar(value=_FIRST_OPT)
        self._combo_values = [lbl for lbl, _ in DPT_OPTIONS]
        self.combo = ttk.Combobox(dpt_frame, textvariable=self.dpt_var,
                                  values=self._combo_values,
                                  state="readonly", font=("Courier New", 10),
                                  style="KNX.TCombobox")
        self.combo.pack(fill="x", pady=(3, 0), ipady=6)
        self.combo.bind("<<ComboboxSelected>>", self._on_dpt_change)

        # value entry
        val_frame = tk.Frame(self, bg=BG)
        val_frame.pack(fill="x", padx=24, pady=(0, 6))
        tk.Label(val_frame, text="VALUE",
                 font=("Courier New", 8), fg=TEXT_DIM, bg=BG).pack(anchor="w")
        vf = tk.Frame(val_frame, bg=BORDER, bd=1)
        vf.pack(fill="x", pady=(3, 0))
        self.val_var = tk.StringVar(value="1")
        tk.Entry(vf, textvariable=self.val_var, font=("Courier New", 12),
                 fg=TEXT, bg=PANEL, insertbackground=ACCENT,
                 relief="flat", bd=8, highlightthickness=0).pack(fill="x")

        self.hint_var = tk.StringVar(value=HINT.get(_FIRST_OPT, ""))
        tk.Label(val_frame, textvariable=self.hint_var,
                 font=("Courier New", 8), fg=TEXT_DIM, bg=BG).pack(anchor="w", pady=(2, 0))

        # send button
        self.btn = tk.Button(self, text="▶  SEND TELEGRAM",
                             font=("Courier New", 12, "bold"),
                             fg=BG, bg=ACCENT,
                             activeforeground=BG, activebackground=ACCENT2,
                             relief="flat", bd=0, cursor="hand2", pady=12,
                             command=self._send)
        self.btn.pack(fill="x", padx=24, pady=(8, 6))

        # log
        tk.Label(self, text="LOG", font=("Courier New", 8),
                 fg=TEXT_DIM, bg=BG).pack(anchor="w", padx=24)
        log_frame = tk.Frame(self, bg=PANEL)
        log_frame.pack(fill="x", padx=24, pady=(3, 20))
        self.log = tk.Text(log_frame, height=6, font=("Courier New", 9),
                           fg=TEXT, bg=PANEL, insertbackground=ACCENT,
                           relief="flat", bd=8, state="disabled",
                           highlightthickness=0)
        self.log.pack(fill="x")
        self.log.tag_config("ok",   foreground=ACCENT)
        self.log.tag_config("err",  foreground=ERR)
        self.log.tag_config("warn", foreground=WARN)
        self.log.tag_config("info", foreground=INFO)
        self.log.tag_config("dim",  foreground=TEXT_DIM)

        tk.Frame(self, bg=ACCENT, height=2).pack(fill="x", side="bottom")

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.update_idletasks()
        w, h = 440, self.winfo_reqheight()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def _section(self, title):
        f = tk.Frame(self, bg=BG)
        f.pack(fill="x", padx=24, pady=(4, 8))
        tk.Label(f, text=title, font=("Courier New", 8, "bold"),
                 fg=ACCENT, bg=BG).pack(side="left")
        tk.Frame(f, bg=BORDER, height=1).pack(
            side="left", fill="x", expand=True, padx=(8, 0), pady=4)

    # ── events ───────────────────────────────────────────────────────────────
    def _on_dpt_change(self, _event=None):
        sel = self.dpt_var.get()
        # if user clicked a separator, jump to next real option
        enc = next((e for lbl, e in DPT_OPTIONS if lbl == sel), SEP)
        if enc is SEP:
            next_real = next((lbl for lbl, e in DPT_OPTIONS if e is not None), sel)
            self.dpt_var.set(next_real)
            sel = next_real
        self.hint_var.set(HINT.get(sel, ""))

    def _tick(self):
        now = datetime.now()
        self.clock_var.set(now.strftime("%H:%M:%S"))
        self.date_var.set(now.strftime("%d / %m / %Y"))
        self.after(1000, self._tick)

    def _log(self, msg, tag=""):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.configure(state="normal")
        self.log.insert("end", f"[{ts}] ", "dim")
        self.log.insert("end", msg + "\n", tag or "")
        self.log.see("end")
        self.log.configure(state="disabled")

    # ── send ─────────────────────────────────────────────────────────────────
    def _send(self):
        ga_str  = self.ga_var.get().strip()
        dpt_lbl = self.dpt_var.get()
        val_str = self.val_var.get().strip()
        ip      = self.ip_var.get().strip()
        port_s  = self.port_var.get().strip()

        if not ga_str:
            self._log("Group address is missing", "err"); return
        if not val_str:
            self._log("Value is missing", "err"); return
        try:
            port = int(port_s)
        except ValueError:
            self._log("Invalid port number", "err"); return

        encoder = next((enc for lbl, enc in DPT_OPTIONS if lbl == dpt_lbl and enc is not None), None)
        if encoder is None:
            self._log("Select a valid data type (not a section header)", "err"); return

        try:
            payload = encoder(val_str)
        except Exception as e:
            self._log(f"Invalid value for {dpt_lbl.split()[0]}: {e}", "err"); return

        self.btn.configure(state="disabled", text="  SENDING...")
        self._log(f"→ GA {ga_str}  DPT {dpt_lbl.split()[0]}  val={val_str}", "info")
        threading.Thread(
            target=self._run_async,
            args=(ip, port, ga_str, payload),
            daemon=True
        ).start()

    def _run_async(self, ip, port, ga_str, payload):
        try:
            asyncio.run(self._do_send(ip, port, ga_str, payload))
        except Exception as e:
            self.after(0, lambda: self._log(f"ERROR: {e}", "err"))
        finally:
            self.after(0, lambda: self.btn.configure(
                state="normal", text="▶  SEND TELEGRAM"))

    async def _do_send(self, ip, port, ga_str, payload):
        cfg = ConnectionConfig(
            connection_type=ConnectionType.TUNNELING,
            gateway_ip=ip,
            gateway_port=port,
        )
        async with XKNX(connection_config=cfg) as xknx:
            telegram = Telegram(
                destination_address=GroupAddress(ga_str),
                payload=GroupValueWrite(payload),
            )
            await xknx.telegrams.put(telegram)
            await asyncio.sleep(0.5)
            self.after(0, lambda: self._log(
                f"OK  GA={ga_str}  {ip}:{port}", "ok"))

    def resource_path(relative_path):
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.dirname(__file__), relative_path)
        
if __name__ == "__main__":
    app = KNXSendApp()
    app.mainloop()
