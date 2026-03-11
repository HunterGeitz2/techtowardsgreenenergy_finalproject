import csv
import os

import matplotlib.pyplot as plt
import pandas as pd

import config


def ensure_output_dir():
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)


def save_logs_to_csv(logs: list[dict], filename: str):
    ensure_output_dir()
    path = os.path.join(config.OUTPUT_DIR, filename)

    if not logs:
        return

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=logs[0].keys())
        writer.writeheader()
        writer.writerows(logs)


def save_metrics_to_csv(metrics_rows: list[dict], filename: str):
    ensure_output_dir()
    path = os.path.join(config.OUTPUT_DIR, filename)

    if not metrics_rows:
        return

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=metrics_rows[0].keys())
        writer.writeheader()
        writer.writerows(metrics_rows)


def plot_timeseries(logs: list[dict], scenario_name: str):
    ensure_output_dir()
    df = pd.DataFrame(logs)

    plt.figure(figsize=(10, 5))
    plt.plot(df["time_step"], df["true_load"], label="True Load")
    plt.plot(df["time_step"], df["reported_load"], label="Reported Load")
    plt.plot(df["time_step"], df["total_generation"], label="Generation")
    plt.xlabel("Time Step")
    plt.ylabel("Power")
    plt.title(f"Load and Generation - {scenario_name}")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(config.OUTPUT_DIR, f"{scenario_name}_power.png"))
    plt.close()

    plt.figure(figsize=(10, 5))
    plt.plot(df["time_step"], df["frequency"], label="Frequency")
    plt.axhline(config.FREQUENCY_MIN, linestyle="--")
    plt.axhline(config.FREQUENCY_MAX, linestyle="--")
    plt.xlabel("Time Step")
    plt.ylabel("Frequency (Hz)")
    plt.title(f"Frequency Stability - {scenario_name}")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(config.OUTPUT_DIR, f"{scenario_name}_frequency.png"))
    plt.close()

    plt.figure(figsize=(10, 5))
    plt.plot(df["time_step"], df["voltage"], label="Voltage")
    plt.axhline(config.VOLTAGE_MIN, linestyle="--")
    plt.axhline(config.VOLTAGE_MAX, linestyle="--")
    plt.xlabel("Time Step")
    plt.ylabel("Voltage (p.u.)")
    plt.title(f"Voltage Stability - {scenario_name}")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(config.OUTPUT_DIR, f"{scenario_name}_voltage.png"))
    plt.close()


def plot_metric_comparison(metrics_rows: list[dict]):
    ensure_output_dir()
    df = pd.DataFrame(metrics_rows)

    metric_names = [
        "availability_percent",
        "data_integrity_percent",
        "energy_efficiency_percent",
        "average_response_time_steps",
    ]

    for metric in metric_names:
        plt.figure(figsize=(10, 5))
        plt.bar(df["scenario"], df[metric])
        plt.xticks(rotation=30, ha="right")
        plt.ylabel(metric)
        plt.title(f"Scenario Comparison - {metric}")
        plt.tight_layout()
        plt.savefig(os.path.join(config.OUTPUT_DIR, f"{metric}_comparison.png"))
        plt.close()