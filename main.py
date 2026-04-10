import random
import math
import statistics
import hashlib
import time
from dataclasses import dataclass
from typing import List, Dict, Optional

import matplotlib.pyplot as plt


SEED = 42
TIME_STEPS = 120
random.seed(SEED)


@dataclass
class GridState:
    demand: float
    solar: float
    wind: float
    total_generation: float
    storage_level: float
    frequency: float
    voltage: float
    controller_response: float
    sensor_load_reported: Optional[float]
    true_load: float
    served_energy: float
    unmet_demand: float
    energy_loss: float
    attack_detected: bool          # attack or communication issue noticed
    bad_data_used: bool            # corrupted data actually influenced controller
    packet_dropped: bool
    malicious_command_used: bool
    recovered_stably: bool


class SmartGridSimulator:
    def __init__(self, secure_mode: bool = False):
        self.secure_mode = secure_mode
        self.storage_capacity = 80.0
        self.storage_level = 40.0
        self.max_charge_rate = 12.0
        self.max_discharge_rate = 12.0
        self.generator_reserve = 20.0
        self.previous_valid_load = 50.0
        self.shared_secret = "smartgrid_secure_key"

    def demand_profile(self, t: int) -> float:
        base = 50 + 10 * math.sin(2 * math.pi * t / 24)
        noise = random.uniform(-3, 3)
        peak = 8 if 40 <= t <= 60 else 0
        return max(20, base + noise + peak)

    def solar_profile(self, t: int) -> float:
        daylight = max(0, math.sin(math.pi * ((t % 24) / 24)))
        noise = random.uniform(-2, 2)
        return max(0, 25 * daylight + noise)

    def wind_profile(self, t: int) -> float:
        base = 18 + 5 * math.sin(2 * math.pi * t / 18 + 1.2)
        noise = random.uniform(-4, 4)
        return max(5, base + noise)

    def sign_message(self, payload: str) -> str:
        return hashlib.sha256((payload + self.shared_secret).encode()).hexdigest()

    def verify_message(self, payload: str, signature: str) -> bool:
        return self.sign_message(payload) == signature

    def make_sensor_message(self, true_load: float) -> Dict:
        payload = f"{true_load:.3f}"
        signature = self.sign_message(payload)
        return {
            "payload": payload,
            "signature": signature,
            "auth": True,
            "dropped": False,
            "tampered": False,
        }

    def attack_false_data_injection(self, msg: Dict, bias_pct: float) -> Dict:
        tampered_load = float(msg["payload"]) * (1 + bias_pct / 100.0)
        msg["payload"] = f"{tampered_load:.3f}"
        msg["tampered"] = True
        return msg

    def attack_dos(self, msg: Dict, drop_probability: float) -> Dict:
        if random.random() < drop_probability:
            msg["dropped"] = True
        return msg

    def attack_unauthorized_command(self, legitimate_command: float) -> Dict:
        malicious = legitimate_command + random.uniform(-15, 15)
        return {
            "command": malicious,
            "auth": False,
        }

    def secure_receive_load(self, msg: Dict) -> Dict:
        result = {
            "accepted": False,
            "load_value": None,
            "attack_detected": False,
            "bad_data_used": False,
            "packet_dropped": msg["dropped"],
        }

        if msg["dropped"]:
            result["attack_detected"] = True
            result["accepted"] = True
            result["load_value"] = self.previous_valid_load
            # secure system uses fallback, so bad data was NOT used
            result["bad_data_used"] = False
            return result

        payload = msg["payload"]

        if not self.verify_message(payload, msg["signature"]):
            result["attack_detected"] = True
            result["accepted"] = True
            result["load_value"] = self.previous_valid_load
            result["bad_data_used"] = False
            return result

        load_value = float(payload)

        if abs(load_value - self.previous_valid_load) > 0.20 * max(1.0, self.previous_valid_load):
            result["attack_detected"] = True
            result["accepted"] = True
            result["load_value"] = self.previous_valid_load
            result["bad_data_used"] = False
            return result

        result["accepted"] = True
        result["load_value"] = load_value
        self.previous_valid_load = load_value
        return result

    def insecure_receive_load(self, msg: Dict) -> Dict:
        result = {
            "accepted": False,
            "load_value": None,
            "attack_detected": False,
            "bad_data_used": False,
            "packet_dropped": msg["dropped"],
        }

        if msg["dropped"]:
            result["attack_detected"] = True
            result["accepted"] = True
            result["load_value"] = self.previous_valid_load
            # stale/outdated information is still a data integrity problem
            result["bad_data_used"] = True
            return result

        load_value = float(msg["payload"])
        self.previous_valid_load = load_value
        result["accepted"] = True
        result["load_value"] = load_value

        if msg["tampered"]:
            result["attack_detected"] = True
            result["bad_data_used"] = True

        return result

    def controller(self, reported_load: float, renewable_supply: float) -> float:
        error = reported_load - renewable_supply
        command = max(-self.max_charge_rate, min(self.max_discharge_rate, 0.6 * error))
        return command

    def apply_control(self, command: float, renewable_supply: float, true_load: float) -> Dict:
        support = 0.0
        absorb = 0.0

        if command > 0:
            discharge = min(command, self.storage_level, self.max_discharge_rate)
            self.storage_level -= discharge
            support += discharge

            short_after_storage = max(0.0, true_load - (renewable_supply + support))
            reserve = min(short_after_storage, self.generator_reserve)
            support += reserve
        else:
            surplus = max(0.0, renewable_supply - true_load)
            charge = min(-command, surplus, self.storage_capacity - self.storage_level, self.max_charge_rate)
            self.storage_level += charge
            absorb = charge

        total_served = min(true_load, renewable_supply + support)
        unmet = max(0.0, true_load - total_served)

        excess = max(0.0, renewable_supply - true_load - absorb)
        energy_loss = excess + unmet * 0.15

        load_ratio = unmet / max(true_load, 1.0)
        frequency = 50.0 - 1.2 * load_ratio + random.uniform(-0.03, 0.03)
        voltage = 1.0 - 0.15 * load_ratio + random.uniform(-0.01, 0.01)

        stable = abs(frequency - 50.0) <= 0.2 and abs(voltage - 1.0) <= 0.05

        return {
            "served_energy": total_served,
            "unmet_demand": unmet,
            "energy_loss": energy_loss,
            "frequency": frequency,
            "voltage": voltage,
            "stable": stable,
        }

    def process_command(self, legitimate_command: float, malicious_override: Optional[Dict]) -> Dict:
        if malicious_override is None:
            return {"command_used": legitimate_command, "malicious_used": False}

        if self.secure_mode and malicious_override["auth"] is False:
            return {"command_used": legitimate_command, "malicious_used": False}

        return {"command_used": malicious_override["command"], "malicious_used": True}

    def step(
        self,
        t: int,
        fdi_active: bool = False,
        dos_active: bool = False,
        cmd_attack_active: bool = False,
    ) -> GridState:
        demand = self.demand_profile(t)
        solar = self.solar_profile(t)
        wind = self.wind_profile(t)
        total_generation = solar + wind

        msg = self.make_sensor_message(demand)

        if fdi_active:
            bias = random.uniform(10, 15)
            msg = self.attack_false_data_injection(msg, bias)

        if dos_active:
            msg = self.attack_dos(msg, drop_probability=0.30)

        start = time.perf_counter()

        if self.secure_mode:
            rx = self.secure_receive_load(msg)
        else:
            rx = self.insecure_receive_load(msg)

        reported_load = rx["load_value"]
        legit_command = self.controller(reported_load, total_generation)

        malicious = None
        if cmd_attack_active:
            malicious = self.attack_unauthorized_command(legit_command)

        processed = self.process_command(legit_command, malicious)
        final_command = processed["command_used"]

        control_result = self.apply_control(final_command, total_generation, demand)
        end = time.perf_counter()

        response_time = (end - start) * 1000
        if self.secure_mode:
            response_time += random.uniform(3.0, 8.0)
        else:
            response_time += random.uniform(1.0, 4.0)

        return GridState(
            demand=demand,
            solar=solar,
            wind=wind,
            total_generation=total_generation,
            storage_level=self.storage_level,
            frequency=control_result["frequency"],
            voltage=control_result["voltage"],
            controller_response=response_time,
            sensor_load_reported=reported_load,
            true_load=demand,
            served_energy=control_result["served_energy"],
            unmet_demand=control_result["unmet_demand"],
            energy_loss=control_result["energy_loss"],
            attack_detected=rx["attack_detected"],
            bad_data_used=rx["bad_data_used"],
            packet_dropped=rx["packet_dropped"],
            malicious_command_used=processed["malicious_used"],
            recovered_stably=control_result["stable"],
        )

    def run_scenario(self, scenario_name: str) -> Dict:
        states: List[GridState] = []

        for t in range(TIME_STEPS):
            fdi = False
            dos = False
            cmd = False

            if scenario_name == "baseline":
                pass
            elif scenario_name in ("attack", "secured"):
                if 20 <= t <= 45:
                    fdi = True
                if 50 <= t <= 75:
                    dos = True
                if 85 <= t <= 100:
                    cmd = True
            else:
                raise ValueError(f"Unknown scenario: {scenario_name}")

            state = self.step(
                t=t,
                fdi_active=fdi,
                dos_active=dos,
                cmd_attack_active=cmd,
            )
            states.append(state)

        return self.compute_metrics(states, scenario_name)

    def compute_metrics(self, states: List[GridState], scenario_name: str) -> Dict:
        total_demand = sum(s.true_load for s in states)
        total_served = sum(s.served_energy for s in states)
        total_loss = sum(s.energy_loss for s in states)
        stable_count = sum(1 for s in states if s.recovered_stably)

        bad_data_steps = sum(1 for s in states if s.bad_data_used)
        detected_steps = sum(1 for s in states if s.attack_detected)

        availability = 100.0 * sum(
            1 for s in states if s.unmet_demand <= 0.05 * s.true_load
        ) / len(states)

        # FIXED: integrity now means trustworthy data used by controller
        data_integrity = 100.0 * (len(states) - bad_data_steps) / len(states)

        avg_response_time = statistics.mean(s.controller_response for s in states)
        efficiency = 100.0 * total_served / max(total_demand + total_loss, 1e-6)
        frequency_deviation = statistics.mean(abs(s.frequency - 50.0) for s in states)
        voltage_deviation = statistics.mean(abs(s.voltage - 1.0) for s in states)

        malicious_command_count = sum(1 for s in states if s.malicious_command_used)
        packet_drop_count = sum(1 for s in states if s.packet_dropped)

        return {
            "scenario": scenario_name,
            "states": states,
            "availability": availability,
            "data_integrity": data_integrity,
            "avg_response_time_ms": avg_response_time,
            "energy_efficiency": efficiency,
            "stability_percent": 100.0 * stable_count / len(states),
            "avg_frequency_deviation": frequency_deviation,
            "avg_voltage_deviation": voltage_deviation,
            "malicious_command_count": malicious_command_count,
            "packet_drop_count": packet_drop_count,
            "detected_steps": detected_steps,
            "bad_data_steps": bad_data_steps,
            "total_unmet_demand": sum(s.unmet_demand for s in states),
            "total_energy_loss": total_loss,
        }


