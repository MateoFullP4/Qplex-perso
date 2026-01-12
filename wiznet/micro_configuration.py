"""
This file only serves as an easier and more readable way to code main.py
All the parameters needed are written here for a more modular code. 
"""

GLOBAL_CONFIG = {
    "http_server_port": 8080, # Port to the Prometheus server
    "scrap_interval": 5,     
    "tags": {             
        "location": "lab_a",
        "gauge_id": "graphix001"
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
        "static_ip": ('192.168.10.10', '255.255.255.0', '192.168.10.1', '8.8.8.8')
    }


SI = 0x0F
EOT = 0x04
SEPARATOR = ';'

VERSION = "0.2-micropython"
NAME = "Graphix_uProm_Exporter"