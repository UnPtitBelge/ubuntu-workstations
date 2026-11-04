#!/usr/bin/env python3
"""Read an existing tool update report and notify about available updates.

Does not install, refresh or modify development tools or APT packages.
"""

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def active_graphical_session():
    """Only attempt notifications during an active, local graphical login."""
    try:
        result = subprocess.run(
            ["loginctl", "list-sessions", "--no-legend", "--no-pager"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        if result.returncode != 0:
            return False
        uid = str(os.getuid())
        for line in result.stdout.splitlines():
            parts = line.split()
            if not parts:
                continue
            session_id = parts[0]
            details = subprocess.run(
                ["loginctl", "show-session", session_id,
                 "--property=User", "--property=Active", "--property=Type",
                 "--property=Remote", "--property=Class"],
                capture_output=True, text=True, timeout=10, check=False,
            )
            if details.returncode != 0:
                continue
            props = dict(row.split("=", 1) for row in details.stdout.splitlines() if "=" in row)
            if (props.get("User") == uid and props.get("Active") == "yes"
                    and props.get("Type") in ("wayland", "x11")
                    and props.get("Remote") == "no"
                    and props.get("Class") == "user"):
                return True
    except (OSError, subprocess.TimeoutExpired):
        return False
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--test-notification", action="store_true")
    parser.add_argument("--max-age-hours", type=float, default=192)
    parser.add_argument("--repeat-hours", type=float, default=168)
    args = parser.parse_args()
    if args.max_age_hours <= 0 or args.repeat_hours <= 0:
        parser.error("time limits must be positive")

    if args.test_notification:
        if not active_graphical_session():
            print("No active local graphical session; notification not sent")
            return 1
        result = subprocess.run(
            ["notify-send", "--app-name=Workstation Maintenance",
             "Workstation update alerts test", "GNOME notifications are working."],
            check=False,
        )
        return result.returncode

    home = Path.home()
    report = home / ".local/state/workstation-tool-updates/latest.txt"
    state_dir = home / ".local/state/workstation-tool-update-alerts"
    state_path = state_dir / "last-notification.json"
    now = dt.datetime.now(dt.timezone.utc)

    if not report.is_file():
        print(f"SKIPPED: no update report ({report}). Run workstation-tool-update-check first.")
        return 0
    age_hours = (now.timestamp() - report.stat().st_mtime) / 3600
    if age_hours > args.max_age_hours or age_hours < -1:
        print(f"SKIPPED: update report is stale or dated in the future ({age_hours:.1f}h).")
        return 0

    content = report.read_text(encoding="utf-8", errors="replace")
    if "SUMMARY: REPORT GENERATED" not in content:
        print("SKIPPED: report lacks successful completion marker.")
        return 0

    # Only [AVAILABLE] lines count. Error/status text is handled by other monitoring.
    available = [line.strip() for line in content.splitlines()
                 if re.match(r"^\[AVAILABLE\]\s+", line)]
    if not available:
        print("HEALTHY: no available development updates reported")
        return 0

    if state_path.is_file():
        try:
            data = json.loads(state_path.read_text())
            previous = dt.datetime.fromisoformat(data["sent_at"])
            if previous.tzinfo is not None:
                elapsed = (now - previous).total_seconds() / 3600
                if 0 <= elapsed < args.repeat_hours:
                    print(f"SUPPRESSED: last update notification sent {elapsed:.1f}h ago")
                    return 0
        except (ValueError, KeyError, TypeError, OSError):
            pass

    title = f"Development updates available ({len(available)})"
    body = "\n".join(available[:3])
    if len(available) > 3:
        body += f"\n...and {len(available) - 3} more"
    body += "\nSee workstation-tool-update-check for details."

    if args.dry_run:
        print("DRY RUN: would send notification")
        print(title)
        print(body)
        return 0

    if not active_graphical_session():
        print("DEFERRED: no active local graphical session; will retry on next timer run")
        return 0

    try:
        result = subprocess.run(
            ["notify-send", "--app-name=Workstation Maintenance", "--urgency=low", title, body],
            capture_output=True, text=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: notification delivery failed: {exc}", file=sys.stderr)
        return 1
    if result.returncode != 0:
        print(f"ERROR: notification delivery failed: {result.stderr.strip()}", file=sys.stderr)
        return 1
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"sent_at": now.isoformat(), "available": available}, indent=2) + "\n")
    print(f"NOTIFIED: {len(available)} development update(s) available")
    return 0


if __name__ == "__main__":
    sys.exit(main())
