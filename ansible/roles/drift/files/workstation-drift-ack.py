#!/usr/bin/env python3
"""Acknowledge an out-of-band edit to a drift-monitored file.

Usage:
  workstation-drift-ack <label>   record the file's current SHA-256 as accepted
  workstation-drift-ack --list    show acknowledged entries
  workstation-drift-ack --clear <label>   remove an acknowledgement

An acknowledged edit is reported as [ACCEPTED] (still visible) instead of
[DRIFT]; it stops counting as an issue until the file changes again or
provisioning re-baselines it.
"""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import sys

STATE = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "workstation-drift"
BASELINE = STATE / "baseline.json"
ACCEPTED = STATE / "accepted.json"


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_accepted():
    try:
        data = json.loads(ACCEPTED.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("entries"), list):
            return data
    except (OSError, ValueError):
        pass
    return {"schema": 1, "entries": []}


def save_accepted(data):
    STATE.mkdir(parents=True, exist_ok=True)
    tmp = ACCEPTED.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(ACCEPTED)


def find_entry(label):
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    for entry in baseline.get("files", []):
        if entry.get("label") == label:
            return entry
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("label", nargs="?", help="drift target label to acknowledge")
    parser.add_argument("--list", action="store_true", help="list acknowledged entries")
    parser.add_argument("--clear", metavar="LABEL", help="remove an acknowledgement")
    args = parser.parse_args()

    if args.list:
        data = load_accepted()
        if not data["entries"]:
            print("No acknowledged drift entries.")
            return 0
        for entry in data["entries"]:
            print(f"[ACCEPTED] {entry.get('label')}: sha256={entry.get('sha256')} "
                  f"at {entry.get('accepted_at')} (path: {entry.get('path')})")
        return 0

    if args.clear:
        data = load_accepted()
        before = len(data["entries"])
        data["entries"] = [e for e in data["entries"] if e.get("label") != args.clear]
        if len(data["entries"]) == before:
            print(f"No acknowledgement found for label: {args.clear}", file=sys.stderr)
            return 1
        save_accepted(data)
        print(f"Cleared acknowledgement for: {args.clear}")
        return 0

    if not args.label:
        parser.error("provide a label, or use --list / --clear LABEL")
    entry = find_entry(args.label)
    if entry is None:
        print(f"Unknown drift target label: {args.label}", file=sys.stderr)
        print("Known labels: " + ", ".join(e.get("label", "?") for e in
              json.loads(BASELINE.read_text(encoding="utf-8")).get("files", [])), file=sys.stderr)
        return 2
    path = Path(entry["path"])
    if not path.is_file():
        print(f"Cannot acknowledge: file missing: {path}", file=sys.stderr)
        return 1
    digest = sha256_file(path)
    data = load_accepted()
    data["entries"] = [e for e in data["entries"] if e.get("label") != args.label]
    data["entries"].append({
        "label": args.label,
        "path": entry["path"],
        "sha256": digest,
        "accepted_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
    })
    save_accepted(data)
    print(f"Acknowledged '{args.label}' (sha256={digest[:16]}...); "
          f"it will be reported as [ACCEPTED] until it changes again.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
