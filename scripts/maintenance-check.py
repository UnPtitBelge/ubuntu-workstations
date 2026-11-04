#!/usr/bin/env python3
"""Repository validation shared by local development and CI; never provisions."""
from pathlib import Path
import py_compile
import subprocess
import sys
import tempfile


def main():
    root = Path(__file__).resolve().parents[1]
    checks = [
        ('Git whitespace', ['git', 'diff', '--check'], root),
        ('Repository audit', [sys.executable, 'scripts/audit-workstation.py', '.'], root),
        ('Regression tests', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], root),
    ]
    checks.extend(
        (f'Ansible syntax: {path.stem}',
         ['ansible-playbook', f'playbooks/{path.name}', '--syntax-check'], root / 'ansible')
        for path in sorted((root / 'ansible/playbooks').glob('*.yml'))
    )
    checks.append(('Inventory parses', ['ansible-inventory', '-i', 'inventory/hosts.yml', '--graph'], root / 'ansible'))
    failures = 0
    print('=== Python compilation ===', flush=True)
    # Temporary bytecode avoids modifying deployed source directories.
    with tempfile.TemporaryDirectory(prefix='workstation-compile-') as tmp:
        paths = sorted(path for directory in ('ansible', 'scripts', 'tests')
                       for path in (root / directory).rglob('*.py'))
        for index, path in enumerate(paths):
            try:
                py_compile.compile(str(path), cfile=str(Path(tmp) / f'{index}.pyc'), doraise=True)
            except py_compile.PyCompileError as exc:
                print(exc, file=sys.stderr)
                failures += 1
    for label, command, working_dir in checks:
        print(f'\n=== {label} ===', flush=True)
        try:
            if subprocess.run(command, cwd=working_dir, check=False).returncode:
                failures += 1
        except FileNotFoundError:
            print(f'ERROR: {command[0]} not found.', file=sys.stderr)
            failures += 1
    print(f'\nMaintenance gate: {"PASS" if not failures else "FAIL"} ({failures} failed checks)')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
