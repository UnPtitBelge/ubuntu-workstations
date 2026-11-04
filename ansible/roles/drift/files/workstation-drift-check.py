#!/usr/bin/env python3
"""Read-only drift audit for explicitly baselined workstation files."""

import datetime
import hashlib
import json
import os
import socket
import sys
from pathlib import Path

STATE = Path.home() / ".local" / "state" / "workstation-drift"
BASELINE = STATE / "baseline.json"
REPORT = STATE / "latest.txt"


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    lines = [
        "WORKSTATION CONFIGURATION DRIFT REPORT",
        "Host: " + socket.gethostname(),
        "Time: " + datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "Scope: selected Ansible-managed files (not a full-system audit)",
        "",
    ]
    issues = 0
    try:
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        if baseline.get("schema") != 1 or not isinstance(baseline.get("files"), list):
            raise ValueError("unsupported baseline format")
        if not baseline["files"]:
            raise ValueError("baseline contains no files")
        for entry in baseline["files"]:
            label = entry["label"]
            path = Path(entry["path"])
            expected = entry["sha256"]
            try:
                if not path.is_file():
                    lines.append("[DRIFT] " + label + ": missing: " + str(path))
                    issues += 1
                elif sha256_file(path) != expected:
                    lines.append("[DRIFT] " + label + ": content changed: " + str(path))
                    issues += 1
                else:
                    lines.append("[OK] " + label)
            except (OSError, ValueError) as exc:
                lines.append("[ERROR] " + label + ": " + str(exc))
                issues += 1
    except (OSError, ValueError, KeyError, TypeError) as exc:
        lines.append("[ERROR] Cannot load baseline: " + str(exc))
        issues += 1
    lines.extend(["", "OVERALL: ATTENTION REQUIRED" if issues else "OVERALL: NO DRIFT DETECTED"])
    report = "\n".join(lines) + "\n"
    print(report, end="")
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(report, encoding="utf-8")
    except OSError as exc:
        print("Could not write drift report: " + str(exc), file=sys.stderr)
        return 1
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
