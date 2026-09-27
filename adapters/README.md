# Layer 10: System Service Adapters

- **Components:** `adapters/process_adapter.py`, `adapters/memory_adapter.py`, `adapters/filesystem_adapter.py`
- **Owner:** Magesh (Linux/OS Lead)
- **Architecture Layer:** Layer 10 (System Services)
- **Status:** Initial Prototype (Phase 9)
- **Contract Status:** `TEMPORARY LOCAL INTERFACE — REQUIRES TEAM API APPROVAL`

## Purpose

The System Service Adapters provide safe, read-only programmatic interfaces to inspect Linux system resources (processes, memory, and filesystem structures) in user space. They serve as the foundational abstraction layer through which higher-level AgenticOS workflows inspect the operating system safely.

## Security Boundary & Prohibitions

To protect system integrity and prevent destructive autonomous actions:

### 1. Process Safety Rules
- **NO Process Termination:** Zero `kill()`, `terminate()`, or signal delivery methods.
- **NO Process Modification:** No priority changes (`nice`, `renice`), no process suspension (`SIGSTOP`).
- **NO Arbitrary Execution:** Returned command line strings are diagnostic metadata; they are never executed.

### 2. Filesystem Safety Rules
- **STRICTLY Read-Only:** Queries existence, file types, sizes, directory listings, mount points, and volume capacities.
- **NO File Creation or Deletion:** Zero `create`, `write`, `delete`, `unlink`, `remove`, or `rmdir` methods.
- **NO File Modification or Renaming:** No `copy`, `move`, `rename`, or truncation operations.
- **NO Permission Changes:** Zero `chmod`, `chown`, or attribute manipulation.
- **NO Destructive Disk Operations:** Zero `mkfs`, `dd`, partition alterations, or formatting.
- **NO Mount Alterations:** Zero `mount`, `umount`, or remount commands.
- **NO Discovered File Execution:** Discovered executable paths are never launched by this adapter.

### 3. General Rules
- **Least Privilege:** Operates entirely as an unprivileged Linux user (`no sudo`).
- **Fault-Tolerant:** Gracefully handles missing files, broken symlinks, and permission restrictions without raising unhandled exceptions.

## Data Sources (Read-Only)

- **Process Inspection:** `/proc/[pid]/status`, `/proc/[pid]/cmdline`, `/proc/[pid]/stat`.
- **Memory Inspection:** `/proc/meminfo`.
- **Filesystem Metadata:** POSIX `os.stat()`, `os.lstat()`, `os.scandir()`.
- **Filesystem Capacity:** POSIX `os.statvfs()`.
- **Mount Points:** Linux `/proc/mounts`.

## Future Filesystem Workspace & Sandboxing Boundary (Architecture Guideline)

Currently, `FilesystemAdapter` provides safe, strictly read-only inspection of paths governed by Linux DAC permissions. For future integration phases where autonomous agents query the filesystem:
- An optional `allowed_roots` parameter should be introduced to restrict directory inspection to designated workspace directories.
- Any path resolving outside `allowed_roots` (via relative path traversal `..` or symlinks) should be rejected to ensure defense-in-depth isolation.
- Sandboxing mechanisms will be implemented upon official cross-layer architectural approval.
