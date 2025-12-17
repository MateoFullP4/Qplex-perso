from prometheus_client import start_http_server, Gauge
import time
import serial

SI = 0x0F
EOT = 0x04
SEPARATOR = ';'

def calculate_crc(data: bytes) -> bytes:
    total = sum(data) % 256
    crc_value = 255 - total
    if crc_value < 32:
        crc_value += 32
    return bytes([crc_value])

def get_graphix_parameter(group: int, parameter: int, port: str = 'COM5', baudrate: int = 9600):
    try:
        with serial.Serial(port, baudrate, timeout=1) as ser:
            command_str = f"{group}{SEPARATOR}{parameter}{SEPARATOR}"
            command_bytes = bytes([SI]) + command_str.encode('ascii')
            crc = calculate_crc(command_bytes)
            message = command_bytes + crc + bytes([EOT])
            ser.write(message)
            time.sleep(0.2)
            response = ser.read_all()
            if not response:
                return None
            if response[-1] == EOT:
                response = response[:-1]
            return response
    except serial.SerialException:
        return None

def parse_parameter_value(response: bytes):
    body = response
    if body[0] == 0x06:  # ACK
        body = body[1:]
    if body[-1] == 0x04:  # EOT
        body = body[:-1]
    value_str = ''.join([chr(b) for b in body if chr(b) in '0123456789.-+eE'])
    try:
        return float(value_str)
    except:
        return None

# ---- Prometheus setup ----
pressure_gauge = Gauge('pressure_value', 'Pressure gauge value', ['device'])

# Start HTTP server on port 9100
start_http_server(9100)

# ---- Main loop ----
while True:
    response = get_graphix_parameter(1, 29, port='COM5', baudrate=9600)
    value = parse_parameter_value(response)
    if value is not None:
        pressure_gauge.labels(device='Graphix_COM5').set(value)
        print(f"Pressure: {value}")
    time.sleep(5)  # read every 5 seconds
