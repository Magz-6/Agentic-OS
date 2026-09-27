# AgenticOS — Filesystem Safety & Adapter Specification (Layer 10)

> **DOCUMENT STATUS:** APPROVED BASELINE DOCUMENTATION  
> **MAINTAINER:** Magesh (Linux / OS Lead)  
> **ARCHITECTURE LAYER:** Layer 10 (System Services — Filesystem Boundary)  
> **CONTRACT STATUS:** `TEMPORARY LOCAL INTERFACE — REQUIRES TEAM API APPROVAL`  
> **DATE:** 27 September 2026  

---

## 1. Architectural Scope & Purpose

In an autonomous agent operating system, filesystem interaction represents a critical safety risk. Unrestricted file write, truncate, permission alteration, or volume formatting commands could result in irreversible data loss.

To protect the underlying host and user files, Magesh's implementation provides a **strictly read-only filesystem adapter** (`adapters/filesystem_adapter.py`). It enables AgenticOS upper layers to inspect file metadata, verify path existence, stream directory entries, query storage capacity, and inspect mount topologies without exposing any write or destructive capabilities.

```
+-------------------------------------------------------------------------+
|                  AgenticOS Upper Intelligence Layers                    |
+-------------------------------------------------------------------------+
                                    │
                                    ▼ (Strictly Read-Only Queries)
+-------------------------------------------------------------------------+
| Layer 10: FilesystemAdapter (adapters/filesystem_adapter.py)            |
|                                                                         |
|  - inspect_path(path)      -> Safe metadata, symlink classification    |
|  - list_directory(path)    -> Streaming directory entry summaries       |
|  - get_usage(path)         -> Capacity, free space, and usage %         |
|  - get_mounts()            -> Mount table from /proc/mounts             |
+-------------------------------------------------------------------------+
                                    │
                                    ▼ (POSIX System Calls & Virtual Files)
+-------------------------------------------------------------------------+
| Linux Kernel VFS: os.stat, os.lstat, os.scandir, os.statvfs, /proc/mounts|
+-------------------------------------------------------------------------+
```

---

## 2. Implemented Read-Only Operations

The `FilesystemAdapter` exposes four safe inspection methods:

### A. Path Inspection (`inspect_path`)
* **Signature:** `inspect_path(target_path: Union[str, Path]) -> Dict[str, Any]`
* **Capabilities:** Safely queries file metadata without raising unhandled exceptions on missing or inaccessible paths.
* **Returned Metadata:**
  * `path`: Normalized string representation.
  * `exists`: Boolean indicating physical presence.
  * `is_file`, `is_dir`, `is_symlink`: File classification flags.
  * `is_broken_symlink`: Indicates a symlink pointing to a nonexistent target.
  * `size_bytes`: File size in exact integer bytes.
  * `mtime`: Modification timestamp (POSIX float seconds).
  * `permissions_octal`: Standard octal permission string (e.g. `'0o755'`).
  * `symlink_target`: Unresolved target destination if the path is a symlink.
  * `status`: Status classification (`"ok"`, `"not_found"`, `"permission_denied"`, `"broken_symlink"`, `"error"`).

### B. Directory Listing (`list_directory`)
* **Signature:** `list_directory(target_path: Union[str, Path], limit: Optional[int] = 100) -> Dict[str, Any]`
* **Capabilities:** Iterates directory entries safely using `os.scandir()` within a context manager.
* **Safety Features:**
  * Enforces an entry collection limit (default: 100 entries) to prevent memory exhaustion in large directories (e.g. `/usr/lib`).
  * Calculates `total_entries` count even if entry collection is capped.
  * Gracefully skips unreadable individual entries without aborting the overall scan.
  * Explicitly distinguishes non-directories (`status="not_a_directory"`).

