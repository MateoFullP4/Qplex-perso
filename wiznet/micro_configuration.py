"""
This file centralizes all configuration parameters used by main.py.

It is intended to improve readability and maintainability by separating
hardware, network, and application settings from the program logic.

The configuration includes:
- Global application settings (scrape interval, HTTP port, metric labels)
- UART parameters for communication with the Graphix controller
- SPI and Ethernet parameters for the W5500 network interface
- Protocol constants used by the Graphix RS232 communication

Modifying this file allows the behavior of the application to be adjusted
without changing the main program code.
"""


GLOBAL_CONFIG = {
    "http_server_port": 8080, # Port to the Prometheus server
    "scrap_interval": 5,     
    "tags": {             
        "location": "Turbo pump",
        "gauge_id": "graphix001", 
        "device": "IONIVAC ITR 90"
    }
}


GRAPHIX_CONFIG = {
    "uart_id": 0,           
    "tx_pin": 0,           
    "rx_pin": 1,           
    "baudrate": 9600        
}


NETWORK_CONFIG = {
        "spi_id": 0,
        "cs_pin": 17,    
        "rst_pin": 20,   
        "mac_address": b'\x02\x8a\x2b\x63\x43\x21', 
        "static_ip": ('10.42.0.11', '255.255.255.0', '10.42.0.1', '8.8.8.8')
    }


SI = 0x0F
EOT = 0x04
SEPARATOR = ';'

VERSION = "0.2-micropython"
NAME = "Graphix_uProm_Exporter"