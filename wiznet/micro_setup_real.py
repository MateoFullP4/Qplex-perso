""" 
This program is intended to run on a W5500-EVB-Pico board under Windows,
using MicroPython.

The required MicroPython firmware (.uf2) can be found at:
https://micropython.org/download/RPI_PICO/
Tested with MicroPython v1.26.1 (2025-09-11).

The program relies on a separate config.py file stored on the board,
which contains all hardware, network, and application configuration values.

For wiring details and CRC calculation rules, refer to the
Graphix One controller manual:
https://www.idealvac.com/files/manuals/Leybold_GRAPHIX_123_Instruction_Manual.pdf

This code allows the W5500-EVB-Pico to:
- Read pressure data from a Graphix One controller over RS232 (UART)
- Expose the measurements through an Ethernet-based HTTP server
- Serve the data in Prometheus text exposition format

Note:
This implementation supports Ethernet only. If another network interface
is required, the setup_network() function must be modified accordingly.
"""

import utime
import usocket as socket
import machine
import gc
import re
import sys


# --- Configuration & Constants ---
# Import all user-defined configuration parameters
from config import (
    GLOBAL_CONFIG, GRAPHIX_CONFIG, NETWORK_CONFIG,
    SI, EOT, SEPARATOR, VERSION, NAME)


# --- Global Runtime State ---
pressure_value = None
scraper_status = "starting"
METRICS = {}


# --- Classes ---
class uGauge:
    """
    Minimal Prometheus-like Gauge implementation.

    This class stores a numeric value and formats it according to
    Prometheus text exposition standards.
    """
    def __init__(self, name, documentation, unit, tags):
        """
        Initializes a gauge metric.

        Args:
            - name (str): Metric name exposed to Prometheus.
            - documentation (str): Human-readable metric description.
            - unit (str): Measurement unit (informational).
            - tags (dict): Dictionary of label key/value pairs.

        Returns:
            - None
        """
        self.name = name
        self.documentation = documentation
        self.unit = unit
        self.labels = self._format_labels(tags)
        self.value = None


    def _format_labels(self, tags):
        """
        Converts a dictionary of labels into a Prometheus-compatible string.
        Example: { "location": "lab", "id": "001" } --> location="lab",id="001"

        Args:
            - tags (dict): Label key/value pairs.

        Returns:
            - str: Formatted label string
        """
        return ','.join(['{k}="{v}"'.format(k=k, v=v) for k, v in tags.items()])
    

    def set(self, value):
        """
        Updates the stored gauge value.
        Args:
            - value (float): New value to store.

        Returns:
            - None
        """
        self.value = value

        
    def __str__(self):
        """
        Formats the gauge as Prometheus exposition text.

        Returns:
            - str: Formatted metric string, or empty string if no value is set.
        """
        if self.value is None:
            return ""
        
        return (
            f"# HELP {self.name} {self.documentation}\n"
            f"# TYPE {self.name} gauge\n"
            f"{self.name}{{{self.labels}}} {self.value}"
        )



# --- Utility Functions ---
def log(level, message):
    """
    Prints a timestamped log message.

    Args:
        - level (str): Log severity level (INFO, ERROR, SUCCESS, etc.).
        - message (str): Message to display.

    Returns:
        - None
    """
    time_tuple = utime.localtime() 

    # Format the hour, minute, and second into an 'HH:MM:SS' string format 
    timestamp = "{:02d}:{:02d}:{:02d}".format(time_tuple[3], time_tuple[4], time_tuple[5])
    print("[{}] - {} - {}".format(timestamp, level, message))



def calculate_crc(data: bytes) -> bytes:
    """
    Computes the CRC checksum required by the Graphix RS232 protocol.

    Args:
        - data (bytes): Payload bytes excluding CRC and EOT.

    Returns:
        - bytes: Single-byte CRC value.
    """
    total = sum(data) % 256
    crc_value = 255 - total
    if crc_value < 32:
        crc_value += 32
    return bytes([crc_value])



