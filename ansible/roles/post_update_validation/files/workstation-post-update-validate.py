#!/usr/bin/env python3
"""Read-only post-APT-update checks for Docker and Proton VPN."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

GROUPS = {
    "docker": ("docker-ce", "docker-ce-cli", "containerd.io", "docker-buildx-plugin", "docker-compose-plugin", "docker-ce-rootless-extras"),
    "proton": ("proton-vpn-gnome-desktop",),
}
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "workstation-post-update"
VERSIONS_FILE = STATE_DIR / "versions.json"
REPORT_FILE = STATE_DIR / "latest.txt"


def run(*args, timeout=25):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        return p.returncode, (p.stdout or p.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)


def versions():
    found = {}
    for group, packages in GROUPS.items():
        found[group] = {}
        for pkg in packages:
            rc, output = run("dpkg-query", "-W", "-f=${Status}|${Version}", pkg)
            found[group][pkg] = (output.split("|", 1)[1] if rc == 0 and output.startswith("install ok installed|") else None)
    return found


def save_versions(data):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temp = VERSIONS_FILE.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    temp.replace(VERSIONS_FILE)


def checks(changed_groups):
    results = []
    def record(ok, desc, detail):
        results.append((ok, desc, detail))

    if "docker" in changed_groups:
        rc, status = run("systemctl", "is-active", "docker.service")
        record(rc == 0 and status == "active", "Docker service", status)
        rc, output = run("docker", "info", "--format", "{{.ServerVersion}}")
        record(rc == 0 and bool(output), "Docker API", output)
        rc, output = run("docker", "compose", "version", "--short")
        record(rc == 0, "Docker Compose", output)
        rc, output = run("docker", "buildx", "version")
        record(rc == 0, "Docker Buildx", output)
    if "proton" in changed_groups:
        rc, output = run("dpkg-query", "-W", "-f=${Status}", "proton-vpn-gnome-desktop")
        record(rc == 0 and output == "install ok installed", "Proton VPN package", output)
        # Connectivity and authenticated VPN state intentionally not assumed.
        record(True, "Proton VPN session", "Not checked (manual connection test recommended)")
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--baseline", action="store_true", help="Save currently installed package versions as the reference (no validation)")
    mode.add_argument("--watch", action="store_true", help="Validate if monitored APT package versions changed since the last successful check")
    mode.add_argument("--check", choices=["docker", "proton", "all"], help="Force read-only validation now")
    args = parser.parse_args()
    current = versions()

    if args.baseline:
        save_versions(current)
        print("Baseline saved; no packages changed and no validation executed.")
        return 0

    if args.watch:
        if not VERSIONS_FILE.exists():
            print("No baseline yet; run --baseline after installation. No result marked healthy.")
            return 2
        try:
            old = json.loads(VERSIONS_FILE.read_text())
        except (OSError, ValueError) as exc:
            print(f"Invalid baseline: {exc}", file=sys.stderr)
            return 2
        groups = [group for group in GROUPS if current[group] != old.get(group)]
        if not groups:
            print("No monitored package-version changes; no validation required.")
            return 0
    else:
        groups = list(GROUPS) if args.check == "all" else [args.check]

    results = checks(groups)
    lines = ["WORKSTATION POST-UPDATE VALIDATION", f"Host: {socket.gethostname()}", f"Time: {dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec='seconds')}", "Mode: READ ONLY", f"Scope: {', '.join(groups)}", ""]
    if args.watch:
        for group in groups:
            for pkg, after in current[group].items():
                before = old.get(group, {}).get(pkg)
                if before != after:
                    lines.append(f"[CHANGE] {pkg}: {before or '(not installed)'} -> {after or '(not installed)'}")
        lines.append("")
    for ok, title, detail in results:
        lines.append(f"[{'OK' if ok else 'FAIL'}] {title}: {detail}")
    good = all(row[0] for row in results)
    lines += ["", "OVERALL: " + ("HEALTHY" if good else "ATTENTION REQUIRED")]
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    # Keep old baseline after a failure: the next unrelated APT transaction can re-check.
    # A successful manual check records current versions too, so subsequent watch checks are meaningful.
    if good:
        save_versions(current)
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
