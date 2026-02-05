# Flashing MicroPython Code on W5500-EVB-Pico (Wiznet)

This guide explains how to flash MicroPython and deploy the project files onto a **W5500-EVB-Pico** (Raspberry Pi Pico + Wiznet W5500 Ethernet).

---

## 1. Requirements

### Hardware
- W5500-EVB-Pico board
- USB cable (data-capable)
- 


### Software
- **MicroPython UF2 firmware** for Raspberry Pi Pico  
  Download from:  
  https://micropython.org/download/RPI_PICO/
  Use version v1.26.1 (2025-09-11)

- **mpremote**  is a tool that provides an integrated set of utilities to remotely interact with, manage the filesystem on, and automate a MicroPython device.

Install `mpremote`:
```bash
pip install mpremote
```

- **ampy** is a tool to control MicroPython boards over a serial connection.

Install `ampy`:
```bash
pip install adafruit-ampy
```
