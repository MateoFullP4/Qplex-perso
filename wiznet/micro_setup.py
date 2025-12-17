import utime
import usocket as socket
import machine
import sys
import random


from config import (
    GLOBAL_CONFIG, GRAPHIX_CONFIG, NETWORK_CONFIG,
    SI, EOT, SEPARATOR, VERSION, NAME)

pressure_value = None
scraper_status = "starting"
METRICS = {}


class uGauge:
    def __init__(self, name, documentation, unit, tags):
        self.name = name
        self.documentation = documentation
        self.unit = unit
        self.labels = self._format_labels(tags)
        self.value = 0

    def _format_labels(self, tags):
        return ','.join(['{k}="{v}"'.format(k=k, v=v) for k, v in tags.items()])

    def set(self, value):
        self.value = value
        
    def __str__(self):
        output = [
            "# HELP {} {}".format(self.name, self.documentation),
            "# TYPE {} gauge".format(self.name),
            "{}{{{}}} {}".format(self.name, self.labels, self.value)
        ]
        return '\n'.join(output)


def log(level, message):
    # Get current time tuple: (year, month, mday, hour, minute, second, weekday, yearday)
    time_tuple = utime.localtime() 
    
    # Format the hour, minute, and second into an 'HH:MM:SS' string format 
    timestamp = "{:02d}:{:02d}:{:02d}".format(time_tuple[3], time_tuple[4], time_tuple[5])
    
    print("[{}] - {} - {}".format(timestamp, level, message))


def calculate_crc(data: bytes) -> bytes:
    # Calculates the CRC for the Graphix bytes protocol
    total = sum(data) % 256
    crc_value = 255 - total
    if crc_value < 32:
        crc_value += 32
    return bytes([crc_value])


def get_graphix_parameter(group: int, parameter: int, uart_port: machine.UART):
    # Simulating pressure reading from the pressure gauge, around 1000 Pa
    utime.sleep_ms(200) 

    # Pin adress of the Graphix controller    
    if group == 1 and parameter == 29: 
        # Generate a random value in the range 995.0 to 1005.0
        mock_value = 1000.0 + (random.random() * 10.0 - 5.0) 
        response_str = f"{mock_value:.3f}{SEPARATOR}" 
        # Returning value string in ascii to simulate the gauge response
        return response_str.encode('ascii') + bytes([EOT])
    else:
        log("WARNING", f"Mock called for unknown parameter ({group}, {parameter})")
        return None

def parse_parameter_value(response: bytes):
    # Parses the simulated value to extract the numerical response
    global scraper_status
    
    if not response:
        return None
        
    # Find the start of the data 
    body = response
    
    # Remove EOT if present
    if body and body[-1] == EOT:
        body = body[:-1]

    try:
        body_str = body.decode('ascii').strip()
        parts = body_str.split(SEPARATOR)
        if len(parts) >= 1:
            value_str = parts[0]
            return float(value_str)
        
    except ValueError as e:
        log("ERROR", f"Could not parse '{body_str}' into a float: {e}")
        scraper_status = "error"
        return None
    except Exception as e:
        log("ERROR", f"Parsing failed: {e}")
        scraper_status = "error"
        return None


def setup_metrics():
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
    global scraper_status
    conn, addr = s.accept()
    # Set a timeout for reading the request
    try:
        request = conn.recv(1024)
        if request:
            log("DEBUG", f"Request received from {addr[0]}")
            if b'GET /metrics' in request:
                metrics_body = []
                for name, metric in METRICS.items():
                    metrics_body.append(str(metric))
                metrics_body.append(f"graphix_scraper_status{{status=\"{scraper_status}\"}} 1")
                body_content = '\n'.join(metrics_body) + '\n'
                response_headers = [
                    "HTTP/1.1 200 OK",
                    "Content-Type: text/plain; version=0.0.4; charset=utf-8",
                    f"Content-Length: {len(body_content)}",
                    "Connection: close",
                    "\r\n"
                ]
                response = '\r\n'.join(response_headers).encode('utf-8') + body_content.encode('utf-8')
                conn.sendall(response)
            else:
                conn.sendall(b"HTTP/1.1 404 Not Found\r\n\r\n")
    except Exception as e:
        log("ERROR", f"Socket handling error: {e}")
    finally:
        conn.close()


def main_loop(uart):
    global pressure_value, scraper_status

    interval = GLOBAL_CONFIG["scrap_interval"]
    port = GLOBAL_CONFIG["http_server_port"]
    tags = GLOBAL_CONFIG["tags"]
    addr = socket.getaddrinfo("0.0.0.0", port)[0]

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr[-1])
    s.listen(1)
    log("INFO", f"Prometheus HTTP server listening on port {port}")
    last_scrape_time = utime.time() - interval 
    while True:
        current_time = utime.time()
        if current_time - last_scrape_time >= interval:
            last_scrape_time = current_time
            log("DEBUG", "Measuring and updating pressure...")
            response = get_graphix_parameter(1, 29, uart) 
            value = parse_parameter_value(response)
            if value is not None:
                METRICS["pressure"].set(value)
                scraper_status = "running"
                log("INFO", f"Pressure: {value}")
            else:
                scraper_status = "error"
                log("WARNING", "Failed to read pressure value")
        try:
            serve_prometheus_metrics(s)
        except OSError as e:
            if e.args[0] != 11: 
                log("ERROR", f"Socket accept error: {e}")
        utime.sleep_ms(100) 



def setup_network():
    # Initializes the W5500 Ethernet controller with Static IP.

    import network
    from machine import Pin, SPI # Keep Pin and SPI imported
    
    # Define Pin objects for cs/rst
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

    # Network Interface Initialization 

    nic = network.WIZNET5K(
        spi, 
        cs_pin_obj,   
        rst_pin_obj,   
    )
    
    # Handle Static IP 
    if "static_ip" in NETWORK_CONFIG:
        nic.active(True) # Must be active before config
        nic.ifconfig(NETWORK_CONFIG["static_ip"])
        ip_addr = nic.ifconfig()[0]
    else:
        log("ERROR", "Static IP configuration missing, but required for direct link.")
        return False

    log("INFO", "Waiting for Ethernet link...")
    max_wait = 10
    while not nic.isconnected() and max_wait > 0:
        utime.sleep(1)
        max_wait -= 1
        
    if nic.isconnected():
        log("INFO", f"Ethernet connected! Static IP: {ip_addr}")
        return ip_addr # Return the IP address
    else:
        log("ERROR", "Failed to connect to Ethernet.")
        return False



if __name__ == "__main__":
    ip_address = setup_network() # Get the IP address
    if not ip_address:
        sys.exit(1) # Exit if networking fails
    
    # Initialize Metrics
    setup_metrics()

    # Initialize UART
    uart = machine.UART(
        GRAPHIX_CONFIG["uart_id"], 
        baudrate=GRAPHIX_CONFIG["baudrate"], 
        tx=machine.Pin(GRAPHIX_CONFIG["tx_pin"]), 
        rx=machine.Pin(GRAPHIX_CONFIG["rx_pin"])
    )
    log("INFO", f"UART {GRAPHIX_CONFIG['uart_id']} initialized (MOCK MODE).")
    log("SUCCESS", f"Metrics available at http://{ip_address}:{GLOBAL_CONFIG['http_server_port']}/metrics")
    
    # Start Main Loop
    main_loop(uart)