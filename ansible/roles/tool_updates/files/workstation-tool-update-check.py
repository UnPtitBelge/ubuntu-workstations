#!/usr/bin/env python3
"""Read-only update inventory for the local workstation. No upgrades performed."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys


def executable(name, *relative_fallbacks):
    for candidate in [shutil.which(name), *(str(Path.home() / x) for x in relative_fallbacks)]:
        if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def run(argv, timeout=120):
    try:
        return subprocess.run(
            argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout, cwd=Path.home(), check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return str(exc)


def parse_policy(output):
    result = {}
    for line in output.splitlines():
        line = line.strip()
        for key in ('Installed', 'Candidate'):
            if line.startswith(key + ':'):
                result[key.lower()] = line.split(':', 1)[1].strip()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apt-package', action='append', default=[])
    args = parser.parse_args()
    lines = [
        'WORKSTATION DEVELOPMENT UPDATE REPORT',
        f'Host: {socket.gethostname()}',
        'Time: ' + datetime.now().astimezone().isoformat(timespec='seconds'),
        'Mode: READ ONLY (no updates installed)',
        '',
        '=== MISE (GLOBAL TOOL REQUESTS) ===',
    ]
    errors = 0
    mise = executable('mise', '.local/bin/mise')
    if mise is None:
        lines.append('[UNKNOWN] mise executable not found')
        errors += 1
    else:
        result = run([mise, 'outdated', '--global', '--json'])
        if isinstance(result, str) or result.returncode != 0:
            detail = result if isinstance(result, str) else (result.stderr.strip() or result.stdout.strip())
            lines.append('[UNKNOWN] Could not check mise: ' + str(detail)[:350])
            errors += 1
        else:
            try:
                tools = json.loads(result.stdout or '{}')
                if not isinstance(tools, dict):
                    raise ValueError('Expected JSON object')
                if tools:
                    for name, item in sorted(tools.items()):
                        if isinstance(item, dict):
                            lines.append(f"[AVAILABLE] {name}: {item.get('current', '?')} -> {item.get('latest', '?')} (requested: {item.get('requested', '?')})")
                        else:
                            lines.append(f'[AVAILABLE] {name}: {item}')
                else:
                    lines.append('[OK] No newer versions within current global mise requests')
            except (ValueError, TypeError) as exc:
                lines.append('[UNKNOWN] Could not parse mise output: ' + str(exc))
                errors += 1

    lines.extend(['', '=== RUSTUP ==='])
    rustup = executable('rustup', '.cargo/bin/rustup')
    if rustup is None:
        lines.append('[UNKNOWN] rustup executable not found')
        errors += 1
    else:
        result = run([rustup, 'check'])
        if isinstance(result, str) or result.returncode != 0:
            detail = result if isinstance(result, str) else (result.stderr.strip() or result.stdout.strip())
            lines.append('[UNKNOWN] Could not check Rust toolchains: ' + str(detail)[:350])
            errors += 1
        else:
            lines.extend(result.stdout.strip().splitlines() or ['[OK] rustup check completed'])

    lines.extend(['', '=== UV TOOLS ==='])
    uv = executable('uv', '.local/bin/uv')
    if uv is None:
        lines.append('[UNKNOWN] uv executable not found')
        errors += 1
    else:
        result = run([uv, 'tool', 'list', '--outdated'])
        if isinstance(result, str) or result.returncode != 0:
            detail = result if isinstance(result, str) else (result.stderr.strip() or result.stdout.strip())
            lines.append('[UNKNOWN] Could not check uv tools: ' + str(detail)[:350])
            errors += 1
        else:
            outdated = [ln.strip() for ln in result.stdout.splitlines()
                        if ln.strip() and not ln.startswith('-')]
            if outdated:
                for ln in outdated:
                    lines.append('[AVAILABLE] ' + ln)
            else:
                lines.append('[OK] No outdated uv tools')

    lines.extend(['', '=== APT PACKAGES (INFORMATION ONLY) ==='])
    apt_cache = executable('apt-cache')
    for package in args.apt_package:
        if apt_cache is None:
            lines.append('[UNKNOWN] apt-cache executable not found')
            errors += 1
            break
        result = run([apt_cache, 'policy', package], timeout=20)
        if isinstance(result, str) or result.returncode != 0:
            lines.append(f'[UNKNOWN] apt-cache policy failed for {package}')
            errors += 1
            continue
        policy = parse_policy(result.stdout)
        installed = policy.get('installed', '(none)')
        candidate = policy.get('candidate', '(none)')
        status = 'AVAILABLE' if installed not in ('(none)', '') and candidate not in ('(none)', '') and installed != candidate else 'OK'
        lines.append(f'[{status}] {package}: installed={installed}; candidate={candidate}')
    lines.extend(['', 'NOTE: Pinned exact mise versions may not appear as outdated.',
                  'NOTE: APT candidates are not necessarily approved for installation.',
                  'SUMMARY: CHECK ERRORS' if errors else 'SUMMARY: REPORT GENERATED',
                  'OVERALL: ' + ('ATTENTION REQUIRED' if errors else 'HEALTHY')])

    state_dir = Path.home() / '.local/state/workstation-tool-updates'
    state_dir.mkdir(parents=True, exist_ok=True)
    text = '\n'.join(lines) + '\n'
    (state_dir / 'latest.txt').write_text(text, encoding='utf-8')
    print(text, end='')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
