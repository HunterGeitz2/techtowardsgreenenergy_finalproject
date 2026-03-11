import config


def calculate_availability(logs: list[dict]) -> float:
    if not logs:
        return 0.0
    good_steps = sum(1 for row in logs if row["unmet_demand"] <= 0.01)
    return 100.0 * good_steps / len(logs)


def calculate_data_integrity(logs: list[dict]) -> float:
    if not logs:
        return 0.0
    intact = sum(1 for row in logs if row["data_integrity_ok"])
    return 100.0 * intact / len(logs)


def calculate_energy_efficiency(logs: list[dict]) -> float:
    total_load = sum(row["true_load"] for row in logs)
    total_served = sum(row["served_load"] for row in logs)
    if total_load <= 0:
        return 0.0
    return 100.0 * total_served / total_load


def calculate_average_response_time(logs: list[dict]) -> float:
    recovery_times = []
    attack_active = False
    recovery_counter = 0

    for row in logs:
        under_attack = row["attack_type"] != "none"

        stable = (
            config.FREQUENCY_MIN <= row["frequency"] <= config.FREQUENCY_MAX
            and config.VOLTAGE_MIN <= row["voltage"] <= config.VOLTAGE_MAX
            and row["unmet_demand"] <= 0.01
        )

        if under_attack and not attack_active:
            attack_active = True
            recovery_counter = 0

        if attack_active:
            recovery_counter += 1
            if stable:
                recovery_times.append(recovery_counter)
                attack_active = False

    if not recovery_times:
        return 0.0
    return sum(recovery_times) / len(recovery_times)


def summarize_metrics(logs: list[dict], scenario_name: str) -> dict:
    return {
        "scenario": scenario_name,
        "availability_percent": round(calculate_availability(logs), 2),
        "data_integrity_percent": round(calculate_data_integrity(logs), 2),
        "energy_efficiency_percent": round(calculate_energy_efficiency(logs), 2),
        "average_response_time_steps": round(calculate_average_response_time(logs), 2),
    }