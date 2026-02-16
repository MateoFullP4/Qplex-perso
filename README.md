# Qplex-perso

This repository compile the codes used to interact with hardware in Qplex project. It ranges from interfacing PID to setup remote monitoring for pressure gauges.

---

## Documentation

To facilitate the understanding of the codes, I uploaded the **.pdf manuals** of the hardware used in Qplex in this folder (PID, pressure gauge...). \


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

### 1 - test_pressure_reading.py
This code serves as a **quick connection test** with the Graphix One controller to **check for hardware issues**. \
When executed, the test asks for the current pressure value (in Pascals), then parse the response to 
extract the float value and then prints it. \
**Beware** : The parsing part may vary depending on the model of the pressure gauge. For reference, the parsing function used in `../wiznet/main.py` handles scientific expression. 


### 2 - test_prometheus_client.py

## Wiznet


