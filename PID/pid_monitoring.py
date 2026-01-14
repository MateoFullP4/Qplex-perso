"""
This code is designed to print different values of the PID when ran. 
It does not include a loop (yet) and therefore only return the values once when executed. 

Feel free to add any other parameters you want to access, you'll find the addresses in that : 
https://assets.omega.com/manuals/M4704.pdf

This code is tailored for a Windows System, please note that you need to change the port from
'COMX' to the required format for Linux e.g '/dev/ttyS#'.

This code currently returns a dictionnary with : 
    - The PID parameters (Ti, Td, P)
    - The number of patterns programmed : Np
    - The total number of steps programmed : Ns
    - A list such that : - Steps[i][j][0] is the set temperature of the j-th step of the i-th pattern 
                         - Steps[i][j][1] is the set time between steps of the j-th step of the i-th pattern 
"""

import minimalmodbus
import numpy as np

# --- Configuration Constants ---
PORT = 'COM8'           # Serial port identifier
SLAVE_ADDRESS = 1       # Modbus slave ID
TOTAL_PATTERNS = 8      # Hardware capacity of CN7800
STEPS_PER_PATTERN = 8   # Hardware capacity per pattern

# --- Instrument Initialization ---
instrument = minimalmodbus.Instrument(PORT, SLAVE_ADDRESS)
instrument.serial.baudrate = 9600
instrument.serial.timeout = 0.5
instrument.serial.parity = minimalmodbus.serial.PARITY_EVEN
instrument.mode = minimalmodbus.MODE_RTU

# --- Define global variable DATA ---

DATA = {
        "PID": {},
        "Np": 0, 
        "Ns": 0,
        "Steps": np.zeros((TOTAL_PATTERNS, STEPS_PER_PATTERN, 2))
    }


def read_controller_data():
    """
    Reads PID parameters and the full step/pattern memory from the CN7800.
    Returns a dictionary containing the structured data.
    """

    try:
        # Read PID parameters
        DATA["PID"]["P"] = instrument.read_register(0x1009, 1)
        DATA["PID"]["Ti"] = instrument.read_register(0x100A, 0)
        DATA["PID"]["Td"] = instrument.read_register(0x100B, 0)

        # Read programmed patterns and steps
        total_steps_counter = 0
        patterns_with_data = 0

        for p in range(TOTAL_PATTERNS):
            # Read how many steps are active in this specific pattern (Register 0x1040 + p)
            # The controller returns (Number of steps - 1), so we add 1.
            try:
                actual_steps_in_p = instrument.read_register(0x1040 + p, 0) + 1
            except:
                actual_steps_in_p = 0
            
            if actual_steps_in_p > 0:
                patterns_with_data += 1
            
            for s in range(STEPS_PER_PATTERN):
                # Calculate register addresses
                temp_reg = 0x2000 + (p * 8) + s
                time_reg = 0x2080 + (p * 8) + s

                # Read raw values 
                # Temp is stored as T*10, Time is in minutes
                raw_temp = instrument.read_register(temp_reg, 1)
                raw_time = instrument.read_register(time_reg, 0)

                DATA["Steps"][p][s][0] = raw_temp 
                DATA["Steps"][p][s][1] = raw_time

                # Increment total steps if the step has a defined time/temp
                if s < actual_steps_in_p:
                    total_steps_counter += 1 

        DATA["Np"] = patterns_with_data
        DATA["Ns"] = total_steps_counter   

        return DATA 

    except Exception as e:
        print(f"Error reading from controller: {e}")
        return None


def reset_data():
    """
    Reset the data between the runs to avoid conflict with previous runs. 
    """
    DATA["PID"] = {}
    DATA["Np"] = 0
    DATA["Ns"] = 0
    DATA["Steps"] = np.zeros((TOTAL_PATTERNS, STEPS_PER_PATTERN, 2))


def main():
    print(f"Connecting to CN7800 on {PORT}...")

    reset_data()
    results = read_controller_data()

    if results:
        print("\n--- PID Parameters ---")
        print(f"P (Proportional): {results['PID']['P']}")
        print(f"Ti (Integral):    {results['PID']['Ti']}")
        print(f"Td (Derivative):  {results['PID']['Td']}")

        print("\n--- Program Statistics ---")
        print(f"Number of patterns (Np): {results['Np']}")
        print(f"Total active steps (Ns): {results['Ns']}")

        print("\n--- Pattern Data (First 2 Patterns) ---")
        for i in range(2):
            print(f"Pattern {i}:")
            for j in range(STEPS_PER_PATTERN):
                temp = results['Steps'][i][j][0]
                dur = results['Steps'][i][j][1]
                if dur > 0 or temp > 0: # Only print non-empty steps
                    print(f"  Step {j}: {temp}°C for {dur} min")


main()   



