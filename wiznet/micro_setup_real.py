""" 
This code is designed to be implemented on a W5500-EVB-pico under Windows. 
The modules used are specific to micro-python and the .uf2 folder used can be found at :
https://micropython.org/download/RPI_PICO/
The version used is v1.26.1 (2025-09-11)

This program runs with the help of a config.py that is installed on the W5500-EVB-pico, 
in which all the variables of the configuration are specified. 

For more details about the wiring or the CRC calculation, please refer to Graphix One controller Manual : 
https://www.idealvac.com/files/manuals/Leybold_GRAPHIX_123_Instruction_Manual.pdf?srsltid=AfmBOopd9Enj3GeLaJVnPIEAdfaF3iB9zg6F_SY2v9AX0OK8wkuFWzkj

This code allows a W5500-EVB-Pico to read the data from a Graphix One controller and to setup a local 
server through Ethernet, using Prometheus. 
Please note that this only handles Ethernet connection and the function setup_network() needs to be changed
if you want to change the type of connection. 
"""

import utime
import usocket as socket
import machine
import gc
import sys

# --- Configuration & Constants ---
# Import the variables of the configuration from config.py
from config import (
    GLOBAL_CONFIG, GRAPHIX_CONFIG, NETWORK_CONFIG,
    SI, EOT, SEPARATOR, VERSION, NAME)

# --- Global System States ---
# Global states for tracking pressure and system status
pressure_value = None
scraper_status = "starting"
METRICS = {}


class uGauge:
    """
    A lightweight class to mimic Prometheus gauge behavior. 
    Formats data into the standard Prometheus text exposition format.
    """

    def __init__(self, name, documentation, unit, tags):
        self.name = name
        self.documentation = documentation
        self.unit = unit
        self.labels = self._format_labels(tags)
        self.value = 0

    def _format_labels(self, tags):
        # Converts a dictionary of tags into a Prometheus label string. 
        return ','.join(['{k}="{v}"'.format(k=k, v=v) for k, v in tags.items()])

    def set(self, value):
        # Updates the current gauge value. 
        self.value = value
        
    def __str__(self):
        # Returns the full Prometheus formatted string for this metric.
        output = [
            "# HELP {} {}".format(self.name, self.documentation),
            "# TYPE {} gauge".format(self.name),
            "{}{{{}}} {}".format(self.name, self.labels, self.value)
        ]
        return '\n'.join(output)


def log(level, message):
    """ 
    Standardized logger with timestamps: [HH:MM:SS] - LEVEL - Message.
    """
    time_tuple = utime.localtime() 

    # Format the hour, minute, and second into an 'HH:MM:SS' string format 
    timestamp = "{:02d}:{:02d}:{:02d}".format(time_tuple[3], time_tuple[4], time_tuple[5])
    print("[{}] - {} - {}".format(timestamp, level, message))


def calculate_crc(data: bytes) -> bytes:
    """
    Calculates the CRC for the Graphix bytes protocol over RS232. 
    """
    total = sum(data) % 256
    crc_value = 255 - total
    if crc_value < 32:
        crc_value += 32
    return bytes([crc_value])


def get_graphix_parameter(group: int, parameter: int, uart: machine.UART):
    """
    Requests a specific parameter/value to the controller. 
    The list of parameters and their respective addresses can be found in the manual. 
    """
    # Construct command string 
    command_str = f"{group}{SEPARATOR}{parameter}{SEPARATOR}"
    command_bytes = bytes([SI]) + command_str.encode("ascii")

    # Add checksum and End of Transmission (EoT)
    crc = calculate_crc(command_bytes)
    message = command_bytes + crc + bytes([EOT])

    print(f"DEBUG UART - Sending: {message}")

    # Transmit and wait for the controller answer
    uart.write(message)
    utime.sleep_ms(300) 

    # Check buffer and return raw bytes
    if uart.any():
        response = uart.read()
        print(f"DEBUG UART - Received: {response}")
        return response
    else:
        print("DEBUG UART - No response received")
        return None


def parse_parameter_value(response: bytes):
    """
    Extracts numerical value from the raw Graphix responses.
    Handles 'ACK' (0x06) prefix and strips the CRT/EoT suffixes.
    """
    # Every valid response is of len >= 3 (Start byte, Data, End byte)
    if not response or len(response)<3:
        return None

    try:
        # Decodes bytes to string, removing protocol characters
        clean_str = response[1:-2].decode('ascii').strip()

        #Filter only numeric characters (can include scientific notation)
        numeric_part = "".join([c for c in clean_str if c.isdigit() or c in '.-E+'])

        if numeric_part:
            return float(numeric_part)
        return None
                
    except Exception as e:
        log("ERROR", "Parsing failed: {} | Raw: {}".format(e, response))
        return None


