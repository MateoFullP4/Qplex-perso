import time
import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import argparse
import serial
import yaml
from prometheus_client import start_http_server, Gauge, Enum, Info


SI = 0x0F
EOT = 0x04
SEPARATOR = ';'
VERSION = "0.1"
NAME = "Graphix Prometheus Exporter"
ROOT = Path(os.path.dirname(__file__))
CONFIG_FILE_PATH = None
CONFIG = {}
METRICS = {}
GLOBAL_TAGS = {}

# ----------------------------
# Logger
# ----------------------------
fmt = "[%(asctime)s] - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(format=fmt, datefmt="%Y-%m-%d %H:%M:%S", level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------------------
# Functions
# ----------------------------
def file_path(string):
    if os.path.isfile(string):
        return Path(string)
    else:
        raise FileNotFoundError(string)

def load_config():
    global CONFIG, GLOBAL_TAGS
    with CONFIG_FILE_PATH.open() as file:
        CONFIG = yaml.safe_load(file)
    GLOBAL_TAGS = CONFIG["global"]["tags"]
    logger.info(f"Configuration loaded: {CONFIG}")

def calculate_crc(data: bytes) -> bytes:
    total = sum(data) % 256
    crc_value = 255 - total
    if crc_value < 32:
        crc_value += 32
    return bytes([crc_value])

def get_graphix_parameter(group: int, parameter: int, port: str, baudrate: int):
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
    except serial.SerialException as e:
        logger.error(f"Serial error: {e}")
        return None

def parse_parameter_value(response: bytes):
    if not response:
        return None
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

def setup_prometheus_server():
    global METRICS
    port = CONFIG["global"]["http_server_port"]
    start_http_server(port)
    logger.info(f"Prometheus HTTP server started on port {port}")

    # Info metric
    i = Info(
        name="program_information",
        documentation="Program information",
        labelnames=list(GLOBAL_TAGS.keys())
    )
    i.labels(**GLOBAL_TAGS).info({"name": NAME, "version": VERSION})

    # Status enum
    status = Enum(
        name="scraper_status",
        documentation="Scraper status",
        labelnames=list(GLOBAL_TAGS.keys()),
        states=["starting", "running", "error"]
    )
    status.labels(**GLOBAL_TAGS).state("starting")
    METRICS["status"] = status

    # Pressure gauge
    pressure = Gauge(
        name="pressure_value",
        documentation="Pressure gauge value",
        unit="Pa",
        labelnames=list(GLOBAL_TAGS.keys())
    )
    METRICS["pressure"] = pressure

def measure_and_update():
    global METRICS
    port = CONFIG["graphix"]["port"]
    baudrate = CONFIG["graphix"]["baudrate"]

    response = get_graphix_parameter(1, 29, port, baudrate)
    value = parse_parameter_value(response)

    if value is not None:
        METRICS["pressure"].labels(**GLOBAL_TAGS).set(value)
        METRICS["status"].labels(**GLOBAL_TAGS).state("running")
        logger.debug(f"Pressure: {value}")
    else:
        METRICS["status"].labels(**GLOBAL_TAGS).state("error")
        logger.warning("Failed to read pressure value")

def start_monitoring():
    interval = CONFIG["global"]["scrap_interval"]
    METRICS["status"].labels(**GLOBAL_TAGS).state("running")
    logger.info("Starting measurement loop...")
    while True:
        measure_and_update()
        time.sleep(interval)

# ----------------------------
# Main
# ----------------------------
def main():
    load_config()
    setup_prometheus_server()
    start_monitoring()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", type=file_path, help="Config file path")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.config:
        CONFIG_FILE_PATH = args.config
    else:
        CONFIG_FILE_PATH = ROOT / "config.yml"

    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")

    main()
