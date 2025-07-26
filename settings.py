# Site configuration
site_name = "ol-pejeta"

vehicle_settings = [
    {
        "type": "drone",
        "id": 1,
        "connection": "172.17.240.1",
        "port": "14550",
        "protocol": "udp",
        "home_location": {"lat": 0.0271556, "lon": 36.903084, "alt": 10},
    },
    {
        "type": "car",
        "id": 2,
        "connection": "172.17.240.1",
        "port": "14570",
        "protocol": "udp",
        "home_location": {"lat": 0.0274684, "lon": 36.902941, "alt": 10},
    },
    {
        "type": "operator",
        "connection": "127.0.0.1",
        "port": "COM6",
        "baud_rate": "115200",
        "protocol": "serial",
    },
]
