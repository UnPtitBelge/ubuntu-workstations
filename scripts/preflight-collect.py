#!/usr/bin/env python3
"""Read-only provider-migration preflight inventory (docs/MIGRATE.md stage A).

Collects, per capability, the selected provider, data locations and volumes,
service/unit state and authentication *presence* — never secret values. Tokens,
keys, full Syncthing device IDs and credentials are never printed; device IDs
are truncated to a 7-character prefix for comparison only.

Run directly or via ansible/playbooks/provider-preflight.yml.
"""

import argparse
import datetime
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import xml.etree.ElementTree as ET


def run(*args, timeout=15):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)


def systemctl_user(*args):
    return run("systemctl", "--user", *args)


def unit_state(unit):
    rc, enabled = systemctl_user("is-enabled", unit)
    rc2, active = systemctl_user("is-active", unit)
    rc3, result = systemctl_user("show", unit, "--property=Result", "--value")
    return {
        "enabled": enabled.strip() if rc == 0 else "unknown",
        "active": active.strip() if rc2 == 0 else "unknown",
        "last_result": result.strip() if rc3 == 0 else "unknown",
    }


def dataset_stats(sources, exclude_file):
    """Filtered file count and bytes per source, using the same rsync rules
    as the backup (read-only listing)."""
    stats = []
    for source in sources:
        source = source.rstrip("/")
        entry = {"source": source, "exists": Path(source).is_dir()}
        if entry["exists"] and exclude_file and Path(exclude_file).is_file():
            # rsync ignores --out-format in list-only mode: parse the default
            # listing PERMS SIZE DATE TIME NAME (name may contain spaces).
            rc, out = run("rsync", "--list-only", "-m", "--no-links",
                          f"--exclude-from={exclude_file}", source + "/")
            files = []
            for line in out.splitlines():
                parts = line.split(None, 4)
                if len(parts) >= 5 and parts[0].startswith("-") and parts[1].isdigit():
                    files.append(int(parts[1]))
            entry["files"] = len(files)
            entry["bytes"] = sum(files)
        elif entry["exists"]:
            count = 0
            total = 0
            for root, _dirs, names in os.walk(source):
                for name in names:
                    try:
                        st = os.stat(os.path.join(root, name))
                        count += 1
                        total += st.st_size
                    except OSError:
                        pass
            entry["files"] = count
            entry["bytes"] = total
            entry["note"] = "unfiltered count (no exclude file found)"
        stats.append(entry)
    return stats


def backup_section(ctx, lines):
    lines.append("== capability: backup ==")
    provider = ctx["providers"].get("backup", "none")
    lines.append(f"provider: {provider}")
    if provider == "none":
        lines.append("disabled")
        return
    lines.append(f"dataset_id: {ctx.get('dataset_id', '?')}")
    remote = ctx.get("remote_parent") or "(not set)"
    lines.append(f"remote destination: {remote}")
    for entry in dataset_stats(ctx.get("backup_sources", []), ctx.get("exclude_file")):
        if entry.get("exists"):
            note = f" ({entry['note']})" if entry.get("note") else ""
            lines.append(f"  source {entry['source']}: {entry.get('files', '?')} files, "
                         f"{entry.get('bytes', '?')} bytes{note}")
        else:
            lines.append(f"  source {entry['source']}: MISSING")
    status_file = Path(ctx["home"]) / ".local/state/workstation-backup/status.json"
    if status_file.is_file():
        try:
            record = json.loads(status_file.read_text(encoding="utf-8"))
            lines.append(f"  last run: result={record.get('result')} provider={record.get('provider')} "
                         f"at {record.get('checked_at')} files={record.get('files')} bytes={record.get('bytes')}")
            lines.append(f"  verified_restore_at: {record.get('verified_restore_at')}")
        except (OSError, ValueError) as exc:
            lines.append(f"  status record unreadable: {exc}")
    else:
        lines.append("  last run: no normalized status record yet")
    manifest = Path(ctx["home"]) / ".local/state/workstation-backup/manifest-latest.json"
    if manifest.is_file():
        try:
            m = json.loads(manifest.read_text(encoding="utf-8"))
            lines.append(f"  manifest: {m.get('file_count')} files, {m.get('total_bytes')} bytes, "
                         f"generated {m.get('generated_at')}")
        except (OSError, ValueError):
            lines.append("  manifest: present but unreadable")
    tests = Path(ctx["home"]) / ".local/state/workstation-backup/restore-tests.jsonl"
    if tests.is_file():
        last = tests.read_text(encoding="utf-8").strip().splitlines()
        if last:
            try:
                t = json.loads(last[-1])
                lines.append(f"  last restore drill: {t.get('result')} at {t.get('time')} file={t.get('file')}")
            except ValueError:
                lines.append("  last restore drill: unparseable entry")
    unit_map = {
        "proton/drive": "workstation-proton-backup.timer",
        "google/drive": "workstation-rclone-backup.timer",
    }
    unit = unit_map.get(provider)
    if unit:
        state = unit_state(unit)
        lines.append(f"  timer {unit}: enabled={state['enabled']} active={state['active']} "
                     f"last_result={state['last_result']}")
    lines.append("")


