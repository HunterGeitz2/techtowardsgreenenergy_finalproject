import random

import config


def false_data_injection(sensor_data: dict) -> dict:
    attacked = sensor_data.copy()
    bias = random.uniform(config.FDI_BIAS_MIN, config.FDI_BIAS_MAX)
    attacked["load"] = attacked["load"] * (1 + bias)
    attacked["attack_flag"] = "FDI"
    attacked["fdi_bias"] = bias
    return attacked


def dos_attack_drop(packet: dict) -> dict | None:
    if random.random() < config.DOS_DROP_RATE:
        return None
    packet = packet.copy()
    packet["attack_flag"] = "DoS"
    return packet


def dos_attack_delay(comm_layer, packet: dict) -> dict | None:
    delayed_packet = comm_layer.transmit_with_delay(packet, config.DOS_DELAY_STEPS)
    if delayed_packet is not None:
        delayed_packet = delayed_packet.copy()
        delayed_packet["attack_flag"] = "DoS_DELAY"
    return delayed_packet


def command_injection(control_action: dict, t: int) -> dict:
    malicious = control_action.copy()
    if config.CMD_ATTACK_START <= t <= config.CMD_ATTACK_END:
        malicious["reserve_dispatch"] *= config.CMD_MALICIOUS_SCALE
        malicious["storage_dispatch"] *= config.CMD_MALICIOUS_SCALE
        malicious["load_shed"] = 0.0
        malicious["source_id"] = "attacker"
        malicious["attack_flag"] = "CMD_INJECTION"
    return malicious


def apply_attack(attack_type: str, sensor_data: dict, control_action: dict | None = None, t: int = 0, comm_layer=None):
    if attack_type == "fdi":
        return false_data_injection(sensor_data), control_action
    if attack_type == "dos_drop":
        return dos_attack_drop(sensor_data), control_action
    if attack_type == "dos_delay":
        return dos_attack_delay(comm_layer, sensor_data), control_action
    if attack_type == "cmd_injection" and control_action is not None:
        return sensor_data, command_injection(control_action, t)
    return sensor_data, control_action