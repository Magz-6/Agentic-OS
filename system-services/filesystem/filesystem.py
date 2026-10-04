from pathlib import Path


def inspect_path(path_string):
    path = Path(path_string)

    if not path.exists():
        print(f"Path does not exist: {path}")
        return

    if path.is_file():
        print(f"Type: File")
        print(f"Path: {path}")
        print(f"Size: {path.stat().st_size} bytes")

    elif path.is_dir():
        print(f"Type: Directory")
        print(f"Path: {path}")
        print("Contents:")

        for item in path.iterdir():
            if item.is_dir():
                print(f"  [DIR]  {item.name}")
            else:
                print(f"  [FILE] {item.name}")

    else:
        print(f"Type: Other")
        print(f"Path: {path}")


def main():
    inspect_path("/home/magz/AgenticOS/system-services/monitor/monitor.py")


if __name__ == "__main__":
    main()
