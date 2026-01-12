import minimalmodbus
import numpy as np
import time 

# Define main parameters

TOTAL_STEPS = 15 # Between 2 and 64
TIME_BETWEEN_STEPS = 1 # in minutes
FINAL_TEMPERATURE = 100 # in Celsius 
MAX_STEPS_PER_PATTERN = 8
PORT = 'COM8'


# -------------------------------------   Instrument setup   -----------------------------------------------

# The parameters are found on the front panel of the CN7500

instrument = minimalmodbus.Instrument(PORT, 1) # Check the Serial COM
instrument.serial.baudrate = 9600
instrument.serial.timeout = 0.2
instrument.serial.parity = minimalmodbus.serial.PARITY_EVEN
instrument.mode = minimalmodbus.MODE_RTU



# -------------------------------------   A few functions   -----------------------------------------------

# Get Room temperature
def read_pv():
    return instrument.read_register(int("0x1000",0),1)

# Get PID parameters
def read_pid():
    kp = instrument.read_register(int("0x1009",0), 1)
    ti = instrument.read_register(int("0x100A",0), 0)
    td = instrument.read_register(int("0x100B",0), 0)
    return kp,ti,td

# Set to program mode
def enable_program_mode():
    instrument.write_register(int("0x1005",0), 3)

# Generate the temperatures list
def generate_temperatures():
    if TOTAL_STEPS < 1 or TOTAL_STEPS > 64:
        raise ValueError("The total number of steps must be between 1 and 64") 
    
    room_temperature = read_pv()
    

    if TOTAL_STEPS == 1:
        return [float(room_temperature)]
    
    first_target = room_temperature + 1.0
    if TOTAL_STEPS == 2:
        return [float(room_temperature), float(first_target)]
    
    remaining_steps = TOTAL_STEPS - 2
    linear_part = np.linspace(first_target, FINAL_TEMPERATURE, remaining_steps+1)
    temperatures = [float(room_temperature)] + list(linear_part)

    return temperatures


# Split the total list into chunks of size n
def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]


# In case there is an interference in the writing
def safe_write(register, value):
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



# ----------------------------------     Programming the patterns   -----------------------------------------



def program_all_paterns():

    temperatures = generate_temperatures()

    patterns = list(chunk(temperatures, MAX_STEPS_PER_PATTERN))
    count = 0
    for p_index, steps in enumerate(patterns):
        for s_index, T in enumerate(steps):
            temp_reg = int("0x2000",0) + p_index*8 + s_index
            time_reg = int("0x2080",0) + p_index*8 + s_index
            

            if count > 1:
                instrument.write_bit(int("0x0813",0), 0)
            

            safe_write(temp_reg, int(round(T * 10)))
            safe_write(time_reg, TIME_BETWEEN_STEPS)

        # declare number of steps in pattern
        safe_write(0x1040 + p_index, len(steps) - 1)

        # link patterns so they go one after another
        link_reg = int("0x1060",0) + p_index
        if p_index == len(patterns)-1:
            safe_write(link_reg, 0x08) # end
        else:
            safe_write(link_reg, p_index + 1)

    for i in range(len(patterns)):
        safe_write(0x1050 + i, 0)

    # Reset to Start of Program
    safe_write(0x1030, 0) # Start at Pattern 0
    safe_write(0x1031, 0) # Start at Step 0
    
    # Start Program Mode
    safe_write(0x1005, 3)
    
    # AT On
    instrument.write_bit(0x0813, 1)

    # Run Program
    instrument.write_bit(0x0814, 1)


program_all_paterns()









