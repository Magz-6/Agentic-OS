# AgenticOS — Application & System Adapter Framework v0.1

- **Layer:** Layer 9 (Applications) & Layer 10 (System Services)
- **Owner:** Magesh (Linux Integration & System Services Lead)
- **Status:** Initial Adapter Framework Prototype (Phase 10)
- **Integration Status:**
  - `Magesh Adapter Framework: IMPLEMENTED`
  - `Workflow Runtime Integration: PENDING TEAM CONTRACT`
  - `Task Dispatcher Integration: PENDING TEAM CONTRACT`

> [!IMPORTANT]
> **Contract Notices:**
> 1. *Workflow Runtime and Task Dispatcher integration are pending finalized team contracts.*
> 2. *The framework does not provide arbitrary shell execution.*

---

## 1. Purpose of the Adapter Layer

The Adapter Framework provides a structured, contract-neutral abstraction layer for executing controlled operating system and application actions on AgenticOS. It defines a uniform action dispatch contract (`validate()`, `execute()`, and `run()`), an extensible `AdapterRegistry`, and an immutable structured envelope (`AdapterResult`) for reporting status, data, and diagnostic errors.

Higher-level autonomous components (such as future Workflow Runtimes, Task Dispatchers, and Agent executors) interact with the Linux host strictly through these registered adapters rather than making direct low-level OS calls.

---

## 2. Ownership Boundary

### Magesh Owns:
- Core adapter interface contract (`BaseAdapter`)
- Standardized execution result schema (`AdapterResult`, `AdapterStatus`)
- Central adapter registry (`AdapterRegistry`, `default_registry`)
- Linux filesystem inspection adapter (`FilesystemAdapter`)
- Allowlist-controlled application execution adapter (`ApplicationAdapter`)
- Read-only system state inspection adapter (`SystemAdapter`)
- Framework test suite and security boundary enforcement

### Magesh Explicitly Does NOT Own:
- Vivek's Goal Runtime / Workflow Runtime / Task Graph / State Machine
- Vishnu's Task Decomposition / Parameter Extraction
- Krithikesh's Task Dispatcher / Agent Bus
- Application UI / Prompts / Telemetry Collector

---

## 3. Architecture & Components

```
                    +------------------------------------+
                    | Future Workflow Runtime / Dispatch |
                    |     (Pending Team Contract)        |
                    +-----------------+------------------+
                                      |
                                      v
                    +------------------------------------+
                    |       adapters.AdapterRegistry     |
                    +-----------------+------------------+
                                      |
             +------------------------+------------------------+
             |                        |                        |
             v                        v                        v
+------------------------+ +--------------------+ +------------------------+
|   FilesystemAdapter    | | ApplicationAdapter | |     SystemAdapter      |
| (Inspect / Meta / Use) | | (Allowlist Launch) | | (Host / Kernel / Unit) |
+------------------------+ +--------------------+ +------------------------+
             |                        |                        |
             +------------------------+------------------------+
                                      |
                                      v
                    +------------------------------------+
                    |       adapters.AdapterResult       |
                    | (SUCCESS / VALIDATION_ERROR / ...) |
                    +------------------------------------+
```