### C. Storage Capacity & Usage (`get_usage`)
* **Signature:** `get_usage(target_path: Union[str, Path] = "/") -> Dict[str, Any]`
* **Capabilities:** Computes total, free, available, and used storage bytes for the volume containing `target_path`.
* **Calculation Math:**
  $$\text{Total Bytes} = \text{f\_blocks} \times \text{f\_frsize}$$
  $$\text{Free Bytes} = \text{f\_bfree} \times \text{f\_frsize}$$
  $$\text{Available Bytes} = \text{f\_bavail} \times \text{f\_frsize}$$
  $$\text{Used Bytes} = \max(0, \text{Total Bytes} - \text{Free Bytes})$$
  $$\text{Usage \%} = \text{round}\left(\frac{\text{Used Bytes}}{\text{Total Bytes}} \times 100.0, 2\right)$$
* **Cross-Platform Resilience:** Uses POSIX `os.statvfs()` on Linux; falls back cleanly to `shutil.disk_usage()` when executed on the Windows host.

### D. Mount Table Inspection (`get_mounts`)
* **Signature:** `get_mounts() -> List[Dict[str, Any]]`
* **Capabilities:** Parses Linux `/proc/mounts` into structured dictionaries reporting `device`, `mountpoint`, `fstype`, `options`, and a computed boolean `is_read_only` (set to `True` if `'ro'` is present in mount options).

---

## 3. Symlink Traversal & Circular Safety

Symlinks pose security and denial-of-service risks (e.g. circular directory loops, traversal outside restricted hierarchies, and broken targets).

The `FilesystemAdapter` handles symlinks using a strict two-stage check:
1. **Lstat Precedence:** The adapter always calls `Path.lstat()` before `Path.stat()`. This inspects the symlink pointer itself rather than blindly following the target.
2. **Broken Symlink Detection:**
   * If `p.is_symlink()` is true, the adapter attempts to dereference the target via `p.stat()`.
   * If `FileNotFoundError` or `OSError` is caught during target inspection, the path is explicitly flagged with `exists=False`, `is_broken_symlink=True`, and `status="broken_symlink"`.
   * Symlink target text is captured via `p.readlink()` without following deep or circular paths.

---

## 4. Explicit Mutation Prohibitions

To ensure the filesystem adapter cannot be misused to modify, delete, or destroy files, the following capabilities are **STRICTLY PROHIBITED** and verified absent by unit tests (`test_prohibition_of_destructive_filesystem_methods`):

| Prohibited Category | Prohibited Operations & Methods | Security Rationale |
| :--- | :--- | :--- |
| **File Mutation** | `create`, `write`, `append`, `truncate`, `touch` | Prevents unauthorized file modification or data corruption. |
| **File Deletion** | `delete`, `unlink`, `remove`, `rmdir`, `shutil.rmtree` | Prevents accidental or autonomous data destruction. |
| **File Movement** | `copy`, `move`, `rename`, `link` | Guarantees immutable filesystem structure during inspection. |
| **Permission Changes** | `chmod`, `chown`, `setfacl`, `chattr` | Prevents privilege escalation or access restriction tampering. |
| **Mount Operations** | `mount`, `umount`, `remount` | Prevents unprivileged or unauthorized filesystem mounting. |
| **Disk Operations** | `mkfs`, `fdisk`, `parted`, `dd` | Strictly eliminates volume formatting or partition table destruction. |
| **Executable Execution** | Spawning discovered binaries | Filesystem discovery is purely informative; execution is strictly restricted to the `AppLauncher` allowlist. |

---

## 5. WSL2 Filesystem Boundaries: Linux ext4 vs. Windows DrvFs

In the current development environment, two distinct filesystem types exist with fundamentally different behaviors:

### A. Native Linux Root Filesystem (`/`)
* **Underlying Filesystem:** `ext4` virtual disk image (`vhdx`).
* **Case Sensitivity:** Fully case-sensitive (e.g. `File.txt` and `file.txt` are distinct).
* **POSIX Semantics:** Full support for POSIX file permissions (`0o755`, `0o644`), standard symlinks, hard links, and UNIX ownership.
* **Performance:** High I/O throughput; recommended for all AgenticOS code execution and test runs.

