# Qplex-perso

This repository compiles the code used to interact with hardware in the Qplex project.  
It ranges from PID interfacing to setting up remote monitoring for pressure gauges.

---

## Documentation

To facilitate understanding, the **PDF manuals** of the hardware used in Qplex (PID, pressure gauge, etc.) are included in this repository.

---

# PID

## 1 - `pid_monitoring.py`

This script prints various PID values when run.  
It **does not include a loop** and therefore returns the values only once per execution.

Its sole purpose is to **test hardware communication and connection parameters** (baud rate, port number, etc.) before running the other scripts in this folder.

---

## 2 - `set_ramp.py`

This script sets a ramp on an **Omega CN7800 auto-heater**.

The configurable parameters are:
- Total number of steps  
- Final temperature  
- Time interval between each step  

This implementation demonstrates how ramps operate but **does not handle**:
- Overwriting existing ramps  
- Logging  
- Monitoring  

---

## 3 - `streamlit_config.py`

This script provides an ergonomic interface to communicate with a **CN7800 Omega PID** using **Streamlit**.

A more detailed and complete documentation is available directly from the web interface generated when the application is launched.

---

# Test_Pressure_Gauge

## 1 - `mock_values.py`

This program **simulates communication** with a Graphix controller and exposes a **fake pressure measurement** through an HTTP server using the Prometheus text exposition format.

It is intended for development, testing, and validation of:

- Prometheus scraping  
- Network configuration  
- Metric formatting  
- Application logic  

No real RS232 communication is performed.  
The pressure value is randomly generated to mimic a real sensor.

---

## 2 - `test_pressure_reading.py`

This script serves as a **quick connection test** for the Graphix One controller.

When executed, it:
1. Requests the current pressure value (in Pascals)  
2. Parses the controller response  
3. Extracts and prints the floating-point value  

⚠ **Note:**  
The parsing logic may vary depending on the pressure gauge model.  
For reference, the parsing function used in `../wiznet/main.py` is more robust and better handles scientific notation.

---

## 3 - `test_prometheus_client.py`

This script implements a **Prometheus exporter** for a Leybold Graphix One pressure controller.

It communicates with the controller over a serial connection, periodically reads the pressure value using the Graphix protocol (SI / CRC / EOT framing), and exposes the measurement through an HTTP endpoint compatible with Prometheus.

### Features

- Serial communication with the Graphix One controller  
- Protocol frame construction and CRC calculation  
- YAML-based configuration (`config.yml`)  
- Embedded HTTP server for Prometheus scraping  
- Pressure metric export (in Pascals)  
- Scraper status monitoring (`starting` / `running` / `error`)  
- Logging with optional debug mode  

The script is designed to run as a **continuous monitoring service** in a standard Python environment.


---

# Wiznet

## 1 - `config.py`

Centralizes **all configuration parameters** used by `main.py`.

Includes:

- Global application settings (scrape interval, HTTP port, metric labels)  
- UART parameters for communication with the Graphix controller  
- SPI and Ethernet configuration for the W5500 interface  
- Protocol constants for Graphix RS232 communication  

---

## 2 - `main.py`

Designed to run on a **W5500-EVB-Pico board** using **MicroPython**.

It allows the board to:

- Read pressure data from a Graphix One controller via RS232 (UART)  
- Expose measurements through an Ethernet-based HTTP server  
- Serve metrics in Prometheus text exposition format  

---

## 3 - `FLASHING_GUIDE.md`

Explains how to:

- Flash MicroPython  
- Deploy project files  
- Configure the W5500-EVB-Pico (Raspberry Pi Pico + Wiznet W5500 Ethernet module)  