def sync_section(ctx, lines):
    lines.append("== capability: sync ==")
    provider = ctx["providers"].get("sync", "none")
    lines.append(f"provider: {provider}")
    if provider != "syncthing":
        lines.append("(no built-in data inventory for this provider)")
        lines.append("")
        return
    config = Path(ctx["home"]) / ".config/syncthing/config.xml"
    if not config.is_file():
        lines.append("  syncthing config: not present (not enrolled yet)")
        lines.append("")
        return
    try:
        root = ET.parse(config).getroot()
    except (ET.ParseError, OSError) as exc:
        lines.append(f"  syncthing config unreadable: {exc}")
        lines.append("")
        return
    my_id = root.findtext(".//device/@id") or ""
    lines.append(f"  device ID (prefix only): {my_id[:7]}...")
    folders = []
    for folder in root.findall("./folder"):
        folders.append({
            "id": folder.get("id"),
            "label": folder.get("label") or folder.get("id"),
            "path": folder.get("path"),
        })
    lines.append(f"  shared folders ({len(folders)}): " +
                 (", ".join(f"{f['label']} -> {f['path']}" for f in folders) if folders else "none"))
    apikey = root.findtext("./gui/apikey")
    if apikey:
        rc, out = run("curl", "-sS", "--max-time", "10",
                      "-H", f"X-API-Key: {apikey}", "http://127.0.0.1:8384/rest/system/status")
        if rc == 0:
            try:
                status = json.loads(out)
                lines.append(f"  local API: reachable; syncthing {status.get('version')}; "
                             f"myID prefix {str(status.get('myID', ''))[:7]}...")
            except ValueError:
                lines.append("  local API: reachable but returned non-JSON")
        else:
            lines.append("  local API: not reachable (syncthing not running in this session)")
        rc, out = run("curl", "-sS", "--max-time", "10",
                      "-H", f"X-API-Key: {apikey}", "http://127.0.0.1:8384/rest/system/connections")
        if rc == 0:
            try:
                conns = json.loads(out).get("connections", {})
                connected = sum(1 for c in conns.values() if c.get("connected"))
                lines.append(f"  connected peers: {connected}/{len(conns)}")
            except ValueError:
                pass
    else:
        lines.append("  local API: no API key in config (GUI API disabled)")
    state = unit_state("syncthing.service")
    lines.append(f"  user service syncthing.service: enabled={state['enabled']} active={state['active']} "
                 f"last_result={state['last_result']}")
    lines.append("")


def vpn_section(ctx, lines):
    lines.append("== capability: vpn ==")
    provider = ctx["providers"].get("vpn", "none")
    lines.append(f"provider: {provider}")
    home = Path(ctx["home"])
    if provider == "wireguard":
        conf_dir = home / ".config/wireguard"
        confs = sorted(p.name for p in conf_dir.glob("*.conf")) if conf_dir.is_dir() else []
        lines.append(f"  config files present: {', '.join(confs) if confs else 'none (manual enrollment)'}")
        for conf in confs:
            iface = conf[:-5]
            rc, out = run("sudo", "-n", "wg", "show", iface)
            if rc == 0:
                handshake = [l for l in out.splitlines() if "latest handshake" in l]
                transfer = [l for l in out.splitlines() if "transfer" in l]
                lines.append(f"  {iface}: " + (handshake[0].strip() if handshake else "no handshake yet") +
                             ("; " + transfer[0].strip() if transfer else ""))
            else:
                lines.append(f"  {iface}: not currently up (wg show needs the tunnel up; manual check)")
    elif provider.startswith("proton"):
        rc, out = run("dpkg-query", "-W", "-f=${Package} ${Status}\n", "*proton*")
        installed = [l.split()[0] for l in out.splitlines() if "install ok installed" in l]
        lines.append(f"  proton packages installed: {', '.join(installed) if installed else 'none'}")
        lines.append("  authenticated session: manual (keyring) — presence not probed by this tool")
    else:
        lines.append("  (no built-in checks for this provider; see docs/PROVIDERS.md)")
    lines.append("")


