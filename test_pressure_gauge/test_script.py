"""
This code serves as a quick connection test with the Graphix One controller to check for hardware issues:
https://www.idealvac.com/files/manuals/Leybold_GRAPHIX_123_Instruction_Manual.pdf?srsltid=AfmBOoqdN6HQTN063OsilJ9S7iyruV-MYv_djclDzcOr8JYWnCZSRBMs

When executed, the test asks for the current pressure value (in Pascals), then parse the response to 
extract the float value and then prints it. 
"""

import serial
import time

# --- Protocol Constants ---
SI = 0x0F
EOT = 0x04
SEPARATOR = ';'

def calculate_crc(data: bytes) -> bytes:
    """
    Calculate the ASCII CRC character for the given byte string.
    Please refer to the controller manual for the specific CRC formula.
    Args:
        data (bytes): Command payload in bytes."""
    total = sum(data) % 256
    crc_value = 255 - total
    if crc_value < 32:
        crc_value += 32
    return bytes([crc_value])



def get_graphix_parameter(group: int, parameter: int, port: str = 'COM1', baudrate: int = 9600):
    """
    Read a parameter from the Graphix One controller over RS232.
    Handles non-ASCII bytes in the response.
    Args:
        group (int): The parameter group (e.g., 1).
        parameter (int): The specific parameter index (e.g., 29 for pressure).
        port (str): Serial port identifier (e.g., 'COM5' or '/dev/ttyUSB0').
        baudrate (int): Communication speed (defaulted to 9600).
    """
    try:
        with serial.Serial(port, baudrate, timeout=1) as ser:
            # Build command bytes (excluding CRC and EOT)
            command_str = f"{group}{SEPARATOR}{parameter}{SEPARATOR}"
            command_bytes = bytes([SI]) + command_str.encode('ascii')
            
            # Calculate CRC
            crc = calculate_crc(command_bytes)
            
            # Full message
            message = command_bytes + crc + bytes([EOT])
            print(f"Sending bytes: {message}")
            
            ser.write(message)
            
            # Wait for response
            time.sleep(0.2)
            response = ser.read_all()  # raw bytes
            
            if not response:
                print("No response received.")
                return None
            
            # Remove EOT if present
            if response[-1] == EOT:
                response = response[:-1]
            
            # Print response as hex for debugging
            print("Received (hex):", response.hex())
                        
            return response

    except serial.SerialException as e:
        print(f"Serial error: {e}")
        return None


def parse_parameter_value(response: bytes):
    """
    Cleans the raw byte response and extracts the numerical string.
    Handles ASCII control characters like ACK (0x06).
    Args: 
        response (bytes): The raw byte sequence returned by the Graphix One.
    """
    body = response
    # Strip ASCII Acknowledge (ACK) if the controller prepended it
    if body[0] == 0x06:  
        body = body[1:]

    # Strip EOT if it was embedded in the body rather than the suffix
    if body[-1] == 0x04:  
        body = body[:-1]

    # Use a list comprehension to filter only characters used in scientific notation
    value_str = ''.join([chr(b) for b in body if chr(b) in '0123456789.-+eE'])
    return value_str


# --- Testing part ---
# This could be integrated in a __main__ 
response = get_graphix_parameter(1, 29, port='COM5', baudrate=9600)
value = parse_parameter_value(response)
print(f"Parameter value: {value}")



