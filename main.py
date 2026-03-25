import attacks
import config
import metrics
import security
from models import (
    CommunicationLayer,
    Controller,
    LoadModel,
    RenewableGenerator,
    SensorModel,
    SmartGrid,
)
from utils import (
    plot_metric_comparison,
    plot_timeseries,
    save_logs_to_csv,
    save_metrics_to_csv,
)


def run_simulation(
    scenario_name: str,
    attack_type: str = "none",
    security_enabled: bool = False,
) -> list[dict]:
    generator = RenewableGenerator()
    load_model = LoadModel()
    sensors = SensorModel()
    controller = Controller()
    grid = SmartGrid()
    comms = CommunicationLayer()
    detector = security.AnomalyDetector()

    logs = []
    last_safe_packet = None

    for t in range(config.SIMULATION_STEPS):
        solar, wind, total_generation = generator.total_output(t)
        true_load = load_model.get_load(t)

        base_control = {
            "reserve_dispatch": 0.0,
            "storage_dispatch": 0.0,
            "load_shed": 0.0,
            "source_id": config.AUTH_TOKEN,
        }

        true_state = grid.update_state(t, solar, wind, true_load, base_control)
        sensor_packet = sensors.read_all(true_state)

        if security_enabled:
            sensor_packet = security.sign_message(sensor_packet)

        transmitted_packet = comms.transmit(sensor_packet)

        if attack_type in ("fdi", "dos_drop", "dos_delay"):
            transmitted_packet, _ = attacks.apply_attack(
                attack_type=attack_type,
                sensor_data=transmitted_packet,
                control_action=None,
                t=t,
                comm_layer=comms,
            )

        # ----- New metric flags -----
        packet_received = transmitted_packet is not None
        packet_tampered = False
        controller_data_trusted = False

        anomaly_detected = False
        auth_ok = True
        ranges_ok = True
        used_fallback = False

        # Detect whether the incoming packet was tampered with
        if packet_received:
            if attack_type == "fdi":
                # FDI changes sensor values directly
                packet_tampered = abs(transmitted_packet["load"] - true_load) > 1e-6
            else:
                packet_tampered = False

        if security_enabled:
            incoming_packet_valid = False

            if transmitted_packet is not None:
                checksum_ok = security.verify_message(transmitted_packet)
                ranges_ok = security.validate_sensor_ranges(transmitted_packet)
                anomaly_detected = detector.detect(transmitted_packet)

                incoming_packet_valid = checksum_ok and ranges_ok and (not anomaly_detected)

            if incoming_packet_valid:
                controller_packet = transmitted_packet
                controller_data_trusted = True
            else:
                controller_packet = security.fallback_sensor_packet(last_safe_packet, None)
                used_fallback = controller_packet is not None
                controller_data_trusted = used_fallback
        else:
            # No security: controller trusts whatever arrives
            controller_packet = transmitted_packet
            controller_data_trusted = packet_received and (not packet_tampered)

        if controller_packet is None:
            controller_packet = {
                "time_step": t,
                "load": true_load,
                "generation": total_generation,
                "voltage": config.NOMINAL_VOLTAGE,
                "frequency": config.NOMINAL_FREQUENCY,
            }
            used_fallback = True
            controller_data_trusted = False

        control_action = controller.compute_control(controller_packet)

        if attack_type == "cmd_injection":
            _, control_action = attacks.apply_attack(
                attack_type=attack_type,
                sensor_data=controller_packet,
                control_action=control_action,
                t=t,
                comm_layer=comms,
            )

        if security_enabled:
            auth_ok = security.authenticate_command(control_action)
            command_ranges_ok = security.validate_command_ranges(control_action)

            if not auth_ok or not command_ranges_ok:
                control_action = security.fallback_command()

        final_state = grid.update_state(t, solar, wind, true_load, control_action)

        if security_enabled and controller_data_trusted and not used_fallback:
            last_safe_packet = controller_packet.copy()

        log_row = {
            "time_step": t,
            "scenario": scenario_name,
            "attack_type": attack_type,
            "security_enabled": security_enabled,
            "solar_generation": final_state.solar_generation,
            "wind_generation": final_state.wind_generation,
            "total_generation": final_state.total_generation,
            "true_load": final_state.true_load,
            "reported_load": controller_packet["load"],
            "served_load": final_state.served_load,
            "unmet_demand": final_state.unmet_demand,
            "reserve_used": final_state.reserve_used,
            "storage_used": final_state.storage_used,
            "load_shed": final_state.load_shed,
            "voltage": final_state.voltage,
            "frequency": final_state.frequency,
            "imbalance": final_state.imbalance,
            "packet_received": packet_received,
            "packet_tampered": packet_tampered,
            "controller_data_trusted": controller_data_trusted,
            "used_fallback": used_fallback,
            "anomaly_detected": anomaly_detected,
            "command_authenticated": auth_ok,
        }
        logs.append(log_row)

    return logs


def main():
    scenarios = [
        ("baseline", "none", False),
        ("fdi_attack", "fdi", False),
        ("dos_drop_attack", "dos_drop", False),
        ("dos_delay_attack", "dos_delay", False),
        ("cmd_injection_attack", "cmd_injection", False),
        ("secured_fdi", "fdi", True),
        ("secured_dos_drop", "dos_drop", True),
        ("secured_dos_delay", "dos_delay", True),
        ("secured_cmd_injection", "cmd_injection", True),
    ]

    all_metrics = []

    for scenario_name, attack_type, security_enabled in scenarios:
        logs = run_simulation(
            scenario_name=scenario_name,
            attack_type=attack_type,
            security_enabled=security_enabled,
        )

        save_logs_to_csv(logs, f"{scenario_name}.csv")
        plot_timeseries(logs, scenario_name)

        summary = metrics.summarize_metrics(logs, scenario_name)
        all_metrics.append(summary)
        print(summary)

    save_metrics_to_csv(all_metrics, "summary_metrics.csv")
    plot_metric_comparison(all_metrics)


if __name__ == "__main__":
    main()