"""
Graphix One Prometheus Exporter

This script interfaces with a Leybold Graphix One controller over a serial 
connection in order to read pressure values and expose them as Prometheus metrics.

The program:
- Implements the Graphix One serial communication protocol (SI, CRC, EOT framing)
- Periodically queries a specified parameter from the controller
- Parses the returned scientific-notation value
- Exposes the pressure measurement via an HTTP endpoint compatible with Prometheus
- Provides status monitoring (starting / running / error states)
- Loads configuration parameters from a YAML file

Unlike early draft versions, this script runs as a continuous monitoring service 
and starts an embedded HTTP server for metric scraping.

Configuration (serial port, baudrate, scrape interval, HTTP port, and global tags) 
is defined in a config.yml file and can be overridden via command-line arguments.

Note:
- The serial PORT value depends on the operating system (e.g., COMx on Windows, 
  /dev/ttyUSBx or /dev/ttyACMx on Linux).
- This script is designed to run on a standard Python environment and is not 
  directly compatible with MicroPython-based boards.
"""

import time
import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import argparse
import serial
import yaml
from prometheus_client import start_http_server, Gauge, Enum, Info

# --- Protocol Constants ---
SI = 0x0F        # Start Header (Shift In)
EOT = 0x04       # End Of Transmission
SEPARATOR = ';'  # Delimiter for Group/Parameter commands

# --- Metadata ---
VERSION = "0.1"
NAME = "Graphix Prometheus Exporter"
ROOT = Path(os.path.dirname(__file__))

# --- Global State ---
CONFIG_FILE_PATH = None
CONFIG = {}
METRICS = {}
GLOBAL_TAGS = {}

# --- Logger Configuration ---
fmt = "[%(asctime)s] - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(format=fmt, datefmt="%Y-%m-%d %H:%M:%S", level=logging.INFO)
logger = logging.getLogger(__name__)


def file_path(path: str):
    """
    Checks if a string path is a valid existing file
    Args:
        path (str): path to the file
    """
    if os.path.isfile(path):
        return Path(path)
    else:
        raise FileNotFoundError(path)
    

def load_config():
    """
    Loads the .yaml configuration and initializes global metadata tags. 
    """
    global CONFIG, GLOBAL_TAGS
    with CONFIG_FILE_PATH.open() as file:
        CONFIG = yaml.safe_load(file)
    GLOBAL_TAGS = CONFIG["global"]["tags"]
    logger.info(f"Configuration loaded: {CONFIG}")


def calculate_crc(data: bytes) -> bytes:
    """
    Calculates the bit checksum for the Graphix One protocol. 
    Please note that this protocol is detailled in the manual. 
    Args:
        data (bytes): address sent to the Graphix One in bytes 
    """
    total = sum(data) % 256
    crc_value = 255 - total
    if crc_value < 32:
        crc_value += 32
    return bytes([crc_value])


def get_graphix_parameter(group: int, parameter: int, port: str, baudrate: int):
    """
    Enable communication with the Graphix One through a Serial protocol. 
    Constructs the frame: [SI] + data + [CRC] + [EOT]
    Args:
        group (int): group of the parameter we want to access
        parameter (int): address within the group of the parameter
        port (str): port of the serial connection (can vary between Windows and Linux)
        baudrate (int): can be read on the screen of the Graphix One (by default 9600)
    """
    try:
        with serial.Serial(port, baudrate, timeout=1) as ser:
            command_str = f"{group}{SEPARATOR}{parameter}{SEPARATOR}"
            command_bytes = bytes([SI]) + command_str.encode('ascii')
            crc = calculate_crc(command_bytes)
            message = command_bytes + crc + bytes([EOT])

            ser.write(message)
            time.sleep(0.2) # Hardware processing delay

            response = ser.read_all()
            if not response:
                return None
            
            # Trim EOT from the end of response
            if response[-1] == EOT:
                response = response[:-1]
            return response
    except serial.SerialException as e:
        logger.error(f"Serial error: {e}")
        return None
    

def parse_parameter_value(response: bytes):
    """
    Extracts a float value from the controller's byte response.
    Args: 
        response (bytes): raw response of the Graphix One. 
    """
    if not response:
        return None
    
    body = response
    if body[0] == 0x06:  # Strip ASCII Acknowledge (ACK)
        body = body[1:]
    if body[-1] == 0x04:  # Strip EOT if present in body
        body = body[:-1]

    # Filter for characters valid in a scientific notation float
    value_str = ''.join([chr(b) for b in body if chr(b) in '0123456789.-+eE'])
    try:
        return float(value_str)
    except:
        return None


def setup_prometheus_server():
    """
    Initializes the HTTP server and defines the metrics.
    """
    global METRICS
    port = CONFIG["global"]["http_server_port"]
    start_http_server(port)
    logger.info(f"Prometheus HTTP server started on port {port}")

    # Static metadata about the program
    i = Info(
        name="program_information",
        documentation="Program information",
        labelnames=list(GLOBAL_TAGS.keys())
    )
    i.labels(**GLOBAL_TAGS).info({"name": NAME, "version": VERSION})

    # Tracks the status of the scraper
    status = Enum(
        name="scraper_status",
        documentation="Scraper status",
        labelnames=list(GLOBAL_TAGS.keys()),
        states=["starting", "running", "error"]
    )
    status.labels(**GLOBAL_TAGS).state("starting")
    METRICS["status"] = status

    # Primary data point (in Pascals)
    pressure = Gauge(
        name="pressure_value",
        documentation="Pressure gauge value",
        unit="Pa",
        labelnames=list(GLOBAL_TAGS.keys())
    )
    METRICS["pressure"] = pressure


def measure_and_update():
    """
    Single tick of the measurement cycle: Read -> Parse -> Export.
    """
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
    """
    Infinitely loops based on the configured scrap interval.
    """
    interval = CONFIG["global"]["scrap_interval"]
    METRICS["status"].labels(**GLOBAL_TAGS).state("running")
    logger.info("Starting measurement loop...")
    while True:
        measure_and_update()
        time.sleep(interval)


def main():
    load_config()
    setup_prometheus_server()
    start_monitoring()


if __name__ == "__main__":
    # --- Command Line Argument Parsing ---
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", type=file_path, help="Config file path")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    # Determine config path
    if args.config:
        CONFIG_FILE_PATH = args.config
    else:
        CONFIG_FILE_PATH = ROOT / "config.yml"

    # Set log level based on --debug flag
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")

    main()
