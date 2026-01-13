"""
This code is designed to set a ramp on an Omega CN7800 auto-heater. You can find the manual there :
https://assets.omega.com/manuals/M4704.pdf
This code is tailored for a Windows System, please note that you need to change the port from
'COMX' to the required format for Linux e.g '/dev/ttyS#'.

The parameters of the set ramp are the following :
Total number of steps
Final temperature to reach
Time between each step

Note that the first step is always set exactly one degrees above room temperature to avoid PID 
from overshooting. 
"""

import minimalmodbus
import numpy as np
import time 

# --- Configuration Constants ---
TOTAL_STEPS = 15            # Total sequence steps (2 to 64)
TIME_BETWEEN_STEPS = 1      # Duration of each step in minutes
FINAL_TEMPERATURE = 100     # Target final temperature in Celsius 
MAX_STEPS_PER_PATTERN = 8   # CN7500 hardware limit per pattern
PORT = 'COM8'               # Serial port identifier
SLAVE_ADDRESS = 1           # Modbus slave ID


# --- Instrument Initialization ---
# Setup communication with the CN7500 controller
instrument = minimalmodbus.Instrument(PORT, 1) 
instrument.serial.baudrate = 9600
instrument.serial.timeout = 0.2
instrument.serial.parity = minimalmodbus.serial.PARITY_EVEN
instrument.mode = minimalmodbus.MODE_RTU


def read_pv():
    """
    Reads the Current Processed Value (room temperature) from the controller. 
    Register 0x1000 : Process Value (PV)
    """
    return instrument.read_register(int("0x1000",0),1)


def read_pid():
    """
    Reads the Proportional, Integral, and Derivative (PID) settings.
    Registers: 0x1009 (PB), 0x100A (Ti), 0x100B (Td).
    """
    kp = instrument.read_register(int("0x1009",0), 1)
    ti = instrument.read_register(int("0x100A",0), 0)
    td = instrument.read_register(int("0x100B",0), 0)
    return kp,ti,td


def safe_write(register, value):
    """
    Writes a value to a given register with a retry mechanism to handle interference.
    Args:
        register (int): Hex address of the register
        value (int): value to write 

    """
    max_retries = 3
    for i in range(max_retries):
        try:
            instrument.write_register(register, value)
            return True
        except Exception as e:
            if i == max_retries - 1:
                print(f"Failed to write to {hex(register)} after {max_retries} attempts.")
                raise e
            time.sleep(0.1)


def generate_temperatures():
    """
    Creates a temperature ramp as such : 
    The first step if the current PV, the second is exactly one degrees above, and the rest of the ramp
    is linear from the second step to the final temperature.
    Returns: 
        list: list of floats representing the temperature at each step.
    """
    if TOTAL_STEPS < 1 or TOTAL_STEPS > 64:
        raise ValueError("The total number of steps must be between 1 and 64") 
    
    room_temperature = read_pv()
    
    if TOTAL_STEPS == 1:
        return [float(room_temperature)]
    
    # Initial small step to tune the PID and avoid overshooting
    first_target = room_temperature + 1.0
    if TOTAL_STEPS == 2:
        return [float(room_temperature), float(first_target)]
    
    # Calculate linear ramp for the remaining steps    
    remaining_steps = TOTAL_STEPS - 2
    linear_part = np.linspace(first_target, FINAL_TEMPERATURE, remaining_steps+1)
    temperatures = [float(room_temperature)] + list(linear_part)

    return temperatures


def chunk(lst, n):
    """
    Split the total list into chunks of size n
    Args:
        list: list to split
        int: size of the chunks that will be created
    """
    for i in range(0, len(lst), n):
        yield lst[i:i+n]


def program_all_paterns():
    """
    Main sequence to configure patterns, links, and steps on the CN7500, then executes the heating program.
    """
    temperatures = generate_temperatures()

    # CN7500 organizes steps into 'Patterns' of up to 8 steps each
    patterns = list(chunk(temperatures, MAX_STEPS_PER_PATTERN))

    count = 0
    for p_index, steps in enumerate(patterns):
        for s_index, T in enumerate(steps):
            # Calculate register addresses based on pattern and step index
            # Temp registers start at 0x2000; Time registers start at 0x2080
            temp_reg = int("0x2000",0) + p_index*8 + s_index
            time_reg = int("0x2080",0) + p_index*8 + s_index
            
            # Optional: Disable Auto-tuning bit during setup if needed
            if count > 1:
                instrument.write_bit(int("0x0813",0), 0)
            
            # Note: Temperature is usually stored as (Temp * 10) in the controller
            safe_write(temp_reg, int(round(T * 10)))
            safe_write(time_reg, TIME_BETWEEN_STEPS)
            count += 1

        # Set the 'Actual Number of Steps' for the current pattern (0-indexed)
        # 0x1040 is the start of pattern step-count registers
        safe_write(0x1040 + p_index, len(steps) - 1)

        # Link patterns: Tell current pattern which one to follow next
        # 0x1060 is the start of pattern link registers
        link_reg = int("0x1060",0) + p_index
        if p_index == len(patterns)-1:
            safe_write(link_reg, 0x08) # 0x08 indicates 'End of Program'
        else:
            safe_write(link_reg, p_index + 1)
    
    # Set cycle counts for each pattern to 0 (execute once)
    for i in range(len(patterns)):
        safe_write(0x1050 + i, 0)

    # --- Start Execution Sequence ---    
    safe_write(0x1030, 0)    # Set starting pattern to 0
    safe_write(0x1031, 0)    # Set starting step to 0
    safe_write(0x1005, 3)    # Set Control Mode to 'Program'
    
    instrument.write_bit(0x0813, 1)   # Turn Auto-Tuning (AT) ON
    instrument.write_bit(0x0814, 1)   # Set Run/Stop to RUN

    print(f"Program started: {TOTAL_STEPS} steps programmed successfully.")


program_all_paterns()









