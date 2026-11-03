#!/usr/bin/env python3
"""Read-only local maintenance gate. Never invokes provisioning."""
from pathlib import Path
import subprocess
import sys
root = Path.cwd()
if not (root / 'ansible/playbooks/workstation.yml').exists():
    sys.exit('Run from ubuntu-workstations repository root.')
checks = [
    ('Git whitespace', ['git', 'diff', '--check']),
    ('Ansible syntax', ['ansible-playbook', 'playbooks/workstation.yml', '--syntax-check']),
    ('Health audit syntax', ['ansible-playbook', 'playbooks/validate-workstation.yml', '--syntax-check']),
]
failures = 0
for label, command in checks:
    working_dir = root / 'ansible' if command[0] == 'ansible-playbook' else root
    print(f'\n=== {label} ===', flush=True)
    try:
        result = subprocess.run(command, cwd=working_dir, check=False)
        if result.returncode:
            failures += 1
    except FileNotFoundError:
        print(f'ERROR: {command[0]} not found.', file=sys.stderr)
        failures += 1
print(f'\nMaintenance gate: {"PASS" if not failures else "FAIL"} ({failures} failed checks)')
raise SystemExit(1 if failures else 0)