def print_summary(results: List[Dict]) -> None:
    print("\n" + "=" * 72)
    print("SMART GRID CYBERSECURITY SIMULATION RESULTS")
    print("=" * 72)
    for r in results:
        print(f"\nScenario: {r['scenario'].upper()}")
        print(f"  Availability (%):          {r['availability']:.2f}")
        print(f"  Data Integrity (%):        {r['data_integrity']:.2f}")
        print(f"  Avg Response Time (ms):    {r['avg_response_time_ms']:.2f}")
        print(f"  Energy Efficiency (%):     {r['energy_efficiency']:.2f}")
        print(f"  Stability (%):             {r['stability_percent']:.2f}")
        print(f"  Avg Freq Deviation (Hz):   {r['avg_frequency_deviation']:.4f}")
        print(f"  Avg Volt Deviation (p.u.): {r['avg_voltage_deviation']:.4f}")
        print(f"  Attack Steps Detected:     {r['detected_steps']}")
        print(f"  Bad Data Used:             {r['bad_data_steps']}")
        print(f"  Packet Drops:              {r['packet_drop_count']}")
        print(f"  Malicious Commands Used:   {r['malicious_command_count']}")
        print(f"  Total Unmet Demand:        {r['total_unmet_demand']:.2f}")
        print(f"  Total Energy Loss:         {r['total_energy_loss']:.2f}")