def setup_metrics():
    """
    Initializes global metric objects based on configuration. 
    """
    global METRICS
    tags = GLOBAL_CONFIG["tags"]
    pressure = uGauge(
        name="graphix_pressure_value",
        documentation="Pressure gauge value in Pa",
        unit="Pa",
        tags=tags
    )
    METRICS["pressure"] = pressure


def serve_prometheus_metrics(s):
    """
    HTTP server handler.
    Checks for pending connection, serves metric text and closes.
    """

    global scraper_status
    try:
        # Accept a connexion if one is waiting in queue.
        conn, addr = s.accept()

    except OSError as e:
        # Error 11 (EAGAIN) is expected when no client is connecting
        if e.args[0] in (11, 110): 
            return
        raise e
    
    try:
        conn.settimeout(0.5) # Prevent hanging on slow clients
        request = conn.recv(1024)

        if request and b'GET /metrics' in request:
            # Build the HTTP response body
            metrics_body = []
            for name, metric in METRICS.items():
                metrics_body.append(str(metric))

            # Add internal status metric
            metrics_body.append(f"graphix_scraper_status{{status=\"{scraper_status}\"}} 1")

            body_content = '\n'.join(metrics_body) + '\n'

            # HTTP header construction
            response_headers = [
                "HTTP/1.1 200 OK",
                "Content-Type: text/plain; version=0.0.4; charset=utf-8",
                f"Content-Length: {len(body_content)}",
                "Connection: close",
                "\r\n"
            ]
            response = '\r\n'.join(response_headers).encode('utf-8') + body_content.encode('utf-8')
            conn.sendall(response)

    except Exception as e:
        log("ERROR", f"Web server error: {e}")
    finally:
        conn.close()


def main_loop(uart):
    """
    The loop that is being executed automatically when the W5500-EVB-pico is plugged.
    Manages timing for scraping and web serving. 
    """
    global scraper_status

    interval = GLOBAL_CONFIG["scrap_interval"]
    port = GLOBAL_CONFIG["http_server_port"]
    addr = socket.getaddrinfo("0.0.0.0", port)[0]

    # Initialize TCP Socket. 
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr[-1])
    s.listen(1)
    s.setblocking(False)

    log("INFO", f"Prometheus HTTP server listening on port {port}")
    last_scrape_time = utime.time() - interval 

    while True:
        gc.collect() # Periodically clean memory
        current_time = utime.time()

        # Data scraping logic in Serial        
        if current_time - last_scrape_time >= interval:
            last_scrape_time = current_time
            log("DEBUG", "Measuring and updating pressure...")

            # Request group 1, parameter 29 (pressure value)
            response = get_graphix_parameter(1, 29, uart) 
            value = parse_parameter_value(response)

            if value is not None:
                METRICS["pressure"].set(value)
                scraper_status = "running"
                log("INFO", f"Pressure: {value}")
            else:
                scraper_status = "error"

        # Network Serving Logic (HTTP)
        serve_prometheus_metrics(s)
        utime.sleep_ms(50) 



def setup_network():
    """
    Configures the W5500 via SPI and waits for a physical link.
    """
    import network
    from machine import Pin, SPI 
    
    # Setup hardware Reset and Chip Select pin
    cs_pin_obj = Pin(NETWORK_CONFIG["cs_pin"], Pin.OUT)  
    rst_pin_obj = Pin(NETWORK_CONFIG["rst_pin"], Pin.OUT) 
    
    # SPI Initialization
    spi = SPI(
        NETWORK_CONFIG["spi_id"], # spi_id: 0
        baudrate=2000000, 
        polarity=0, 
        phase=0,
        sck=machine.Pin(18), 
        mosi=machine.Pin(19), 
        miso=machine.Pin(16) 
    ) 

    # W5500 Ethernet Interface Initialization
    nic = network.WIZNET5K(spi, cs_pin_obj, rst_pin_obj)
    nic.active(True)
    nic.ifconfig(NETWORK_CONFIG["static_ip"])

    log("INFO", "Connecting to Ethernet...")

    # Poll for connection status (timeout after 10 seconds).
    for _ in range(10):
        if nic.isconnected():
            log("INFO", f"Connected! IP: {nic.ifconfig()[0]}")
            return nic.ifconfig()[0]
        utime.sleep(1)
    
    log("ERROR", "Ethernet failed.")
    return False


if __name__ == "__main__":
    # Initializes network
    ip_address = setup_network() 
    if not ip_address:
        sys.exit(1) 
    
    # Initialize Metrics (data structures)
    setup_metrics()

    # Initialize UART and RS232 hardware
    uart = machine.UART(
        GRAPHIX_CONFIG["uart_id"], 
        baudrate=GRAPHIX_CONFIG["baudrate"], 
        tx=machine.Pin(GRAPHIX_CONFIG["tx_pin"]), 
        rx=machine.Pin(GRAPHIX_CONFIG["rx_pin"])
    )

    log("SUCCESS", f"Metrics at http://{ip_address}:{GLOBAL_CONFIG['http_server_port']}/metrics")
    
    # Start Main Loop
    main_loop(uart)