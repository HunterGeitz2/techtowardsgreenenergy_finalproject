import glob
import os

import matplotlib.pyplot as plt
import pandas as pd

OUTPUT_DIR = "results"
SUMMARY_FILE = os.path.join(OUTPUT_DIR, "summary_metrics.csv")


def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_summary():
    if not os.path.exists(SUMMARY_FILE):
        raise FileNotFoundError(f"Could not find {SUMMARY_FILE}")
    return pd.read_csv(SUMMARY_FILE)


def load_scenario_logs():
    csv_files = glob.glob(os.path.join(OUTPUT_DIR, "*.csv"))
    scenario_logs = {}

    for file in csv_files:
        filename = os.path.basename(file)
        if filename in ("summary_metrics.csv", "extra_metrics.csv"):
            continue
        scenario_name = filename.replace(".csv", "")
        scenario_logs[scenario_name] = pd.read_csv(file)

    if not scenario_logs:
        raise FileNotFoundError("No scenario CSV log files found in results/")

    return scenario_logs


def save_bar_chart(labels, values, ylabel, title, filename):
    plt.figure(figsize=(10, 5))
    plt.bar(labels, values)
    plt.xticks(rotation=30, ha="right")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, filename))
    plt.close()


def save_line_chart(x, y, xlabel, ylabel, title, filename):
    plt.figure(figsize=(10, 5))
    plt.plot(x, y)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, filename))
    plt.close()


def plot_summary_metrics(summary_df):
    save_bar_chart(
        summary_df["scenario"],
        summary_df["availability_percent"],
        "Availability (%)",
        "Availability by Scenario",
        "availability_by_scenario.png",
    )

    save_bar_chart(
        summary_df["scenario"],
        summary_df["data_availability_percent"],
        "Data Availability (%)",
        "Data Availability by Scenario",
        "data_availability_by_scenario.png",
    )

    save_bar_chart(
        summary_df["scenario"],
        summary_df["incoming_data_integrity_percent"],
        "Incoming Data Integrity (%)",
        "Incoming Data Integrity by Scenario",
        "incoming_data_integrity_by_scenario.png",
    )

    save_bar_chart(
        summary_df["scenario"],
        summary_df["trusted_control_data_percent"],
        "Trusted Control Data (%)",
        "Trusted Data Used by Controller",
        "trusted_control_data_by_scenario.png",
    )

    save_bar_chart(
        summary_df["scenario"],
        summary_df["energy_efficiency_percent"],
        "Energy Efficiency (%)",
        "Energy Efficiency by Scenario",
        "energy_efficiency_by_scenario.png",
    )

    save_bar_chart(
        summary_df["scenario"],
        summary_df["average_response_time_steps"],
        "Response Time (steps)",
        "Average Response Time by Scenario",
        "response_time_by_scenario.png",
    )


def calculate_extra_metrics(df):
    avg_unmet_demand = df["unmet_demand"].mean()
    avg_freq_dev = (df["frequency"] - 50.0).abs().mean()
    max_freq_dev = (df["frequency"] - 50.0).abs().max()
    avg_volt_dev = (df["voltage"] - 1.0).abs().mean()
    max_volt_dev = (df["voltage"] - 1.0).abs().max()

    stability_violations = (
        ((df["frequency"] < 49.5) | (df["frequency"] > 50.5))
        | ((df["voltage"] < 0.95) | (df["voltage"] > 1.05))
    ).sum()

    anomaly_count = df["anomaly_detected"].sum() if "anomaly_detected" in df.columns else 0

    auth_failures = 0
    if "command_authenticated" in df.columns:
        auth_failures = (~df["command_authenticated"]).sum()

    demand_served_ratio = 0.0
    if df["true_load"].sum() > 0:
        demand_served_ratio = 100 * df["served_load"].sum() / df["true_load"].sum()

    fallback_count = df["used_fallback"].sum() if "used_fallback" in df.columns else 0

    return {
        "avg_unmet_demand": avg_unmet_demand,
        "avg_freq_dev": avg_freq_dev,
        "max_freq_dev": max_freq_dev,
        "avg_volt_dev": avg_volt_dev,
        "max_volt_dev": max_volt_dev,
        "stability_violations": stability_violations,
        "anomaly_count": anomaly_count,
        "auth_failures": auth_failures,
        "demand_served_ratio": demand_served_ratio,
        "fallback_count": fallback_count,
    }


def build_extra_metrics_table(scenario_logs):
    rows = []

    for scenario_name, df in scenario_logs.items():
        row = calculate_extra_metrics(df)
        row["scenario"] = scenario_name
        rows.append(row)

    return pd.DataFrame(rows)


