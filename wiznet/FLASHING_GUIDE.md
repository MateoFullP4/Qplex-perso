# Flashing MicroPython Code on W5500-EVB-Pico (Wiznet)

This guide explains how to flash MicroPython and deploy the project files onto a **W5500-EVB-Pico** (Raspberry Pi Pico + Wiznet W5500 Ethernet).

---

## 1. Requirements

### Hardware
- W5500-EVB-Pico board
- USB cable (data-capable)
- Graphix One Controller (pressure gauge)


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

## 2. Flashing Process

This section explains the step-by-step process to flash your W5500-EVB-Pico with MicroPython.

### Step 1 – Enter BOOTSEL Mode
1. Unplug the W5500-EVB-Pico.
2. Press and hold the **BOOTSEL** button.
3. Plug the USB cable into your computer.
4. Release the **BOOTSEL** button.  
   The board appears as a USB drive named `RPI-RP2`.

### Step 2 – Flash MicroPython Firmware
1. Copy the downloaded `.uf2` MicroPython firmware onto the `RPI-RP2` drive.
2. The board will reboot automatically after flashing.

---

### Step 3 – Verify MicroPython Connection
Open a terminal and check the REPL:
```bash
mpremote connect auto repl



