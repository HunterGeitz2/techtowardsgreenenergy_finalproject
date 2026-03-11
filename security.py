import hashlib
from collections import deque

import config


def sign_message(packet: dict) -> dict:
    packet = packet.copy()
    payload = f"{packet.get('time_step')}|{packet.get('load')}|{packet.get('generation')}|{packet.get('voltage')}|{packet.get('frequency')}|{config.INTEGRITY_SECRET}"
    packet["checksum"] = hashlib.sha256(payload.encode()).hexdigest()
    return packet


def verify_message(packet: dict) -> bool:
    if packet is None or "checksum" not in packet:
        return False

    payload = f"{packet.get('time_step')}|{packet.get('load')}|{packet.get('generation')}|{packet.get('voltage')}|{packet.get('frequency')}|{config.INTEGRITY_SECRET}"
    expected = hashlib.sha256(payload.encode()).hexdigest()
    return expected == packet["checksum"]


def authenticate_command(control_action: dict) -> bool:
    return control_action.get("source_id") == config.AUTH_TOKEN


def validate_sensor_ranges(packet: dict) -> bool:
    if packet["load"] < 0:
        return False
    if packet["generation"] < 0:
        return False
    if not (45.0 <= packet["frequency"] <= 55.0):
        return False
    if not (0.8 <= packet["voltage"] <= 1.2):
        return False
    return True


class AnomalyDetector:
    def __init__(self, window_size: int = 5):
        self.recent_loads = deque(maxlen=window_size)

    def detect(self, packet: dict) -> bool:
        anomaly = False

        if self.recent_loads:
            previous = self.recent_loads[-1]
            if previous > 0:
                relative_jump = abs(packet["load"] - previous) / previous
                if relative_jump > config.ANOMALY_LOAD_JUMP:
                    anomaly = True

        if abs(packet["frequency"] - config.NOMINAL_FREQUENCY) > config.ANOMALY_FREQ_DEV:
            anomaly = True

        if abs(packet["voltage"] - config.NOMINAL_VOLTAGE) > config.ANOMALY_VOLT_DEV:
            anomaly = True

        self.recent_loads.append(packet["load"])
        return anomaly


def validate_command_ranges(control_action: dict) -> bool:
    if control_action["reserve_dispatch"] < 0 or control_action["reserve_dispatch"] > config.RESERVE_MAX:
        return False
    if control_action["storage_dispatch"] < 0 or control_action["storage_dispatch"] > config.STORAGE_MAX:
        return False
    if control_action["load_shed"] < 0 or control_action["load_shed"] > config.MAX_LOAD_SHED:
        return False
    return True


def fallback_sensor_packet(last_safe_packet: dict | None, current_packet: dict | None) -> dict | None:
    if current_packet is None:
        return last_safe_packet
    return current_packet


def fallback_command() -> dict:
    return {
        "reserve_dispatch": 0.0,
        "storage_dispatch": 0.0,
        "load_shed": 0.0,
        "source_id": config.AUTH_TOKEN,
    }