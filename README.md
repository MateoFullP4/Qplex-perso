# Qplex-perso

This repository compile the codes used to interact with hardware in Qplex project. It ranges from interfacing PID to setup remote monitoring for pressure gauges.

---

## Documentation

To facilitate the understanding of the codes, I uploaded the **.pdf manuals** of the hardware used in Qplex in this folder (PID, pressure gauge...). 


## PID

### 1 - pid_monitoring.py

This code is designed to print different values of the PID when ran. \
It **does not include a loop** and therefore only return the values once when executed. \
This **code's only purpose is to test the hardware connection** and parameters (baudrate, port number...) for the other files in this folder.

### 2 - set_ramp.py

This code is designed to **set a ramp** on an Omega CN7800 auto-heater.
The parameters of the set ramp are the following : 
- Total number of steps 
- Final temperature to reach 
- Time between each step 

This code gives a nice idea of how ramps work, but **does not handle** overwriting already existing ramps, logs, or any other form of monitoring. 

### 3 - streamlit_config.py

This code is designed to set up an ergonomic interface to communicate with a CN7800 Omega PID, 
using Streamlit. \
An **already existing and more complete documentation** can be found on the internet page that is created when the code is executed. 

## Test_Pressure_Gauge

### 1 - mock_values.py

This program **simulates communication** with a Graphix controller and exposes a **fake pressure measurement** through an HTTP server in Prometheus text exposition format.
\
It is intended for **development, testing, and validation** of:
- Prometheus scraping
- Network configuration
- Metric formatting
- Application logic

No real RS232 communication is performed in this file.
The pressure value is randomly generated to mimic a real sensor.

### 2 - test_pressure_reading.py

This code serves as a **quick connection test** with the Graphix One controller to **check for hardware issues**. \
When executed, the test asks for the current pressure value (in Pascals), then parse the response to 
extract the float value and then prints it. \
**Beware** : The parsing part may vary depending on the model of the pressure gauge. For reference, the parsing function used in `../wiznet/main.py` is different and handles scientific expression better. 


### 3 - test_prometheus_client.py

This code is designed to access and read the pressure value given by a Graphix One controller. \
This code was used as a first try to **setup and relay data to a Prometheus server.** \
A more developped version (compatible with MicroPython) can be found in `../wiznet/main.py`. \
\
**Beware**: This code **does not setup a local server through ethernet**, and that it can not be downloaded
as such on a W5500-EVB-pico and only serves as a draft.


## Wiznet

### 1 - config.py
This file centralizes **all configuration parameters** used by `./main.py`. \

The configuration **includes**:
- Global application settings (scrape interval, HTTP port, metric labels)
- UART parameters for communication with the Graphix controller
- SPI and Ethernet parameters for the W5500 network interface
- Protocol constants used by the Graphix RS232 communication

### 2 - main.py
This program is intended to run on a **W5500-EVB-Pico board**, using **MicroPython**. \

This code allows the W5500-EVB-Pico to:
- Read pressure data from a Graphix One controller over RS232 (UART)
- Expose the measurements through an Ethernet-based HTTP server
- Serve the data in Prometheus text exposition format


### 3 - FLASHING_GUIDE.md
This guide explains how to flash MicroPython and deploy the project files onto a **W5500-EVB-Pico** (Raspberry Pi Pico + Wiznet W5500 Ethernet).
