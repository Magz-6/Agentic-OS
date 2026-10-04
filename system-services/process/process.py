from pathlib import Path
import time


def get_processes():
    processes = []

    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            pid = entry.name

            try:
                status = (entry / "status").read_text().splitlines()

                name = "Unknown"
                memory = 0

                for line in status:
                    if line.startswith("Name:"):
                        name = line.split(":", 1)[1].strip()

                    elif line.startswith("VmRSS:"):
                        memory = int(line.split()[1])

                stat = (entry / "stat").read_text().split()
                cpu_time = int(stat[13]) + int(stat[14])

                processes.append((pid, name, memory, cpu_time))

            except (PermissionError, FileNotFoundError, IndexError):
                continue

    return processes


def main():
    processes_1 = get_processes()

    time.sleep(1)

    processes_2 = get_processes()

    print(f"Running processes: {len(processes_2)}")
    print("-" * 60)

    first_reading = {pid: cpu_time for pid, name, memory, cpu_time in processes_1}

    for pid, name, memory, cpu_time in processes_2:
        if pid in first_reading:
            cpu_difference = cpu_time - first_reading[pid]
            cpu_usage = cpu_difference / 10

            print(
                f"PID: {pid:<6} "
                f"Name: {name:<20} "
                f"Memory: {memory:<8} KB "
                f"CPU: {cpu_usage:.1f}%"
            )


if __name__ == "__main__":
    main()
