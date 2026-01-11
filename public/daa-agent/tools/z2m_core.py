"""
tools/z2m_core.py - Zigbee2MQTT Bridge for DAA
==============================================
Beskrivning: Läser sensorvärden via MQTT.
"""

import json
import paho.mqtt.subscribe as subscribe

# --- KONFIGURATION ---
# Ändra till IP-adressen där din MQTT-broker (Home Assistant/Mosquitto) körs.
BROKER_IP = "192.168.107.6"  # <--- ÄNDRA DENNA
BROKER_PORT = 1883
BASE_TOPIC = "zigbee2mqtt"

def get_sensor_data(friendly_name):
    """
    Hämtar data från en Zigbee-enhet baserat på dess 'Friendly Name'.
    Exempel på friendly_name: 'sensor_kok', 'vardagsrum_temp'
    """
    topic = f"{BASE_TOPIC}/{friendly_name}"
    print(f"[Z2M] Läser från topic: {topic}")

    try:
        # Vi lyssnar efter ETT meddelande (retained) med en timeout på 2 sekunder
        msg = subscribe.simple(topic, hostname=BROKER_IP, port=BROKER_PORT, timeout=2.0)

        if msg is None:
            return "Inget svar från sensorn (Timeout)."

        # Zigbee2MQTT skickar data som JSON: {"temperature": 21.5, "humidity": 50, ...}
        payload = msg.payload.decode("utf-8")
        data = json.loads(payload)

        # Vi formaterar om JSON till en läsbar sträng för AI:n
        readable_output = []
        for key, value in data.items():
            # Filtrera bort teknisk data som linkquality om du vill
            if key not in ["linkquality", "update_available"]:
                readable_output.append(f"{key}: {value}")

        return f"Sensorvärden för {friendly_name}: " + ", ".join(readable_output)

    except Exception as e:
        print(f"[Z2M ERROR] {e}")
        return f"Kunde inte läsa sensor: {str(e)}"