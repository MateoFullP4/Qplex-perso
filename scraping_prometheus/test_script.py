import serial
import time

SI = 0x0F
EOT = 0x04
SEPARATOR = ';'

def calculate_crc(data: bytes) -> bytes:
    """Calculate the ASCII CRC character for the given byte string."""
    total = sum(data) % 256
    crc_value = 255 - total
    if crc_value < 32:
        crc_value += 32
    return bytes([crc_value])



def get_graphix_parameter(group: int, parameter: int, port: str = 'COM1', baudrate: int = 9600):
    """
    Read a parameter from the Graphix One controller over RS232.
    Handles non-ASCII bytes in the response.
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
            
            """
            # Try decoding printable ASCII part (skip unprintable bytes)
            printable = ''.join([chr(b) if 32 <= b <= 126 else '.' for b in response])
            print("Received (interpreted):", printable)
            """
            
            return response

    except serial.SerialException as e:
        print(f"Serial error: {e}")
        return None

def parse_parameter_value(response: bytes):
    # Remove ACK and EOT
    body = response
    if body[0] == 0x06:  # ACK
        body = body[1:]
    if body[-1] == 0x04:  # EOT
        body = body[:-1]

    # Keep only digits, dot, minus, plus, or 'E' (for scientific notation)
    value_str = ''.join([chr(b) for b in body if chr(b) in '0123456789.-+eE'])
    return value_str

response = get_graphix_parameter(1, 29, port='COM5', baudrate=9600)
value = parse_parameter_value(response)
print(f"Parameter value: {value}")



