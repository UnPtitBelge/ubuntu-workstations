#!/usr/bin/env python3
"""Read-only proposal for changing Ansible-pinned mise tools.

No installations, no edits. An explicit Git-reviewed Ansible change is the
only approval mechanism; the existing languages role remains responsible for
actual installation.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import tomllib


def run(*argv: str) -> tuple[int, str]:
    try:
        p = subprocess.run(argv, text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=90, check=False)
        return p.returncode, (p.stdout.strip() or p.stderr.strip())
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)


def find_repo() -> Path | None:
    override = os.environ.get('WORKSTATION_REPO')
    start = Path(override).expanduser() if override else Path.home() / 'Projects/ubuntu-workstations'
    if (start / 'ansible').is_dir():
        return start
    return None


def node_pin(config: dict) -> str | None:
    item = config.get('tools', {}).get('node')
    if isinstance(item, str):
        return item
    if isinstance(item, list) and item and isinstance(item[0], str):
        return item[0]
    if isinstance(item, dict) and isinstance(item.get('version'), str):
        return item['version']
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description='Read-only mise pin review (no updates performed)')
    parser.add_argument('--minimum-release-age', default='7d', help='Mise candidate maturity (default: 7d)')
    args = parser.parse_args()
    home = Path.home()
    config_path = home / '.config/mise/config.toml'
    print('CONTROLLED TOOL UPDATE REVIEW — READ ONLY')
    print(f'Mise configuration: {config_path}')
    if not config_path.is_file():
        print('[ERROR] Global mise config missing. No update proposal generated.')
        return 2
    try:
        config = tomllib.loads(config_path.read_text())
    except (OSError, ValueError) as e:
        print(f'[ERROR] Cannot parse mise config: {e}')
        return 2
    pin = node_pin(config)
    if not pin:
        print('[INFO] Node is not declared in global mise config. Skipping.')
        return 0
    # Only exact versions are eligible. Major must stay unchanged.
    match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)', pin)
    if not match:
        print(f'[REVIEW] Node request {pin!r} is not an exact major.minor.patch pin.')
        print('        No upgrade recommendation: review the Ansible source first.')
        return 0
    major = int(match.group(1))
    code, latest = run('mise', 'latest', f'node@{major}', '--minimum-release-age', args.minimum_release_age)
    if code:
        print(f'[UNKNOWN] Cannot check available Node {major}.x release: {latest}')
        return 2
    if not re.fullmatch(r'\d+\.\d+\.\d+', latest):
        print(f'[UNKNOWN] Unexpected mise response: {latest!r}')
        return 2
    current_tuple = tuple(map(int, pin.split('.')))
    latest_tuple = tuple(map(int, latest.split('.')))
    if latest_tuple[0] != major:
        print('[ERROR] Candidate violates configured major-version boundary; refusing proposal.')
        return 2
    print(f'Node approved major: {major}')
    print(f'Node currently pinned: {pin}')
    print(f'Node candidate (>= {args.minimum_release_age} old): {latest}')
    if latest_tuple > current_tuple:
        print(f'[PROPOSAL] Node {pin} -> {latest} (same major; requires approval in Git)')
        repo = find_repo()
        if repo:
            code, matches = run('rg', '-n', '-F', pin, str(repo / 'ansible'))
            print('Potential Ansible pin source(s):')
            print(matches if code == 0 else '  Not found; locate the managed pin before changing anything.')
            print(f'Run from: {repo}')
        else:
            print('Locate the Ansible-managed Node pin in your repository before changing it.')
        print('Approval workflow: edit the Ansible pin, review Git diff, run desktop playbook, validate, commit.')
    elif latest_tuple == current_tuple:
        print('[OK] No newer Node release within the approved major and maturity window.')
    else:
        print('[INFO] Current pin is newer than the selected age-filtered candidate; no downgrade.')
    print('Java, npm CLI packages, Rust, Docker and Proton: no automatic changes; review independently.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
