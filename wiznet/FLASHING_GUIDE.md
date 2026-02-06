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
```
You should see : 
```bash
>>>
```
Press `Ctrl+]` to exit REPL. 


## 3. Uploading Files on the Wiznet

### Command 1 - Adding a File on the Board
```bash
ampy -p COMx put path-to-file.py name_of_file.py
```
- `path_to_file.py`: Path on your computer
- `name_of_file.py`: Name to save on the board
**Important**: Your main program **must be named** `main.py` on the board. MicroPython automatically executes `main.py` on boot. 
Replace `COMx` with your board's COM port (Windows) or `/dev/ttyUSB0` (Linux).

### Command 2 - Removing a File on the Board
```bash
ampy -p COMx rm name_of_file.py
```
- `name_of_file.py`: Name of the file to remove on the board. 

### Command 3 - Check the Existing Files
```bash
ampy -p COMx ls
```
This shows all files currently on the MicroPython board. 


## 4. Executing Files 

Now, if you were to just plug the wiznet to the controller and to a power source, it would work just fine and start automatically running `main.py`. \\
Though, you might want to debug it, by using `mock_values.py` for instance. \\
To do so, you can execute the files by hand using `mpremote`:
```bash
python -m serial.tools.miniterm COMx 115200
```
Please note that `115200` is the baudrate and can be different depending on the model of the Pico. \\
You should see: 
```bash
--- Miniterm on COM7  115200,8,N,1 ---
--- Quit: Ctrl+] | Menu: Ctrl+T | Help: Ctrl+T followed by Ctrl+H ---
```
To soft reset and run `main.py` by hand, you can now press `Ctrl + D`.