def plot_results(results: List[Dict]) -> None:
    scenarios = [r["scenario"].capitalize() for r in results]
    x = range(len(results))
    width = 0.18

    availability = [r["availability"] for r in results]
    integrity = [r["data_integrity"] for r in results]
    efficiency = [r["energy_efficiency"] for r in results]
    stability = [r["stability_percent"] for r in results]

    plt.figure(figsize=(10, 6))
    plt.bar([i - 1.5 * width for i in x], availability, width=width, label="Availability (%)")
    plt.bar([i - 0.5 * width for i in x], integrity, width=width, label="Data Integrity (%)")
    plt.bar([i + 0.5 * width for i in x], efficiency, width=width, label="Energy Efficiency (%)")
    plt.bar([i + 1.5 * width for i in x], stability, width=width, label="Stability (%)")
    plt.xticks(list(x), scenarios)
    plt.ylabel("Percentage")
    plt.title("Smart Grid Resilience and Optimization Metrics")
    plt.legend()
    plt.tight_layout()

    plt.figure(figsize=(8, 5))
    response = [r["avg_response_time_ms"] for r in results]
    plt.bar(scenarios, response)
    plt.ylabel("Milliseconds")
    plt.title("Average Controller Response Time")
    plt.tight_layout()

    plt.figure(figsize=(10, 6))
    bad_data = [r["bad_data_steps"] for r in results]
    malicious = [r["malicious_command_count"] for r in results]
    unmet = [r["total_unmet_demand"] for r in results]

    plt.bar([i - width for i in x], bad_data, width=width, label="Bad Data Used")
    plt.bar(x, malicious, width=width, label="Malicious Commands Used")
    plt.bar([i + width for i in x], unmet, width=width, label="Total Unmet Demand")
    plt.xticks(list(x), scenarios)
    plt.ylabel("Count / Energy Units")
    plt.title("Attack Impact Indicators")
    plt.legend()
    plt.tight_layout()

    attack = next(r for r in results if r["scenario"] == "attack")
    secured = next(r for r in results if r["scenario"] == "secured")

    labels = ["Availability", "Integrity", "Efficiency", "Stability"]
    improvements = [
        secured["availability"] - attack["availability"],
        secured["data_integrity"] - attack["data_integrity"],
        secured["energy_efficiency"] - attack["energy_efficiency"],
        secured["stability_percent"] - attack["stability_percent"],
    ]

    plt.figure(figsize=(8, 5))
    plt.bar(labels, improvements)
    plt.ylabel("Improvement Points")
    plt.title("Improvement After Cybersecurity Controls")
    plt.tight_layout()

    plt.show()


def main():
    baseline_sim = SmartGridSimulator(secure_mode=False)
    baseline_results = baseline_sim.run_scenario("baseline")

    attack_sim = SmartGridSimulator(secure_mode=False)
    attack_results = attack_sim.run_scenario("attack")

    secured_sim = SmartGridSimulator(secure_mode=True)
    secured_results = secured_sim.run_scenario("secured")

    results = [baseline_results, attack_results, secured_results]
    print_summary(results)
    plot_results(results)


if __name__ == "__main__":
    main()