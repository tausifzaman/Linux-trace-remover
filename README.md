<center>

  
# Trace Remover — Linux Forensic Trace Remover
</center>
<p align="center">
  <img src="https://img.shields.io/badge/Python-3.6+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python Version" />
  <img src="https://img.shields.io/badge/Platform-Linux-FCC624?style=for-the-badge&logo=linux&logoColor=black" alt="Platform" />
  <img src="https://img.shields.io/badge/Architecture-x86__64%20%7C%20aarch64-blue?style=for-the-badge" alt="Architecture" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License" />
  <img src="https://img.shields.io/badge/Maintenance-Active-success?style=for-the-badge" alt="Maintenance" />
  <img src="https://img.shields.io/badge/PRs-Welcome-brightgreen?style=for-the-badge" alt="PRs Welcome" />
</p>

<p align="center">
  <strong>High-performance Linux log sanitizer and system trace cleaner for VPS hygiene and lab environments.</strong>
</p>

---

## Overview

**Trace Remover** is an enterprise-grade root-level Linux hygiene utility engineered to securely overwrite and purge system logs, command execution trails, shell histories, and runtime metadata. Designed specifically for security researchers, system administrators, and lab operators, it provides deterministic cleanup across major Linux distributions.

The utility features **four granular operational power levels**, allowing operators to balance forensic sanitization against operational noise and performance impact.

> **Forensic Reality Check:** No software operating inside a running OS guest can guarantee 100% data eradication. Offloaded telemetry (SIEM, syslog-ng forwarders), cloud control-plane logs, hypervisor metrics, SSD Flash Translation Layer (FTL) wear-leveling reserves, and active volatile memory (RAM/eBPF) remain outside guest root reach. Trace Remover maximizes the destruction of all reachable on-disk and local state artifacts.

---

## Table of Contents

