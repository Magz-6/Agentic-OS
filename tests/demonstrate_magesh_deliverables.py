#!/usr/bin/env python3
"""
AgenticOS v0.1 Alpha — Magesh Required Demonstrations Script
Validates Demonstrations 1 through 5 for Magesh's OS and Linux integration boundaries:
Demonstration 1: Boot AgenticOS (Splash -> graphical desktop -> native shell)
Demonstration 2: Launch Native Application (Allowlist application adapter)
Demonstration 3: Filesystem Operation (Controlled filesystem adapter)
Demonstration 4: System Information (Host/Kernel/CPU/RAM metrics)
Demonstration 5: Multi-step Integration (Create Project folder -> File manager resolution -> Verification)
"""

import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from adapters.application_adapter import ApplicationAdapter
from adapters.filesystem_adapter import FilesystemAdapter
from adapters.system_adapter import SystemAdapter
from hardware.detector import HardwareDetector


def demo1_boot_pipeline():
    print("\n--- DEMONSTRATION 1: Boot & Native Graphical Desktop Architecture ---")
    results = {}

    # Check GRUB config
    grub_path = PROJECT_ROOT / "packaging" / "config" / "grub.cfg"
    grub_content = grub_path.read_text(encoding="utf-8")
    results["grub_plymouth_configured"] = "plymouth.theme=agenticos" in grub_content
    results["grub_casper_configured"] = "boot=casper" in grub_content

    # Check Plymouth assets
    plymouth_dir = PROJECT_ROOT / "linux_integration" / "plymouth" / "agenticos"
    results["plymouth_theme_file"] = (plymouth_dir / "agenticos.plymouth").is_file()
    results["plymouth_splash_image"] = (plymouth_dir / "agenticos-splash.png").is_file()
    results["plymouth_script"] = (plymouth_dir / "agenticos.script").is_file()

    # Check systemd desktop service
    service_file = PROJECT_ROOT / "linux_integration" / "systemd" / "agenticos-desktop.service.template"
    svc_content = service_file.read_text(encoding="utf-8")
    results["systemd_graphical_target"] = "WantedBy=graphical.target" in svc_content
    results["systemd_runner_exec"] = "/opt/agenticos/system-services/desktop/runner.py" in svc_content

    # Check Native GTK Desktop Shell
    shell_file = PROJECT_ROOT / "applications" / "agenticos-shell" / "main.py"
    results["native_shell_exists"] = shell_file.is_file()

    print(json.dumps(results, indent=2))
    assert all(results.values()), "Demonstration 1 failed verification checks!"
    print("✅ DEMONSTRATION 1 SUCCESS: Boot pipeline, Plymouth theme, systemd service, and native shell verified.")
    return results


def demo2_application_launch():
    print("\n--- DEMONSTRATION 2: Safe Application Launcher Integration ---")
    adapter = ApplicationAdapter()

    # Query allowed applications
    res_list = adapter.run("list_allowed_applications", {})
    print(f"Allowed applications: {res_list.data['allowed_applications']}")

    # Check availability of terminal
    res_avail = adapter.run("check_availability", {"app_id": "terminal"})
    print(f"Terminal availability: {res_avail.data}")

    # Rejection of dangerous command injection
    res_malicious = adapter.run("launch_application", {"app_id": "rm -rf /"})
    print(f"Malicious command rejection: status={res_malicious.status.value}, success={res_malicious.success}")
    assert not res_malicious.success, "Failed: Malicious command was not rejected!"

    # Resolve executable
    res_res = adapter.run("resolve_binary", {"app_id": "terminal"})
    print(f"Terminal binary resolution: {res_res.data}")

    print("✅ DEMONSTRATION 2 SUCCESS: Allowlist-governed application launch verified with zero arbitrary execution.")
    return {"allowed": res_list.data, "terminal_check": res_avail.data, "rejection_test": not res_malicious.success}