### B. Windows Host Mount (`/mnt/c/`)
* **Underlying Filesystem:** `9p` (Plan 9 filesystem driver) or `DrvFs` bridging to NTFS.
* **Case Sensitivity:** Case-insensitive by default under Windows NTFS.
* **Permission Translation:** Windows file ACLs are mapped synthetically to POSIX permissions (often showing `0o777` on all files).
* **Performance:** Slower I/O due to cross-boundary inter-process communication; symlinks may require developer mode or elevated Windows privileges.

---

## 6. Future Filesystem Workspace Sandboxing (Proposed Architecture)

> ### 📋 DESIGN RECOMMENDATION — NOT YET IMPLEMENTED:
> The current `FilesystemAdapter` operates under standard Linux Discretionary Access Control (DAC) permissions: it can inspect any path readable by the unprivileged user `mages` across the host.
>
> For future autonomous multi-agent integration (Layer 3 / Layer 1), a **Workspace Sandboxing Boundary** is recommended:
> 1. **`allowed_roots` Parameter:** An optional list of approved directory hierarchies (e.g. `[Path("/mnt/c/Users/mages/OneDrive/Desktop/AgenticOS")]`).
> 2. **Canonical Path Resolution:** All user or agent-provided paths must be resolved via `Path.resolve()` to eliminate relative traversal sequences (`../`).
> 3. **Boundary Assertion:** Any path whose resolved root lies outside `allowed_roots` will be rejected with `status="access_denied_sandbox"`.
> 
> *Status: Documented proposal only; implementation deferred until official team API freeze.*

---

## 7. Error & Fallback Classification

The `FilesystemAdapter` normalizes all filesystem anomalies into predictable, structured dictionary fields:

| Error Condition | Returned `status` | Behavior |
| :--- | :--- | :--- |
| **Path Missing** | `"not_found"` | Returns `exists=False`, zeros for size/mtime, no exception raised. |
| **Permission Denied** | `"permission_denied"` | Returns `status="permission_denied"`, gracefully skipping file content. |
| **Broken Symlink** | `"broken_symlink"` | Returns `is_symlink=True`, `is_broken_symlink=True`, `exists=False`. |
| **Non-Directory Scanned** | `"not_a_directory"` | In `list_directory()`, returns empty entries list with explicit status. |
| **General I/O Error** | `"error"` or `"unavailable"` | Traps `OSError` and returns safe diagnostic dictionary. |

---

## 8. Implementation Status Matrix

| Subsystem / Feature | Implementation Status | Test Coverage | Classification |
| :--- | :---: | :---: | :--- |
| **Path Inspection (`inspect_path`)** | **IMPLEMENTED & VERIFIED** | `test_inspect_path_normal_file` | Read-Only Module |
| **Directory Listing (`list_directory`)** | **IMPLEMENTED & VERIFIED** | `test_list_directory_normal_and_empty` | Read-Only Module |
| **Capacity & Usage (`get_usage`)** | **IMPLEMENTED & VERIFIED** | `test_usage_normal` | Read-Only Module |
| **Mount Parsing (`get_mounts`)** | **IMPLEMENTED & VERIFIED** | `test_get_mounts_normal` | Read-Only Module |
| **Symlink Safety & Broken Link Handling** | **IMPLEMENTED & VERIFIED** | `test_inspect_path_broken_symlink` | Read-Only Module |
| **Prohibition of Destructive Methods** | **IMPLEMENTED & VERIFIED** | `test_prohibition_of_destructive_filesystem_methods` | Security Verification |
| **Cross-Platform Windows Fallback** | **IMPLEMENTED & VERIFIED** | `test_statvfs_fallback_to_disk_usage` | Cross-Platform Support |
| **Workspace Sandboxing (`allowed_roots`)**| **PROPOSED ONLY** | Documented in `adapters/README.md` | **NOT IMPLEMENTED** |
| **File Write / Modify / Delete Methods** | **STRICTLY PROHIBITED** | Verified Absent | **Security Invariant** |