def plot_extra_metrics(extra_df):
    save_bar_chart(
        extra_df["scenario"],
        extra_df["avg_unmet_demand"],
        "Average Unmet Demand",
        "Average Unmet Demand by Scenario",
        "avg_unmet_demand_by_scenario.png",
    )

    save_bar_chart(
        extra_df["scenario"],
        extra_df["avg_freq_dev"],
        "Average Frequency Deviation (Hz)",
        "Average Frequency Deviation by Scenario",
        "avg_frequency_deviation_by_scenario.png",
    )

    save_bar_chart(
        extra_df["scenario"],
        extra_df["max_freq_dev"],
        "Max Frequency Deviation (Hz)",
        "Maximum Frequency Deviation by Scenario",
        "max_frequency_deviation_by_scenario.png",
    )

    save_bar_chart(
        extra_df["scenario"],
        extra_df["avg_volt_dev"],
        "Average Voltage Deviation (p.u.)",
        "Average Voltage Deviation by Scenario",
        "avg_voltage_deviation_by_scenario.png",
    )

    save_bar_chart(
        extra_df["scenario"],
        extra_df["max_volt_dev"],
        "Max Voltage Deviation (p.u.)",
        "Maximum Voltage Deviation by Scenario",
        "max_voltage_deviation_by_scenario.png",
    )

    save_bar_chart(
        extra_df["scenario"],
        extra_df["stability_violations"],
        "Number of Violations",
        "Voltage/Frequency Stability Violations by Scenario",
        "stability_violations_by_scenario.png",
    )

    save_bar_chart(
        extra_df["scenario"],
        extra_df["anomaly_count"],
        "Anomaly Detections",
        "Anomaly Detections by Scenario",
        "anomaly_detections_by_scenario.png",
    )

    save_bar_chart(
        extra_df["scenario"],
        extra_df["auth_failures"],
        "Authentication Failures",
        "Command Authentication Failures by Scenario",
        "auth_failures_by_scenario.png",
    )

    save_bar_chart(
        extra_df["scenario"],
        extra_df["demand_served_ratio"],
        "Demand Served (%)",
        "Demand Served Ratio by Scenario",
        "demand_served_ratio_by_scenario.png",
    )

    save_bar_chart(
        extra_df["scenario"],
        extra_df["fallback_count"],
        "Fallback Uses",
        "Fallback Usage by Scenario",
        "fallback_usage_by_scenario.png",
    )


def plot_time_series_for_each_scenario(scenario_logs):
    for scenario_name, df in scenario_logs.items():
        save_line_chart(
            df["time_step"],
            df["unmet_demand"],
            "Time Step",
            "Unmet Demand",
            f"Unmet Demand Over Time - {scenario_name}",
            f"{scenario_name}_unmet_demand_timeseries.png",
        )

        save_line_chart(
            df["time_step"],
            (df["frequency"] - 50.0).abs(),
            "Time Step",
            "Absolute Frequency Deviation (Hz)",
            f"Frequency Deviation Over Time - {scenario_name}",
            f"{scenario_name}_frequency_deviation_timeseries.png",
        )

        save_line_chart(
            df["time_step"],
            (df["voltage"] - 1.0).abs(),
            "Time Step",
            "Absolute Voltage Deviation (p.u.)",
            f"Voltage Deviation Over Time - {scenario_name}",
            f"{scenario_name}_voltage_deviation_timeseries.png",
        )

        save_line_chart(
            df["time_step"],
            df["reserve_used"],
            "Time Step",
            "Reserve Used",
            f"Reserve Dispatch Over Time - {scenario_name}",
            f"{scenario_name}_reserve_dispatch_timeseries.png",
        )

        save_line_chart(
            df["time_step"],
            df["storage_used"],
            "Time Step",
            "Storage Used",
            f"Storage Dispatch Over Time - {scenario_name}",
            f"{scenario_name}_storage_dispatch_timeseries.png",
        )

        save_line_chart(
            df["time_step"],
            df["load_shed"],
            "Time Step",
            "Load Shed",
            f"Load Shedding Over Time - {scenario_name}",
            f"{scenario_name}_load_shed_timeseries.png",
        )

        if "reported_load" in df.columns and "true_load" in df.columns:
            save_line_chart(
                df["time_step"],
                (df["reported_load"] - df["true_load"]).abs(),
                "Time Step",
                "Absolute Load Error",
                f"Load Measurement Error Over Time - {scenario_name}",
                f"{scenario_name}_load_error_timeseries.png",
            )


def save_extra_metrics_csv(extra_df):
    path = os.path.join(OUTPUT_DIR, "extra_metrics.csv")
    extra_df.to_csv(path, index=False)


def main():
    ensure_output_dir()

    summary_df = load_summary()
    scenario_logs = load_scenario_logs()

    plot_summary_metrics(summary_df)

    extra_df = build_extra_metrics_table(scenario_logs)
    save_extra_metrics_csv(extra_df)
    plot_extra_metrics(extra_df)

    plot_time_series_for_each_scenario(scenario_logs)

    print("Additional performance graphs created successfully.")
    print(f"Saved graphs and extra metrics to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()