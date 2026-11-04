#!/usr/bin/env python3
"""Build a backup dataset manifest with per-file SHA-256 checksums.

The manifest describes exactly the files the backup selects (same rsync
filter rules as the upload), so a migration can compare source and destination
datasets by count, size and checksum instead of trusting remote UI totals.

Usage:
  workstation-backup-manifest.py --dataset-id ID --host HOST --exclude-file FILE \
      --source DIR [--source DIR ...] --output manifest.json
"""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def listed_files(source, exclude_file):
    """Filtered file list of one source via rsync --list-only (read-only).

    rsync ignores --out-format in list-only mode, so parse the default listing:
    PERMS SIZE DATE TIME NAME (name may contain spaces)."""
    cmd = [
        "rsync", "--list-only", "-m", "--no-links",
        f"--exclude-from={exclude_file}",
        source.rstrip("/") + "/",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    files = []
    for line in result.stdout.splitlines():
        parts = line.split(None, 4)
        if len(parts) < 5 or not parts[0].startswith("-"):
            continue  # only regular files ('-' permission prefix)
        size, rel = parts[1], parts[4].strip()
        files.append((rel, int(size) if size.isdigit() else None))
    if result.returncode != 0 and not files:
        raise RuntimeError(f"rsync listing failed for {source}: {result.stderr.strip()}")
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--host", default=socket.gethostname())
    parser.add_argument("--exclude-file", required=True)
    parser.add_argument("--source", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    if not Path(args.exclude_file).is_file():
        print(f"ERROR: exclude file missing: {args.exclude_file}", file=sys.stderr)
        return 1

    entries = []
    total_bytes = 0
    for source in args.source:
        source = source.rstrip("/")
        if not Path(source).is_dir():
            print(f"ERROR: missing source directory: {source}", file=sys.stderr)
            return 1
        name = os.path.basename(source)
        for rel, size in listed_files(source, args.exclude_file):
            local = Path(source) / rel
            if not local.is_file():
                continue
            digest = sha256_file(local)
            actual_size = local.stat().st_size
            total_bytes += actual_size
            entries.append({
                "path": f"{name}/{rel}",
                "size": actual_size,
                "sha256": digest,
            })

    manifest = {
        "schema_version": 1,
        "dataset_id": args.dataset_id,
        "host": args.host,
        "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "files": entries,
        "file_count": len(entries),
        "total_bytes": total_bytes,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(out)
    print(f"Manifest written: {out} ({len(entries)} files, {total_bytes} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
