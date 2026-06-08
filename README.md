# KNX Telegram Sender

A lightweight desktop tool for sending KNX telegrams directly to a KNX/IP gateway via tunneling connection.

Built with Python + tkinter, powered by [xknx](https://github.com/XKNX/xknx).

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square)
![xknx](https://img.shields.io/badge/xknx-latest-green?style=flat-square)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey?style=flat-square)

---

## Features

- Connect to any KNX/IP gateway via tunneling (IP + port)
- Send a value to any group address
- Full DPT support across all major data types (see list below)
- Live clock display
- Colour-coded log panel
- Open the gateway web interface in one click

## Supported Data Types

| DPT | Description |
|-----|-------------|
| 1.x | Switch, Bool, Enable, Up/Down, Open/Close, Start/Stop |
| 3.x | Dimming control, Blinds control (4-bit) |
| 5.x | Scaling (%), 1-Byte unsigned |
| 6.x | Percent V8 signed, Counter pulses |
| 7.x | 2-Byte unsigned |
| 8.x | 2-Byte signed, Rotation angle |
| 9.x | Temperature, Humidity, Illuminance, Wind speed, Pressure, Voltage, Current, generic 2-byte float |
| 10/11 | Time, Date |
| 12.x | 4-Byte unsigned |
| 13.x | 4-Byte signed, Active energy (Wh / kWh) |
| 14.x | 4-Byte float (generic) |
| 16.x | ASCII string, Latin-1 string (max 14 chars) |
| 17/18 | Scene number, Scene control (activate / learn) |
| 19 | DateTime |
| 20 | HVAC mode (Auto / Comfort / Standby / Economy / Protection) |
| Raw | Raw hex bytes (e.g. `FF 0A 3B`) |

## Requirements

- Python 3.10+
- [xknx](https://xknx.io)

```
pip install xknx
```

## Usage

```
python knxsend.py
```

1. Enter your KNX/IP gateway IP and port (default: `3671`)
2. Enter the group address (e.g. `1/2/3`)
3. Select the data type from the dropdown
4. Enter the value — a hint is shown below the field
5. Click **▶ SEND TELEGRAM**

## Value Format Examples

| DPT | Input example |
|-----|--------------|
| 1.001 Switch | `1` / `0` / `true` / `false` |
| 3.007 Dimming | `increase 5` / `decrease 3` / `stop` |
| 5.001 Scaling | `75` |
| 9.001 Temperature | `21.5` |
| 10.001 Time | `14:30:00` |
| 11.001 Date | `09/06/2025` |
| 19.001 DateTime | `09/06/2025 14:30:00` |
| 20.102 HVAC mode | `comfort` / `standby` / `auto` |
| Raw hex | `FF 0A 3B` |

## License

MIT