def get_graphix_parameter(group: int, parameter: int, uart: machine.UART):
    """
    Sends a parameter read request to the Graphix controller via UART.

    Args:
        - group (int): Parameter group identifier.
        - parameter (int): Parameter address within the group.
        - uart (machine.UART): Initialized UART interface.

    Returns:
        - bytes | None: Raw response bytes, or None if no response was received.
    """
    # Construct command string 
    command_str = f"{group}{SEPARATOR}{parameter}{SEPARATOR}"
    command_bytes = bytes([SI]) + command_str.encode("ascii")

    # Add checksum and End of Transmission (EoT)
    crc = calculate_crc(command_bytes)
    message = command_bytes + crc + bytes([EOT])

    print(f"DEBUG UART - Sending: {message}")

    # Transmit and wait for the controller answer
    uart.read()
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
    Parses a numeric value from the controller response.

    Args:
        - response (bytes): Raw UART response from the controller.

    Returns:
        - float | None: Parsed pressure value (mbar), or None if invalid.
    """

    # Basic sanity check: response must exist and be long enough
    if not response or len(response) < 5:
        return None

    try:
        # Decode bytes to ASCII and immediately strip control characters
        # commonly used by the controller protocol (ACK, SI, EOT, etc.)
        raw = response.decode("ascii", "ignore")
        clean_raw = raw.replace(chr(6), "").replace(chr(15), "").replace(chr(4), "")

        # Use a regular expression to extract a floating-point number
        match = re.search(r"([-+]?\d+\.\d+[eE][-+]?\d+)", clean_raw)

         # If no valid number is found, the response is considered invalid
        if not match:
            return None
        
         # Convert the extracted string to a float
        val = float(match.group(1))
        
        # Safety check:
        # On this type of controller, an exact or negative zero reading is often caused by communication noise
        # or parsing artifacts, not by a real physical measurement
        if val <= 0:
            return None
            
        return val
    
    except:
        return None



def setup_metrics():
    """
    Initializes all Prometheus metric objects.

    Args:
        - None

    Returns:
        - None
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
    Accepts HTTP connections and serves Prometheus metrics.

    Args:
        - s (socket.socket): Listening TCP socket.

    Returns:
        - None
    """
    global scraper_status
    conn = None
    try:
        s.settimeout(0.1) 
        conn, addr = s.accept()
    except OSError:
        return 

    try:
        # Let time for the switch data to arrive.
        utime.sleep_ms(50) 
        
        conn.settimeout(2.0)
        request = conn.recv(1024)

        # Answering every 'GET' requests to avoid "Empty reply"
        if request and b'GET' in request:
            metrics_body = []
            for name, metric in METRICS.items():
                metrics_body.append(str(metric))

            metrics_body.append(f"graphix_scraper_status{{status=\"{scraper_status}\"}} 1")
            body_content = '\n'.join(metrics_body) + '\n'

            # HTTP Header
            response_headers = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: text/plain; version=0.0.4; charset=utf-8\r\n"
                "Content-Length: {}\r\n"
                "Connection: close\r\n"
                "\r\n"
            ).format(len(body_content))

            conn.sendall(response_headers.encode('utf-8'))
            conn.sendall(body_content.encode('utf-8'))
            
            # Wait for the W5500 physical delay
            utime.sleep_ms(200) 

        else:
            # If the request is empty, send an error message instead of cutting connexion
            conn.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")

    except Exception as e:
        pass

    finally:
        if conn:
            conn.close()


def main_loop(uart):
    """
    Main runtime loop:
    - Periodically polls the Graphix controller
    - Updates metrics
    - Serves HTTP requests

    Args:
        - uart (machine.UART): Initialized UART interface.

    Returns:
        - None
    """
    global scraper_status

    interval = GLOBAL_CONFIG["scrap_interval"]
    port = GLOBAL_CONFIG["http_server_port"]
    
    # Listen on all available network interfaces
    addr = socket.getaddrinfo("0.0.0.0", port)[0][-1]

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(5) # Increased backlog to handle lab network traffic
    s.setblocking(False)

    # Initialize last scrape time so the first read happens immediately
    last_scrape_time = utime.time() - interval 

    while True:
        gc.collect()
        current_time = utime.time()

        # UART polling: performed ONLY when the configured interval has elapsed
        if current_time - last_scrape_time >= interval:
            last_scrape_time = current_time
            try:
                response = get_graphix_parameter(1, 29, uart) 
                new_value = parse_parameter_value(response)

                if new_value is not None:
                    METRICS["pressure"].set(new_value)
                    scraper_status = "running"
                else:
                    # No update is performed here, so METRICS["pressure"]
                    # keeps its previous value (e.g. 7.87e-06)
                    scraper_status = "parse_fail" 
            except Exception as e:
                scraper_status = "uart_fail"

        # Serve the HTTP metrics endpoint as frequently as possible
        serve_prometheus_metrics(s)

        # Short sleep to avoid maxing out the CPU
        utime.sleep_ms(10) 



def setup_network():
    """
    Initializes the W5500 Ethernet interface and waits for link establishment.

    Args:
        - None

    Returns:
        - str | bool: Assigned IP address on success, False on failure.
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