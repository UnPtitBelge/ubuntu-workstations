#!/usr/bin/env python3
import datetime
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

WARN_PERCENT = 85
issues = []
lines = []

def record(ok, label, detail):
    status = "OK" if ok else "WARN"
    lines.append(f"[{status}] {label}: {detail}")
    if not ok:
        issues.append(label)

def command(*args):
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return result.returncode, result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)

def check_service(name, user=False):
    args = ["systemctl"]
    if user:
        args.append("--user")
    code, output = command(*args, "is-active", name)
    record(code == 0 and output == "active", name, output or "inactive")

def check_timer(name):
    code1, enabled = command("systemctl", "is-enabled", name)
    code2, active = command("systemctl", "is-active", name)
    ok = code1 == 0 and code2 == 0 and active == "active"
    record(ok, name, f"enabled={enabled}; active={active}")

def check_disk(path):
    usage = shutil.disk_usage(path)
    percent = round(100 * usage.used / usage.total)
    record(percent < WARN_PERCENT, f"Disk {path}", f"{percent}% used")

lines.append("WORKSTATION HEALTH REPORT")
lines.append(f"Host: {socket.gethostname()}")
lines.append("Time: " + datetime.datetime.now().astimezone().isoformat(timespec="seconds"))
lines.append("")

check_disk("/")

home = Path.home()
if os.stat("/").st_dev != os.stat(home).st_dev:
    check_disk(str(home))

check_service("docker.service")
check_service("syncthing.service", user=True)

check_timer("apt-daily.timer")
check_timer("apt-daily-upgrade.timer")

reboot_required = Path("/var/run/reboot-required").exists()
record(not reboot_required, "Reboot required", "yes" if reboot_required else "no")

lines.append("")
lines.append("OVERALL: ATTENTION REQUIRED" if issues else "OVERALL: HEALTHY")

report = "
".join(lines) + "
"

destination = home / ".local" / "state" / "workstation-health"
destination.mkdir(parents=True, exist_ok=True)
(destination / "latest.txt").write_text(report)

print(report, end="")
sys.exit(1 if issues else 0)
