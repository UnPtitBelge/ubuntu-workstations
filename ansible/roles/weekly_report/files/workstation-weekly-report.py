#!/usr/bin/env python3
"""Consolidate existing workstation reports; does not repair or run backups."""

import argparse
from datetime import datetime
from pathlib import Path
import re
import socket
import sys
import time

SOURCES = (
    ("System health", ".local/state/workstation-health/latest.txt", "HEALTHY"),
    ("Configuration drift", ".local/state/workstation-drift/latest.txt", "NO DRIFT DETECTED"),
    ("Proton Drive backup", ".local/state/workstation-backup-monitor/latest.txt", "HEALTHY"),
)
OVERALL_RE = re.compile(r"^OVERALL:\s*(.+?)\s*$", re.MULTILINE)
DETAIL_RE = re.compile(r"^\[(?:OK|WARN|DRIFT|FAIL|ERROR)\].*$", re.MULTILINE)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-age-hours", type=float, default=48)
    args = parser.parse_args()
    if args.max_age_hours <= 0:
        parser.error("--max-age-hours must be positive")

    home = Path.home()
    destination = home / ".local/state/workstation-weekly-report/latest.txt"
    lines = [
        "WORKSTATION WEEKLY MAINTENANCE REPORT",
        f"Host: {socket.gethostname()}",
        "Generated: " + datetime.now().astimezone().isoformat(timespec="seconds"),
        f"Maximum source report age: {args.max_age_hours:g} hours",
        "",
    ]
    issues = []
    now = time.time()

    for name, relative, expected in SOURCES:
        path = home / relative
        lines.append(f"== {name} ==")
        if not path.is_file():
            issues.append(name)
            lines.append(f"[WARN] Report missing: {path}")
            lines.append("")
            continue
        try:
            age_hours = (now - path.stat().st_mtime) / 3600
            report = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            issues.append(name)
            lines.extend([f"[WARN] Cannot read report: {exc}", ""])
            continue

        if not 0 <= age_hours <= args.max_age_hours:
            issues.append(name)
            lines.append(f"[WARN] Report age {age_hours:.1f}h exceeds limit {args.max_age_hours:g}h")
        else:
            lines.append(f"[OK] Report age: {age_hours:.1f}h")

        matches = OVERALL_RE.findall(report)
        if len(matches) != 1:
            issues.append(name)
            lines.append("[WARN] Expected exactly one OVERALL status line")
        else:
            actual = matches[0].strip()
            if actual == expected:
                lines.append(f"[OK] Report status: {actual}")
            else:
                issues.append(name)
                lines.append(f"[WARN] Report status: {actual} (expected {expected})")
        details = DETAIL_RE.findall(report)
        if details:
            lines.extend("  " + detail for detail in details)
        lines.append("")

    lines.append("OVERALL: ATTENTION REQUIRED" if issues else "OVERALL: HEALTHY")
    output = "\n".join(lines) + "\n"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(output, encoding="utf-8")
    print(output, end="")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
