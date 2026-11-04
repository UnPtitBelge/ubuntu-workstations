#!/usr/bin/env python3
"""Read-only Proton Drive backup service and freshness monitor."""

import argparse
from datetime import datetime
from pathlib import Path
import socket
import subprocess
import sys
import time

BACKUP_SERVICE = "workstation-proton-backup.service"
BACKUP_TIMER = "workstation-proton-backup.timer"
STAMP = Path.home() / ".local/state/workstation-backup-monitor/last-success"
REPORT = Path.home() / ".local/state/workstation-backup-monitor/latest.txt"


def systemctl(*args):
    try:
        result = subprocess.run(
            ["systemctl", "--user", *args],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    output = result.stdout.strip() or result.stderr.strip()
    return result.returncode == 0, output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-age-hours", type=int, default=48)
    args = parser.parse_args()
    if args.max_age_hours < 1:
        parser.error("--max-age-hours must be positive")

    lines = [
        "PROTON DRIVE BACKUP HEALTH REPORT",
        f"Host: {socket.gethostname()}",
        "Time: " + datetime.now().astimezone().isoformat(timespec="seconds"),
        "",
    ]
    issues = []

    def check(label, ok, detail):
        lines.append(f"[{'OK' if ok else 'WARN'}] {label}: {detail}")
        if not ok:
            issues.append(label)

    enabled_ok, enabled = systemctl("is-enabled", BACKUP_TIMER)
    active_ok, active = systemctl("is-active", BACKUP_TIMER)
    check("Backup timer", enabled_ok and enabled == "enabled" and active_ok and active == "active",
          f"enabled={enabled}; active={active}")

    result_ok, result = systemctl("show", BACKUP_SERVICE, "--property=Result", "--value")
    # A service not yet run normally has Result=success; age of stamp handles that case.
    check("Last service result", result_ok and result == "success", result or "unavailable")

    if STAMP.is_file():
        age_seconds = time.time() - STAMP.stat().st_mtime
        age_hours = age_seconds / 3600
        check("Last successful backup", 0 <= age_hours <= args.max_age_hours,
              f"{age_hours:.1f} hours ago (limit: {args.max_age_hours}h)")
    else:
        check("Last successful backup", False,
              "no recorded successful run since monitoring was installed")

    lines.extend(["", "OVERALL: ATTENTION REQUIRED" if issues else "OVERALL: HEALTHY"])
    text = "\n".join(lines) + "\n"
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(text, encoding="utf-8")
    print(text, end="")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