### Module Structure:
- [`adapters/base.py`](file:///c:/Users/mages/OneDrive/Desktop/AgenticOS/adapters/base.py): Base class defining the standard adapter interface.
- [`adapters/result.py`](file:///c:/Users/mages/OneDrive/Desktop/AgenticOS/adapters/result.py): Standardized status enumeration and result container.
- [`adapters/registry.py`](file:///c:/Users/mages/OneDrive/Desktop/AgenticOS/adapters/registry.py): Registration and lookup hub for adapters.
- [`adapters/filesystem_adapter.py`](file:///c:/Users/mages/OneDrive/Desktop/AgenticOS/adapters/filesystem_adapter.py): Read-only filesystem metadata and storage queries.
- [`adapters/application_adapter.py`](file:///c:/Users/mages/OneDrive/Desktop/AgenticOS/adapters/application_adapter.py): Allowlisted application launching and binary verification.
- [`adapters/system_adapter.py`](file:///c:/Users/mages/OneDrive/Desktop/AgenticOS/adapters/system_adapter.py): Read-only system diagnostic queries and service inspection.
- [`adapters/app_launcher.py`](file:///c:/Users/mages/OneDrive/Desktop/AgenticOS/adapters/app_launcher.py): Low-level process spawner with strict allowlist and metacharacter checks.

---

## 4. Base Interface Contract (`BaseAdapter`)

Every adapter must subclass `BaseAdapter` and implement:

1. **`name -> str`**: Unique string identifier for the adapter.
2. **`supported_actions -> Set[str]`**: Set of permitted action strings.
3. **`validate(action: str, parameters: Dict[str, Any]) -> Tuple[bool, Optional[str]]`**:
   Validates parameters before execution. Returns `(True, None)` or `(False, "error message")`.
4. **`execute(action: str, parameters: Dict[str, Any]) -> AdapterResult`**:
   Executes the requested action and returns an `AdapterResult`.
5. **`run(action: str, parameters: Optional[Dict[str, Any]] = None) -> AdapterResult`**:
   High-level entry point that automatically checks `supported_actions`, calls `validate()`, catches exceptions, and delegates to `execute()`.

---

## 5. Result Envelope (`AdapterResult`)

Every adapter call returns an immutable structured `AdapterResult`:

```python
{
    "success": True,
    "status": "SUCCESS",            # SUCCESS, VALIDATION_ERROR, UNSUPPORTED_ACTION, EXECUTION_ERROR
    "adapter": "filesystem",
    "action": "inspect_path",
    "message": "Path inspected successfully",
    "data": {
        "path": "/etc",
        "exists": True,
        "is_dir": True,
        "size_bytes": 4096
    },
    "error": None
}
```

### Status Types:
- `AdapterStatus.SUCCESS`: Action executed successfully.
- `AdapterStatus.VALIDATION_ERROR`: Missing or malformed parameters; forbidden characters or unapproved IDs.
- `AdapterStatus.UNSUPPORTED_ACTION`: Action name is not in `supported_actions`.
- `AdapterStatus.EXECUTION_ERROR`: Runtime failure during execution (e.g. binary missing in headless environment).

---

## 6. Adapter Registry (`AdapterRegistry`)

The central registry provides thread-safe lifecycle and discovery mechanisms:

```python
from adapters import default_registry, FilesystemAdapter, ApplicationAdapter, SystemAdapter

# Access registered adapters
fs_adapter = default_registry.get("filesystem")
app_adapter = default_registry.get("application")
sys_adapter = default_registry.get("system")

# Query registered adapters
all_names = default_registry.list_adapters()  # ["application", "filesystem", "system"]
```

---

## 7. Supported Capabilities

### 7.1 Filesystem Adapter (`filesystem`)
- **`inspect_path`**: Comprehensive POSIX metadata (size, timestamps, permissions, directory flags).
- **`check_existence`**: Non-throwing boolean check for file or directory existence.
- **`list_directory`**: Safe listing of directory entries with type classifications.
- **`get_metadata`**: File attributes, ownership, and mode information.
- **`get_usage`**: Disk capacity and volume usage metrics via `statvfs`.
- **`get_mounts`**: Mounted filesystem hierarchy and options parsed from `/proc/mounts`.

### 7.2 Application Adapter (`application`)
- **`launch_application`**: Launch an allowlisted application by ID (supports `dry_run: True` for validation).
- **`check_availability`**: Check if an application is allowlisted and candidate binary exists.
- **`list_applications`**: List all approved application IDs (`browser`, `terminal`, `text_editor`, `file_manager`).
- **`resolve_binary`**: Locate candidate executable binary in `PATH`.

### 7.3 System Adapter (`system`)
- **`get_system_info`**: Host OS, distribution name, architecture, and Python runtime version.
- **`get_hostname`**: Current machine hostname.
- **`get_kernel_info`**: Kernel release and `/proc/version` metadata.
- **`get_uptime`**: System uptime and idle time from `/proc/uptime`.
- **`get_memory_info`**: Detailed memory metrics parsed from `/proc/meminfo`.
- **`get_service_status`**: Read-only systemd service status via non-shell `systemctl is-active`.

---

## 8. Security Boundaries & Prohibitions

1. **Strictly No Arbitrary Shell Execution**:
   - `shell=True` is forbidden across all adapters and launcher modules.
   - All subprocess calls pass explicit tokenized argument arrays.
2. **Strict Application Allowlist**:
   - Only allowlisted application identifiers (`browser`, `terminal`, `text_editor`, `file_manager`) are permitted.
   - Arbitrary binary paths (e.g., `/bin/bash`, `curl`, `rm`) are rejected during validation.
3. **No Shell Metacharacters**:
   - Arguments containing `;`, `&`, `|`, `` ` ``, `$`, `<`, `>`, `\n`, `\r`, or `\t` are rejected.
   - Script-wrapping flags (`-c`, `/c`, `--command`) are prohibited.
4. **No Destructive System Actions**:
   - System actions are strictly read-only. Destructive actions (`reboot`, `shutdown`, `poweroff`, `kill`, `sudo`) are not supported and rejected.
   - Service status inspection accepts only safe alphanumeric/hyphen/dot unit names and executes only read-only `systemctl is-active`.
5. **Least Privilege**:
   - Adapters run as an unprivileged user without `sudo` requirements.

---

## 9. Example Usage

```python
from adapters import default_registry

# 1. Inspect Filesystem Path
fs = default_registry.get("filesystem")
res = fs.run("inspect_path", {"path": "/etc/os-release"})
if res.success:
    print(f"File size: {res.data['size_bytes']} bytes")

# 2. Check Application Availability (Dry-Run Launch)
app = default_registry.get("application")
res = app.run("launch_application", {
    "app_name": "text_editor",
    "args": ["/tmp/notes.txt"],
    "dry_run": True
})
print("Dry run command:", res.data["command"])

# 3. Query System Service Status
sys_adapter = default_registry.get("system")
res = sys_adapter.run("get_service_status", {"service_name": "agenticos-prompt-ui"})
print("Service active:", res.data["is_active"])
```

---

## 10. Verification & Test Execution

Run the complete test suite including all adapter framework tests:

```bash
# Full test suite
python3 -m unittest discover tests

# Adapter framework unit tests only
python3 -m unittest tests/test_adapter_framework.py tests/test_filesystem_adapter.py tests/test_application_adapter.py tests/test_system_adapter.py
```

---

## 11. Future Integration Points & Status

- **Workflow Runtime Integration**: Pending finalized contract with Vivek. Adapters expose the standardized `run(action, parameters)` method ready for invocation by the workflow engine.
- **Task Dispatcher Integration**: Pending finalized contract with Krithikesh. Adapters can be registered dynamically as dispatched execution targets.
- **Current Headless Limitation**: When AgenticOS runs in headless/server environments without a graphical server (Xorg/Wayland), GUI application launches will report `binary_not_found` or unavailable status safely via `AdapterResult.execution_error`.
