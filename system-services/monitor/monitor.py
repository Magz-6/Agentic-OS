import time
from pathlib import Path


def read_cpu():
    data = Path("/proc/stat").read_text().splitlines()[0].split()

    values = list(map(int, data[1:]))

    idle = values[3] + values[4]
    total = sum(values)

    return total, idle


def read_memory():
    lines = Path("/proc/meminfo").read_text().splitlines()

    memory = {}

    for line in lines:
        key, value = line.split(":", 1)
        memory[key] = int(value.strip().split()[0])

    total = memory["MemTotal"]
    available = memory["MemAvailable"]
    used = total - available

    return total, used, available


def main():
    try:
        while True:
            cpu_total_1, cpu_idle_1 = read_cpu()

            time.sleep(1)

            cpu_total_2, cpu_idle_2 = read_cpu()

            total_difference = cpu_total_2 - cpu_total_1
            idle_difference = cpu_idle_2 - cpu_idle_1

            cpu_usage = 100 * (1 - idle_difference / total_difference)

            total_memory, used_memory, available_memory = read_memory()

            print(f"CPU Usage: {cpu_usage:.2f}%")
            print(f"Total Memory: {total_memory / 1024:.1f} MB")
            print(f"Used Memory: {used_memory / 1024:.1f} MB")
            print(f"Available Memory: {available_memory / 1024:.1f} MB")
            print("-" * 30)

    except KeyboardInterrupt:
        print("\nMonitor stopped.")


if __name__ == "__main__":
    main()

