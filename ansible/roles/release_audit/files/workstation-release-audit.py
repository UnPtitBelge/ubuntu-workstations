#!/usr/bin/env python3
"""Read-only workstation v1.2 readiness assessment; no changes are made."""
import argparse
import datetime as dt
import os
from pathlib import Path
import socket
import subprocess
import sys

USER_TIMERS = [
    'workstation-proton-backup.timer',
    'workstation-health.timer',
    'workstation-drift.timer',
    'workstation-backup-health.timer',
    'workstation-weekly-report.timer',
    'workstation-desktop-alerts.timer',
    'workstation-tool-update-check.timer',
    'workstation-tool-update-alerts.timer',
    'workstation-post-update-validation.timer',
]
SYSTEM_TIMERS = ['apt-daily.timer', 'apt-daily-upgrade.timer']
REPORTS = {
    'system health': '.local/state/workstation-health/latest.txt',
    'configuration drift': '.local/state/workstation-drift/latest.txt',
    'backup health': '.local/state/workstation-backup-monitor/latest.txt',
    'weekly report': '.local/state/workstation-weekly-report/latest.txt',
    'tool updates': '.local/state/workstation-tool-updates/latest.txt',
}


def call(*args):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=15, check=False)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, '', str(exc)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default=str(Path.home() / '.local/state/workstation-release-audit/latest.txt'))
    args = parser.parse_args()
    failures = []
    lines = [
        'WORKSTATION v1.2 RELEASE READINESS AUDIT',
        'Host: ' + socket.gethostname(),
        'Time: ' + dt.datetime.now().astimezone().isoformat(timespec='seconds'),
        'Mode: READ ONLY',
        '',
    ]

    def verify(label, good, detail):
        lines.append(f"[{'OK' if good else 'FAIL'}] {label}: {detail}")
        if not good:
            failures.append(label)

    user = os.environ.get('USER') or str(os.getuid())
    code, value, error = call('loginctl', 'show-user', user, '-p', 'Linger', '--value')
    verify('User lingering', code == 0 and value == 'yes', value or error or 'unavailable')

    for unit in SYSTEM_TIMERS:
        _, enabled, _ = call('systemctl', 'is-enabled', unit)
        _, active, _ = call('systemctl', 'is-active', unit)
        verify(unit, enabled == 'enabled' and active == 'active', f'enabled={enabled or "unknown"}, active={active or "unknown"}')

    for unit in USER_TIMERS:
        _, enabled, _ = call('systemctl', '--user', 'is-enabled', unit)
        _, active, _ = call('systemctl', '--user', 'is-active', unit)
        verify(unit, enabled == 'enabled' and active == 'active', f'enabled={enabled or "unknown"}, active={active or "unknown"}')

    unit = 'workstation-post-update-validation.path'
    _, enabled, _ = call('systemctl', '--user', 'is-enabled', unit)
    _, active, _ = call('systemctl', '--user', 'is-active', unit)
    verify(unit, enabled == 'enabled' and active == 'active', f'enabled={enabled or "unknown"}, active={active or "unknown"}')

    for label, relative in REPORTS.items():
        path = Path.home() / relative
        exists = path.is_file() and path.stat().st_size > 0
        if exists:
            content = path.read_text(errors='replace')
            status_lines = [line.strip() for line in content.splitlines() if line.startswith('OVERALL:')]
            if status_lines:
                healthy = status_lines[-1] in ('OVERALL: HEALTHY', 'OVERALL: NO DRIFT DETECTED')
                verify(label + ' report', healthy, status_lines[-1])
            else:
                # Update discovery ends with SUMMARY instead of OVERALL.
                good = label == 'tool updates' and 'SUMMARY: REPORT GENERATED' in content
                verify(label + ' report', good, str(path) + ' (status unrecognized)' if not good else 'generated')
        else:
            verify(label + ' report', False, f'missing/empty: {path}')

    for binary in ['workstation-tool-update-policy', 'workstation-apt-update-review', 'workstation-post-update-validate']:
        path = Path.home() / '.local/bin' / binary
        verify(binary + ' executable', path.is_file() and os.access(path, os.X_OK), str(path))

    code, output, error = call('docker', 'info', '--format', '{{.ServerVersion}}')
    verify('Docker API', code == 0, output or error or 'unavailable')

    code, output, error = call('systemctl', '--user', 'show', 'workstation-proton-backup.service', '-p', 'Result', '--value')
    # No run yet can yield success as a default, so just report the service result separately.
    lines.append('[INFO] Last backup service result: ' + (output or error or 'unknown'))
    lines.append('[INFO] GNOME notification delivery must be tested in an active desktop session.')
    lines.append('[INFO] This audit does not verify remote backup contents or detect all configuration drift.')
    lines.extend(['', 'OVERALL: ' + ('ATTENTION REQUIRED' if failures else 'READY FOR RELEASE')])

    result = '\n'.join(lines) + '\n'
    output_path = Path(args.output).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result)
    print(result, end='')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
