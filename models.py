import math
import random
from dataclasses import dataclass, asdict

import config


@dataclass
class GridState:
    time_step: int
    solar_generation: float
    wind_generation: float
    total_generation: float
    true_load: float
    served_load: float
    unmet_demand: float
    reserve_used: float
    storage_used: float
    load_shed: float
    voltage: float
    frequency: float
    imbalance: float


class RenewableGenerator:
    def __init__(self):
        self.solar_base = config.SOLAR_BASE
        self.wind_base = config.WIND_BASE
        self.noise = config.GEN_NOISE

    def solar_output(self, t: int) -> float:
        day_profile = max(0.0, math.sin((t / 60.0) * math.pi))
        return max(0.0, self.solar_base * day_profile + random.uniform(-self.noise, self.noise))

    def wind_output(self, t: int) -> float:
        variation = 0.7 + 0.3 * math.sin(t / 20.0)
        return max(0.0, self.wind_base * variation + random.uniform(-self.noise, self.noise))

    def total_output(self, t: int) -> tuple[float, float, float]:
        solar = self.solar_output(t)
        wind = self.wind_output(t)
        return solar, wind, solar + wind


class LoadModel:
    def __init__(self):
        self.base = config.LOAD_BASE
        self.variation = config.LOAD_VARIATION
        self.noise = config.LOAD_NOISE

    def get_load(self, t: int) -> float:
        demand_wave = self.variation * (1 + math.sin(t / 25.0))
        noise = random.uniform(-self.noise, self.noise)
        return max(5.0, self.base + demand_wave + noise)


class SensorModel:
    def read_all(self, state: GridState) -> dict:
        return {
            "time_step": state.time_step,
            "load": state.true_load,
            "generation": state.total_generation,
            "voltage": state.voltage,
            "frequency": state.frequency,
        }


class CommunicationLayer:
    def __init__(self):
        self.delay_buffer = []

    def transmit(self, packet: dict) -> dict | None:
        return packet

    def transmit_with_delay(self, packet: dict, delay_steps: int) -> dict | None:
        self.delay_buffer.append((delay_steps, packet))
        ready_packet = None
        new_buffer = []

        for remaining, pkt in self.delay_buffer:
            if remaining <= 0 and ready_packet is None:
                ready_packet = pkt
            else:
                new_buffer.append((remaining - 1, pkt))

        self.delay_buffer = new_buffer
        return ready_packet


class Controller:
    def __init__(self):
        self.reserve_max = config.RESERVE_MAX
        self.storage_max = config.STORAGE_MAX
        self.max_load_shed = config.MAX_LOAD_SHED

    def compute_control(self, sensor_data: dict) -> dict:
        load = sensor_data["load"]
        generation = sensor_data["generation"]
        imbalance = generation - load

        reserve = 0.0
        storage = 0.0
        shed = 0.0

        if imbalance < 0:
            deficit = abs(imbalance)
            reserve = min(deficit * 0.6, self.reserve_max)
            remaining = max(0.0, deficit - reserve)
            storage = min(remaining * 0.6, self.storage_max)
            remaining = max(0.0, remaining - storage)
            shed = min(remaining, self.max_load_shed)

        return {
            "reserve_dispatch": reserve,
            "storage_dispatch": storage,
            "load_shed": shed,
            "source_id": config.AUTH_TOKEN,
        }


class SmartGrid:
    def __init__(self):
        self.nominal_voltage = config.NOMINAL_VOLTAGE
        self.nominal_frequency = config.NOMINAL_FREQUENCY

    def update_state(
        self,
        t: int,
        solar: float,
        wind: float,
        load: float,
        control_action: dict,
    ) -> GridState:
        generation = solar + wind
        reserve_used = max(0.0, control_action.get("reserve_dispatch", 0.0))
        storage_used = max(0.0, control_action.get("storage_dispatch", 0.0))
        load_shed = max(0.0, control_action.get("load_shed", 0.0))

        served_capacity = generation + reserve_used + storage_used
        effective_load = max(0.0, load - load_shed)
        served_load = min(served_capacity, effective_load)
        unmet_demand = max(0.0, effective_load - served_load)

        imbalance = served_capacity - effective_load

        frequency = self.nominal_frequency + 0.03 * imbalance
        voltage = self.nominal_voltage + 0.005 * imbalance

        return GridState(
            time_step=t,
            solar_generation=solar,
            wind_generation=wind,
            total_generation=generation,
            true_load=load,
            served_load=served_load,
            unmet_demand=unmet_demand,
            reserve_used=reserve_used,
            storage_used=storage_used,
            load_shed=load_shed,
            voltage=voltage,
            frequency=frequency,
            imbalance=imbalance,
        )