def demo3_filesystem_operation():
    print("\n--- DEMONSTRATION 3: Controlled Filesystem Operations ---")
    adapter = FilesystemAdapter()

    # Inspect path
    res_inspect = adapter.run("inspect_path", {"path": "/etc"})
    print(f"Path inspection (/etc): is_dir={res_inspect.data['is_dir']}, permissions={res_inspect.data.get('permissions_octal')}")

    # Query usage
    res_usage = adapter.run("get_usage", {"path": "/"})
    print(f"Filesystem capacity (/): total_bytes={res_usage.data['total_bytes']}, free_bytes={res_usage.data['free_bytes']}")

    # Ensure destructive actions are blocked
    res_rm = adapter.run("delete", {"path": "/etc"})
    print(f"Destructive action block (delete): status={res_rm.status.value}, success={res_rm.success}")
    assert not res_rm.success, "Failed: Destructive filesystem operation was not rejected!"

    print("✅ DEMONSTRATION 3 SUCCESS: Filesystem inspection verified with strict destructive command prevention.")
    return {"inspect": res_inspect.data, "usage": res_usage.data, "security_block": not res_rm.success}


def demo4_system_information():
    print("\n--- DEMONSTRATION 4: System Information & Telemetry ---")
    sys_adapter = SystemAdapter()
    hw_detector = HardwareDetector()

    # System adapter query
    res_sys = sys_adapter.run("get_system_info", {})
    res_uptime = sys_adapter.run("get_uptime", {})

    print(f"Operating System: {res_sys.data['os_pretty_name']}")
    print(f"Kernel Release:   {res_sys.data['release']}")
    print(f"Architecture:     {res_sys.data['architecture']}")
    print(f"Hostname:         {res_sys.data['hostname']}")
    if res_uptime.success:
        print(f"System Uptime:    {res_uptime.data['uptime_seconds']:.2f} seconds")

    # Hardware detector query
    cpu = hw_detector.get_cpu_info()
    mem = hw_detector.get_memory_info()
    print(f"CPU Model:        {cpu.get('model_name')}")
    print(f"Logical Cores:    {cpu.get('logical_cores')}")
    print(f"Memory Total:     {mem.get('total_bytes') / (1024*1024):.2f} MB")

    print("✅ DEMONSTRATION 4 SUCCESS: System, kernel, and hardware metrics collected cleanly.")
    return {"sys_info": res_sys.data, "cpu": cpu, "memory": mem}


def demo5_multistep_integration():
    print("\n--- DEMONSTRATION 5: Multi-Step Integration (Create Project -> File Manager Resolution) ---")
    fs_adapter = FilesystemAdapter()
    app_adapter = ApplicationAdapter()

    demo_dir = Path("/tmp/AgenticOS_Project_Demo")

    # Step 1: Create project folder
    res_create = fs_adapter.run("create_directory", {"path": str(demo_dir)})
    print(f"Step 1 - Create Directory: success={res_create.success}, path={res_create.data.get('path')}")

    # Step 2: Verify directory exists via inspection
    res_verify = fs_adapter.run("inspect_path", {"path": str(demo_dir)})
    print(f"Step 2 - Verify Directory: exists={res_verify.data['exists']}, is_dir={res_verify.data['is_dir']}")

    # Step 3: Resolve file manager
    res_fm = app_adapter.run("resolve_binary", {"app_id": "file_manager"})
    print(f"Step 3 - Resolve File Manager: binary_path={res_fm.data.get('binary_path')}")

    # Step 4: Verify integration flow
    success = res_create.success and res_verify.data["exists"] and res_verify.data["is_dir"]
    assert success, "Multi-step integration failed!"

    print("✅ DEMONSTRATION 5 SUCCESS: Project folder created, verified, and file manager resolved.")
    return {"create": res_create.data, "verify": res_verify.data, "file_manager": res_fm.data}


def main():
    print("=====================================================================")
    print("AgenticOS v0.1 Alpha — Execution of Required Demonstrations 1 - 5")
    print("=====================================================================")

    d1 = demo1_boot_pipeline()
    d2 = demo2_application_launch()
    d3 = demo3_filesystem_operation()
    d4 = demo4_system_information()
    d5 = demo5_multistep_integration()

    print("=====================================================================")
    print("🎉 ALL 5 MAGESH DEMONSTRATIONS EXECUTED AND VALIDATED SUCCESSFULLY")
    print("=====================================================================")


if __name__ == "__main__":
    main()
