#!/usr/bin/env python3
"""Read-only drift audit for explicitly baselined workstation files.

Semantics (docs/WORKSTATION-CHEATSHEET.md):
  [OK]        file matches the baseline written by the last provisioning run.
  [DRIFT]     file differs from the baseline and has NOT been acknowledged —
              an unresolved out-of-band edit; counts as an issue.
  [ACCEPTED]  file differs from the baseline but matches an entry in
              accepted.json (created with `workstation-drift-ack <label>`).
              Still listed in the report, but not an issue.
  Provisioning rewrites the baseline; those re-baselines are never silent:
  every change since the previous checker run is appended to
  baseline-updates.jsonl and summarized in the report.
"""

import datetime
import hashlib
import json
import os
from pathlib import Path
import socket
import sys

STATE = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "workstation-drift"
BASELINE = STATE / "baseline.json"
LAST_SEEN = STATE / "last-seen-baseline.json"
HISTORY = STATE / "baseline-updates.jsonl"
ACCEPTED = STATE / "accepted.json"
REPORT = STATE / "latest.txt"


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def record_baseline_changes(baseline):
    """Append re-baseline events (old sha -> new sha) to the history log."""
    previous = load_json(LAST_SEEN, None)
    events = []
    if isinstance(previous, dict) and isinstance(previous.get("files"), list):
        old = {e.get("label"): e.get("sha256") for e in previous["files"] if isinstance(e, dict)}
        for entry in baseline.get("files", []):
            label = entry.get("label")
            new = entry.get("sha256")
            old_sha = old.get(label)
            if old_sha is not None and old_sha != new:
                events.append({
                    "time": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                    "event": "re-baselined by provisioning",
                    "label": label,
                    "previous_sha256": old_sha,
                    "new_sha256": new,
                })
    if events:
        STATE.mkdir(parents=True, exist_ok=True)
        with HISTORY.open("a", encoding="utf-8") as stream:
            for event in events:
                stream.write(json.dumps(event, sort_keys=True) + "\n")
    try:
        LAST_SEEN.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError:
        pass
    return events


def main():
    lines = [
        "WORKSTATION CONFIGURATION DRIFT REPORT",
        "Host: " + socket.gethostname(),
        "Time: " + datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "Scope: selected Ansible-managed files (not a full-system audit)",
        "",
    ]
    issues = 0
    rebaselines = []
    try:
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        if baseline.get("schema") not in (1, 2) or not isinstance(baseline.get("files"), list):
            raise ValueError("unsupported baseline format")
        if not baseline["files"]:
            raise ValueError("baseline contains no files")
        rebaselines = record_baseline_changes(baseline)
        accepted = load_json(ACCEPTED, {}).get("entries", [])
        accepted_by_label = {}
        for entry in accepted:
            if isinstance(entry, dict) and entry.get("label"):
                accepted_by_label[entry["label"]] = entry.get("sha256")
        for entry in baseline["files"]:
            label = entry["label"]
            path = Path(entry["path"])
            expected = entry["sha256"]
            try:
                if not path.is_file():
                    lines.append("[DRIFT] " + label + ": missing: " + str(path))
                    issues += 1
                    continue
                actual = sha256_file(path)
                if actual == expected:
                    lines.append("[OK] " + label)
                elif accepted_by_label.get(label) == actual:
                    lines.append("[ACCEPTED] " + label + ": differs from baseline, acknowledged out-of-band edit: " + str(path))
                else:
                    lines.append("[DRIFT] " + label + ": content changed: " + str(path))
                    issues += 1
            except (OSError, ValueError) as exc:
                lines.append("[ERROR] " + label + ": " + str(exc))
                issues += 1
    except (OSError, ValueError, KeyError, TypeError) as exc:
        lines.append("[ERROR] Cannot load baseline: " + str(exc))
        issues += 1
    if rebaselines:
        lines.append("")
        lines.append("Baseline refreshed by provisioning since the last run (see baseline-updates.jsonl):")
        for event in rebaselines:
            lines.append("[REBASELINED] " + str(event.get("label")))
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