- [Key Features](#key-features)
- [Power Level Matrix](#power-level-matrix)
- [Forensic Artifact Coverage](#forensic-artifact-coverage)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Usage Guide](#usage-guide)
  - [Interactive Mode](#interactive-mode)
  - [CLI Automation Flags](#cli-automation-flags)
- [Unreachable Vectors & Limitations](#unreachable-vectors--limitations)
- [Post-Execution Checklist](#recommended-post-clean-steps)
- [Security & Legal Disclaimer](#safety-and-legal-notice)
- [Contributing](#contributing)
- [License](#license)

---

## Key Features

- **Multi-Pass Shred Fallback:** Leverages GNU `shred` or `wipe` when present; falls back to an internal PRNG cryptographic-pattern overwrite engine (`urandom` / `0x00` / `0xFF`) with explicit disk cache synchronization (`fsync`).
- **Binary Log Reconstruction:** Re-seeds critical binary databases (`wtmp`, `btmp`, `lastlog`, `utmp`) with minimal valid empty structures to eliminate suspicious zero-byte log anomalies.
- **Race Condition Prevention:** Stops and unhooks active logging daemons (`systemd-journald`, `rsyslog`, `auditd`, `acct`) prior to file purging to prevent newly spawned file handles.
- **Cloud Infrastructure Neutralization:** Wipes cloud initialization artifacts and telemetry from AWS, Google Cloud Engine (GCE), Microsoft Azure (`waagent`), and generic `cloud-init` instances.
- **Package Manager Footprint Purge:** Sanitizes repository transaction records and caches across `apt`, `dpkg`, `yum`, `dnf`, and `zypper`.
- **Live Memory & Network Flushing:** Flushes kernel ring buffers (`dmesg`), ARP neighbor tables, and conntrack state tables.
- **Orphaned File Descriptor Termination:** Identifies and terminates background processes holding unlinked `(deleted)` log file descriptors.
- **Storage Subsystem Scrubbing:** Supports SSD TRIM triggers (`fstrim`) and multi-pass unallocated space zeroing (`sfill` / zero-fill chunking).
- **Zero External Dependencies:** Built entirely with the Python standard library for maximum portability across bare-metal, VPS, and air-gapped instances.

---

## Power Level Matrix

| Level | Profile | Target Scope | Forensic Impact | Free-Space Scrub |
| :---: | :--- | :--- | :---: | :---: |
| **1** | **Soft** | Shell history, core system logs, binary accounting databases (`wtmp`/`btmp`) | Low | No |
| **2** | **Standard** | Level 1 + systemd journal, audit subsystem, package history, cloud metadata | Moderate | No |
| **3** | **Ultra** | Level 2 + network state flush, open log FD process kill, SSD TRIM, user runtimes | High | No |
| **4** | **Nuclear** | Level 3 + recursive multi-mount free-space overwrite and zero-fill | Maximum | **Yes** |

---

## Forensic Artifact Coverage

### 1. Shell & Editor Histories
- Histories: `.bash_history`, `.zsh_history`, `.sh_history`, `.python_history`, `.ipython`, `.mysql_history`, `.psql_history`, `.node_repl_history`, `.nano_history`.
- Editor Cache: `.viminfo`, `.vim/undo/*`, Vim swap files (`.*.swp`, `.*.swo`), and `.local/share/recently-used.xbel`.

### 2. System & Authentication Logs
- System Trails: `/var/log/auth.log*`, `/var/log/secure*`, `/var/log/messages*`, `/var/log/syslog*`, `/var/log/kern.log*`.
- Service Daemon Logs: Nginx, Apache2, MySQL, PostgreSQL, Redis, RabbitMQ, Docker container JSON logs.
- Security Daemon Logs: Fail2ban, UFW, Firewalld, Iptables, Suricata, Snort, OSSEC, Lynis.

### 3. Binary Identity & Accounting Databases
- Preserves structure while wiping content: `/var/log/wtmp`, `/var/log/btmp`, `/var/log/lastlog`, `/var/log/faillog`, `/run/utmp`, `/var/log/tallylog`, `/etc/security/opasswd`.

### 4. Audit & System Journal
- Journal vacuuming: `/var/log/journal/*`, `/run/log/journal/*`, `/var/lib/systemd/catalog/*`.
- Kernel Auditing: Disables dynamic audit framework (`auditctl -e 0 -D`) and clears audit logs under `/var/log/audit/`.

### 5. Network & Dynamic Ephemeral State
- ARP neighbor caches (`ip neigh flush all`).
- Active connection tracking states (`conntrack -F` / `/proc/net/nf_conntrack`).
- Ephemeral SSH session sockets under `/tmp/ssh-*` and `/run/user/*/ssh-*`.

---

## System Requirements

- **Operating System:** Linux (Debian, Ubuntu, RHEL, CentOS, Rocky Linux, AlmaLinux, Fedora, Arch Linux, Alpine).
- **Runtime:** Python `3.6` or later.
- **Privileges:** `root` (UID `0`).

### Optional Acceleration Tools
While completely standalone, the script automatically detects and utilizes the following system binaries if present:
- `shred` / `wipe` (Cryptographic multi-pass file shredding)
- `sfill` (from `secure-delete` package for advanced free-space wiping)
- `fstrim` (Solid-state drive TRIM optimization)
- `conntrack` (Connection tracking table flushing)

---

## Installation

```bash
# Clone the repository
git clone https://github.com/tausifzaman/Linux-trace-remover.git
cd trace-remover

# Ensure executable permissions
chmod +x trace_remover.py
```

---

## Usage Guide

### Interactive Mode

The interactive mode offers visual safety prompts and level confirmations:

```bash
sudo python3 trace_remover.py
```

### CLI Automation Flags

For automated CI/CD runners, deployment scripts, or non-interactive execution:

```bash
# Run Soft clean (Level 1)
sudo python3 trace_remover.py --soft

# Run Ultra clean (Level 3 - aggressive)
sudo python3 trace_remover.py --ultra

# Run Nuclear clean (Level 4 - comprehensive free-space scrub)
sudo python3 trace_remover.py --nuclear
```

---

## Unreachable Vectors & Limitations

Complete host sanitation requires defense-in-depth awareness. Trace Remover **cannot** alter or sanitize:

- **Centralized Log Collectors:** Syslog forwarders, Splunk, Elastic, AWS CloudWatch, Datadog.
- **Cloud Control Planes:** VPC flow logs, hypervisor snapshot delta files, AWS CloudTrail, GCP Audit Logs.
- **Hardware Controller Memory:** Wear-leveling blocks managed by SSD Flash Translation Layers (FTL).
- **Filesystem Snapshots:** Read-only snapshots in copy-on-write filesystems (`Btrfs`, `ZFS`, `LVM thin-pool`).
- **Volatile Execution State:** eBPF probes loaded in kernel space or volatile RAM prior to a hard power reset.

---

## Recommended Post-Clean Steps

After running Trace Remover, sanitize the invoking shell session and trigger a kernel reboot:

```bash
# Clear active in-memory shell history
history -c
history -w
unset HISTFILE
export HISTSIZE=0

# Perform immediate hardware reboot
sudo reboot
```

---

## Safety and Legal Notice

> **DISCLAIMER:** This utility is intended strictly for authorized security auditing, educational lab management, personal VPS privacy, and authorized hygiene exercises. Modifying or destroying system logs without explicit authorization is illegal under computer misuse legislation. The author assumes no liability for damages or regulatory violations resulting from improper usage.

---

## Contributing

Contributions, bug reports, and pull requests are encouraged:

1. Fork the Project.
2. Create your Feature Branch (`git checkout -b feature/NewLogTarget`).
3. Commit your Changes (`git commit -m 'Add log definition for Podman containers'`).
4. Push to the Branch (`git push origin feature/NewLogTarget`).
5. Open a Pull Request.

---

## License

Distributed under the **MIT License**. See `LICENSE` for more information.