def passwords_section(ctx, lines):
    lines.append("== capability: passwords ==")
    provider = ctx["providers"].get("passwords", "none")
    lines.append(f"provider: {provider}")
    home = Path(ctx["home"])
    if provider == "keepassxc":
        vault = Path(ctx.get("keepassxc_vault") or (home / "Documents/Passwords.kdbx"))
        if vault.is_file():
            st = vault.stat()
            in_backup = any(str(vault).startswith(s.rstrip("/")) for s in ctx.get("backup_sources", []))
            lines.append(f"  vault file: {vault} ({st.st_size} bytes, mtime "
                         f"{datetime.datetime.fromtimestamp(st.st_mtime).isoformat(timespec='seconds')})")
            lines.append(f"  vault inside backup sources: {in_backup}")
        else:
            lines.append(f"  vault file: not created yet ({vault})")
        lines.append("  master password/key file: never probed or printed")
    elif provider.startswith("proton"):
        rc, out = run("dpkg-query", "-W", "-f=${Status}", "proton-pass")
        lines.append(f"  proton-pass package: {'installed' if 'install ok installed' in out else 'not installed'}")
        lines.append("  session/CLI login: manual — not probed")
    else:
        lines.append("  (no built-in checks; see docs/PROVIDERS.md)")
    lines.append("")


def mail_section(ctx, lines):
    lines.append("== capability: mail ==")
    provider = ctx["providers"].get("mail", "none")
    lines.append(f"provider: {provider}")
    home = Path(ctx["home"])
    if provider == "google/mail":
        profiles = sorted(p.name for p in (home / ".thunderbird").glob("*.default*")) \
            if (home / ".thunderbird").is_dir() else []
        lines.append(f"  thunderbird profiles: {', '.join(profiles) if profiles else 'none yet (manual account setup)'}")
        lines.append("  account credentials: stored in the profile/keyring — never probed or printed")
    elif provider.startswith("proton"):
        rc, out = run("dpkg-query", "-W", "-f=${Status}", "proton-mail")
        lines.append(f"  proton-mail package: {'installed' if 'install ok installed' in out else 'not installed'}")
        lines.append("  account session: manual — not probed")
    else:
        lines.append("  (no built-in checks; see docs/PROVIDERS.md)")
    lines.append("")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", default=str(Path.home()))
    parser.add_argument("--providers", default="{}", help="JSON of workstation_providers")
    parser.add_argument("--backup-sources", default="[]", help="JSON list of backup sources")
    parser.add_argument("--exclude-file", default="",
                        help="backup exclude file (proton or rclone path; auto-detected if empty)")
    parser.add_argument("--remote-parent", default="")
    parser.add_argument("--dataset-id", default="")
    parser.add_argument("--keepassxc-vault", default="")
    parser.add_argument("--output", default="", help="also write the report to this file")
    args = parser.parse_args()

    home = args.home
    try:
        providers = json.loads(args.providers)
        sources = json.loads(args.backup_sources)
    except ValueError as exc:
        print(f"ERROR: invalid JSON argument: {exc}", file=sys.stderr)
        return 2

    exclude_file = args.exclude_file
    if not exclude_file:
        for candidate in (".config/workstation-proton-backup/excludes.txt",
                          ".config/workstation-rclone-backup/excludes.txt"):
            if (Path(home) / candidate).is_file():
                exclude_file = str(Path(home) / candidate)
                break

    ctx = {
        "home": home,
        "providers": providers,
        "backup_sources": sources,
        "exclude_file": exclude_file,
        "remote_parent": args.remote_parent,
        "dataset_id": args.dataset_id,
        "keepassxc_vault": args.keepassxc_vault,
    }

    lines = [
        "WORKSTATION PROVIDER PREFLIGHT INVENTORY (read-only; no secrets)",
        f"Host: {socket.gethostname()}",
        "Time: " + datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "Purpose: docs/MIGRATE.md stage A — inventory before any provider change.",
        "",
    ]
    backup_section(ctx, lines)
    sync_section(ctx, lines)
    vpn_section(ctx, lines)
    passwords_section(ctx, lines)
    mail_section(ctx, lines)
    report = "\n".join(lines) + "\n"
    print(report, end="")
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(out.suffix + ".tmp")
        tmp.write_text(report, encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(out)
        print(f"Report written to {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
