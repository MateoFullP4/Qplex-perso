# micro_configuration.py : (SAVE AS config.py ON DEVICE)
# MicroPython Configuration for Graphix Prometheus Exporter

# --- Global Settings ---
GLOBAL_CONFIG = {
    "http_server_port": 8080, # Port to serve Prometheus metrics on
    "scrap_interval": 5,      # Seconds between reading the gauge
    "tags": {                 # Global labels for Prometheus metrics
        "location": "lab_a",
        "gauge_id": "graphix001"
    }
}

# --- Serial Gauge Settings (Graphix) ---
GRAPHIX_CONFIG = {
    "uart_id": 0,           
    "tx_pin": 0,            # Recommended: GPIO 0 (Pin 1 on Pico Header)
    "rx_pin": 1,            # Recommended: GPIO 1 (Pin 2 on Pico Header)
    "baudrate": 9600        
}

# --- Networking (Wiznet/ESP Setup) ---
NETWORK_CONFIG = {
        "spi_id": 0,
        "cs_pin": 17,    # Chip Select Pin (CS) for the W5500
        "rst_pin": 20,   # Reset Pin (RST) for the W5500
        "mac_address": b'\x02\x8a\x2b\x63\x43\x21', # Unique MAC address
        
        # --- STATIC IP CONFIGURATION (for direct PC connection) ---
        # Format: (IP Address, Subnet Mask, Gateway, DNS Server)
        # Gateway and DNS don't matter for a direct link, but they must be set.
        "static_ip": ('192.168.10.10', '255.255.255.0', '192.168.10.1', '8.8.8.8')
    }

# --- Gauge Protocol Constants ---
SI = 0x0F
EOT = 0x04
SEPARATOR = ';'

VERSION = "0.2-micropython"
NAME = "Graphix_uProm_Exporter"