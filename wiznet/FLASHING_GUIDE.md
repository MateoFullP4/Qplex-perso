# Flashing MicroPython Code on W5500-EVB-Pico (Wiznet)

This guide explains how to flash MicroPython and deploy the project files onto a **W5500-EVB-Pico** (Raspberry Pi Pico + Wiznet W5500 Ethernet).

---

## 1. Requirements

### Hardware
- W5500-EVB-Pico board
- USB cable (data-capable)

### Software
- **MicroPython UF2 firmware** for Raspberry Pi Pico  
  Download from:  
  https://micropython.org/download/RPI_PICO/

- **Python 3.8+**
- **mpremote** tool (official MicroPython tool)

Install `mpremote`:
```bash
pip install mpremote
