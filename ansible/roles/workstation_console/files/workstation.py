#!/usr/bin/env python3
"""Local workstation dashboard with reviewed setup changes and monitoring actions."""
from __future__ import annotations

import argparse
import difflib
import hashlib
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import time
import unicodedata

LIMIT = 262144
UNIT = re.compile(r'^[A-Za-z0-9_.@:-]+\.(service|timer|path)$')
PROPERTIES = ('Id', 'LoadState', 'ActiveState', 'UnitFileState', 'Result',
              'ExecMainStatus', 'ExecMainStartTimestamp', 'ExecMainExitTimestamp',
              'LastTriggerUSec', 'NextElapseUSecRealtime', 'NextElapseUSecMonotonic')
RANK = {'HEALTHY': 0, 'DISABLED': 0, 'UNKNOWN': 1, 'STALE': 2, 'FAILED': 3}


def clean(value):
    """Strip terminal controls, including escape sequences, from untrusted text."""
    value = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', str(value))
    return ''.join(c if c in '\n\t' or not unicodedata.category(c).startswith('C') else '?' for c in value)


def read_local(path, limit=LIMIT, tail=False):
    """Bound reads and reject special files; do not hang on a FIFO/device."""
    descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('not a regular file')
        if info.st_size > limit:
            if not tail:
                raise ValueError('file exceeds size limit')
            stream.seek(-limit, os.SEEK_END)
            stream.readline()  # Discard a possibly partial first line.
        return stream.read(limit).decode('utf-8'), info.st_mtime


def timestamp_age(value, now):
    if not isinstance(value, str):
        raise ValueError('missing timestamp')
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('timestamp has no timezone')
    age = (now - stamp.timestamp()) / 3600
    if not math.isfinite(age) or age < -1 / 60:
        raise ValueError('timestamp is in the future')
    return max(0, age)


def age_label(hours):
    if hours is None:
        return 'unknown'
    if hours < 1:
        return f'{int(hours * 60)}m'
    if hours < 48:
        return f'{hours:.0f}h'
    return f'{hours / 24:.1f}d'


def run_readonly(argv):
    try:
        result = subprocess.run(argv, capture_output=True, text=True, encoding='utf-8',
                                errors='replace', timeout=4, check=False,
                                env={**os.environ, 'LC_ALL': 'C', 'SYSTEMD_COLORS': '0', 'SYSTEMD_PAGER': 'cat'})
        return result.returncode, result.stdout[:LIMIT], result.stderr[:4096]
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 2, '', f'{type(exc).__name__}: local command unavailable or timed out'


def load_config(path):
    try:
        text, _ = read_local(path)
        config = json.loads(text)
        if not isinstance(config, dict) or config.get('schema_version') != 1:
            raise ValueError('unsupported configuration schema')
        for key in ('hostname', 'inventory_host', 'profile', 'dataset_id'):
            if not isinstance(config.get(key), str) or not config[key]:
                raise ValueError(f'invalid {key}')
        for key in ('capabilities', 'providers', 'thresholds'):
            if not isinstance(config.get(key), dict):
                raise ValueError(f'invalid {key}')
        if not isinstance(config.get('settings', {}), dict):
            raise ValueError('invalid setup settings')
        if not isinstance(config.get('reports'), list) or len(config['reports']) > 32:
            raise ValueError('invalid report sources')
        for value in config['thresholds'].values():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError('invalid freshness threshold')
        for item in config['capabilities'].values():
            if not isinstance(item, dict) or not isinstance(item.get('enabled'), bool):
                raise ValueError('invalid capability switch')
        for key in ('backup_enabled', 'backup_timer_enabled', 'syncthing_enabled',
                    'syncthing_service_enabled', 'tool_update_alerts_enabled', 'security_updates_enabled'):
            if not isinstance(config.get(key), bool):
                raise ValueError(f'invalid {key}')
        if not all(isinstance(v, str) for v in config['providers'].values()):
            raise ValueError('invalid provider selection')
        if not all(key in config['capabilities'] and key in config['providers']
                   for key in ('backup', 'sync', 'vpn', 'mail', 'passwords')):
            raise ValueError('incomplete capability/provider selections')
        for item in config['reports']:
            if not isinstance(item, dict) or not all(isinstance(item.get(k), str) for k in ('name', 'path', 'expected')):
                raise ValueError('invalid report source')
            limit = item.get('max_age_hours', 48)
            if isinstance(limit, bool) or not isinstance(limit, (int, float)) or not math.isfinite(limit) or limit <= 0:
                raise ValueError('invalid report freshness threshold')
        return config, ''
    except FileNotFoundError:
        return {}, 'Console configuration missing; install with playbooks/console.yml. Intent is unknown.'
    except (OSError, ValueError, UnicodeError, TypeError, OverflowError) as exc:
        return {}, f'Console configuration invalid/unreadable ({type(exc).__name__}); intent is unknown.'


def jobs_for(config):
    known = bool(config)
    caps, providers = config.get('capabilities', {}), config.get('providers', {})
    def selected(capability):
        return caps.get(capability, {}).get('enabled', False) and providers.get(capability) not in (None, 'none')
    backup = providers.get('backup')
    prefix = {'proton/drive': 'proton', 'google/drive': 'rclone'}.get(backup)
    scheduled = selected('backup') and config.get('backup_enabled', False) and config.get('backup_timer_enabled', False)
    thresholds = config.get('thresholds', {})
    jobs = []
    def add(key, label, stem=None, report=None, kind='report', enabled=True, scope='user', max_age=48, expected='HEALTHY'):
        jobs.append(dict(id=key, label=label, service=f'{stem}.service' if stem else None,
                         timer=f'{stem}.timer' if stem and kind != 'continuous' else None,
                         scope=scope, report=f'.local/state/{report}/latest.txt' if report else None,
                         kind=kind, enabled=enabled if known else None, max_age=max_age, expected=expected))
    add('health', 'System health', 'workstation-health', 'workstation-health')
    add('drift', 'Selected-file drift', 'workstation-drift', 'workstation-drift', expected='NO DRIFT DETECTED')
    add('backup', f'Backup upload ({backup or "unconfigured"})', f'workstation-{prefix}-backup' if prefix else None,
        'workstation-backup-monitor', kind='backup', enabled=scheduled, max_age=thresholds.get('backup_hours', 48))
    add('restore', 'Restore drill evidence', f'workstation-{prefix}-backup-restore-test' if prefix else None,
        kind='restore', enabled=scheduled, max_age=thresholds.get('restore_hours', 1080))
    # A skipped/none provider does not stop its old timers. Observe both built-in
    # adapters so disabled intent never hides leftover scheduling after a swap.
    for other in ('proton', 'rclone'):
        if other != prefix:
            add(f'other-backup-{other}', f'Other {other} upload schedule', f'workstation-{other}-backup',
                kind='unit', enabled=False)
            add(f'other-restore-{other}', f'Other {other} restore schedule', f'workstation-{other}-backup-restore-test',
                kind='unit', enabled=False)
    add('summary', 'Weekly summary', 'workstation-weekly-report', 'workstation-weekly-report', max_age=192)
    add('updates', 'Update discovery', 'workstation-tool-update-check', 'workstation-tool-updates', max_age=192)
    add('post-update', 'Post-update validation', 'workstation-post-update-validation', 'workstation-post-update', kind='event')
    add('alerts', 'Failure notifications', 'workstation-desktop-alerts', kind='unit')
    add('update-alerts', 'Update notifications', 'workstation-tool-update-alerts', kind='unit',
        enabled=config.get('tool_update_alerts_enabled', True))
    add('sync', 'Syncthing', 'syncthing', kind='continuous',
        enabled=selected('sync') and providers.get('sync') == 'syncthing' and config.get('syncthing_enabled', False)
        and config.get('syncthing_service_enabled', True))
    add('apt-lists', 'Ubuntu package indexes', 'apt-daily', kind='unit', scope='system',
        enabled=config.get('security_updates_enabled', True))
    add('apt-upgrades', 'Ubuntu eligible upgrades', 'apt-daily-upgrade', kind='unit', scope='system',
        enabled=config.get('security_updates_enabled', True))
    # Respect the same report-source paths/statuses/freshness used by monitoring.
    for index, source in enumerate(config.get('reports', [])):
        match = next((job for job in jobs if job['report'] == source['path']), None)
        if match:
            match['expected'] = source['expected']
            match['max_age'] = source.get('max_age_hours', match['max_age'])
        else:
            add(f'report-{index}', source['name'])
            jobs[-1].update(report=source['path'], max_age=source.get('max_age_hours', 48), expected=source['expected'])
    return jobs


class Collector:
    def __init__(self, config_path=None, home=None, runner=run_readonly, host=None):
        self.home = Path(home) if home else Path.home()
        self.config_path = Path(config_path) if config_path else self.home / '.config/workstation/console.json'
        self.runner = runner
        self.host = host or socket.gethostname()
        self.reports = {}
        self.log_error = False

    def path(self, relative):
        path = (self.home / relative).resolve()
        if not path.is_relative_to((self.home / '.local/state').resolve()):
            raise ValueError('report path outside local state directory')
        return path

    def units(self, jobs):
        units, errors = {}, {}
        for scope in ('user', 'system'):
            names = sorted({name for job in jobs if job['scope'] == scope
                            for name in (job['service'], job['timer']) if name})
            if not names:
                continue
            if not all(UNIT.fullmatch(name) for name in names):
                errors[scope] = 'Invalid unit name'
                continue
            argv = ['systemctl'] + (['--user'] if scope == 'user' else [])
            rc, out, err = self.runner(argv + ['show', '--no-pager', '--property=' + ','.join(PROPERTIES), *names])
            for block in out.strip().split('\n\n'):
                properties = dict(line.split('=', 1) for line in block.splitlines() if '=' in line)
                if properties.get('Id') in names:
                    units[(scope, properties['Id'])] = properties
            if rc:
                # Keep the failure concise; raw local logs are shown only on request.
                errors[scope] = 'Systemd unavailable or some units not found; inspect local permissions/journal.'
            for name in names:
                if (scope, name) not in units:
                    errors.setdefault(scope, 'Systemd did not return all requested unit properties.')
        return units, errors

    def report(self, job, now):
        path = self.path(job['report'])
        text, modified = read_local(path)
        self.reports[job['id']] = clean(text)
        hours = (now - modified) / 3600
        if hours < -1 / 60:
            return 'UNKNOWN', 'Report timestamp is in the future', hours
        statuses = re.findall(r'^OVERALL:\s*(.*?)\s*$', text, re.M)
        if len(statuses) != 1:
            return 'UNKNOWN', 'Report must contain exactly one OVERALL line', hours
        if statuses[0] != job['expected']:
            return 'FAILED', 'Report requires attention; open details before replacing evidence', hours
        if job['kind'] != 'event' and hours > job['max_age']:
            return 'STALE', f'Report older than {job["max_age"]:g}h', hours
        return 'HEALTHY', 'Saved report passed' + ('; event-driven, no age alarm' if job['kind'] == 'event' else ''), hours

    def backup_evidence(self, config, now, restore=False):
        text, _ = read_local(self.path('.local/state/workstation-backup/status.json'))
        record = json.loads(text)
        if not isinstance(record, dict) or record.get('schema_version') != 1 or record.get('capability') != 'backup':
            raise ValueError('invalid backup schema')
        if (record.get('provider') != config.get('providers', {}).get('backup')
                or record.get('host') not in (self.host, self.host.split('.')[0])
                or record.get('dataset_id') != config.get('dataset_id')):
            return 'UNKNOWN', 'Backup evidence belongs to another host, provider or dataset', None
        age = timestamp_age(record.get('checked_at'), now)
        if record.get('result') != 'success':
            return 'FAILED', 'Recorded backup did not succeed', age
        if not restore:
            limit = config.get('thresholds', {}).get('backup_hours', 48)
            return ('STALE', f'Last upload older than {limit:g}h', age) if age > limit else ('HEALTHY', 'Matching upload record; not whole-dataset recovery proof', age)
        age = timestamp_age(record.get('verified_restore_at'), now)
        history, _ = read_local(self.path('.local/state/workstation-backup/restore-tests.jsonl'), tail=True)
        records = [json.loads(line) for line in history.splitlines() if line.strip()]
        if not all(isinstance(item, dict) for item in records):
            raise ValueError('invalid restore history')
        matching = [item for item in records if item.get('provider') == record['provider']]
        if not matching:
            return 'UNKNOWN', 'No matching restore history; timestamp alone is not proof', age
        last = matching[-1]
        if last.get('host') != record['host'] or last.get('dataset_id') != record['dataset_id']:
            return 'UNKNOWN', 'Restore history lacks matching host/dataset attribution; verify recovery separately', age
        history_age = timestamp_age(last.get('time'), now)
        if last.get('result') != 'success':
            return 'FAILED', 'Latest matching restore attempt failed', history_age
        if abs(age - history_age) > 1 / 60:
            return 'UNKNOWN', 'Restore timestamp and history disagree', age
        limit = config.get('thresholds', {}).get('restore_hours', 1080)
        return ('STALE', 'Verified restore evidence is too old', age) if age > limit else ('HEALTHY', 'Matching single-file restore evidence; not a full recovery test', age)

    def snapshot(self):
        now = time.time()
        config, warning = load_config(self.config_path)
        if config.get('hostname') not in (None, self.host, self.host.split('.')[0]):
            warning = 'Configuration snapshot belongs to another host; configured intent is not trusted.'
            config = {}
        jobs = jobs_for(config)
        units, errors = self.units(jobs)
        self.reports = {}
        rows = []
        for job in jobs:
            service = units.get((job['scope'], job['service']), {})
            timer = units.get((job['scope'], job['timer']), {})
            row = {**job, 'state': 'HEALTHY', 'reasons': [], 'age_hours': None,
                   'service_properties': service, 'timer_properties': timer,
                   'next_run': timer.get('NextElapseUSecRealtime') or
                   ('boot-relative: ' + timer['NextElapseUSecMonotonic'] if timer.get('NextElapseUSecMonotonic') else 'unknown'),
                   'last_trigger': timer.get('LastTriggerUSec') or 'unknown',
                   'activity': service.get('ActiveState', 'unknown')}
            def mark(state, reason):
                if RANK[state] > RANK[row['state']]:
                    row['state'] = state
                row['reasons'].append(reason)
            observed = [props for name, props in ((job['service'], service), (job['timer'], timer)) if name]
            if job['enabled'] is False:
                if any(not props or props.get('LoadState') not in ('loaded', 'not-found', 'masked') for props in observed):
                    mark('UNKNOWN', 'Disabled intent, but installed unit state could not be read')
                elif any(props.get('ActiveState') in ('active', 'activating') or props.get('UnitFileState') == 'enabled'
                         for props in observed if props.get('Id', '').endswith('.timer') or job['kind'] == 'continuous'):
                    mark('FAILED', 'Disabled in configured intent, but an observed schedule/service is still enabled or active')
                else:
                    row['state'] = 'DISABLED'
                    row['reasons'].append('Disabled/not selected in deployed intent; existing data and reports are retained')
                rows.append(row)
                continue
            if job['enabled'] is None:
                mark('UNKNOWN', 'Configured intent is unknown')
            for props in observed:
                if not props or props.get('LoadState') != 'loaded' or not props.get('ActiveState'):
                    mark('UNKNOWN', 'Required unit missing, masked or unavailable')
                elif props.get('ActiveState') == 'failed' or props.get('Result') not in (None, '', 'success'):
                    mark('FAILED', 'Last systemd invocation failed; inspect the selected journal')
            if job['timer'] and timer.get('LoadState') == 'loaded':
                if timer.get('UnitFileState') != 'enabled' or timer.get('ActiveState') != 'active':
                    mark('FAILED', 'Expected timer is not enabled and active')
            if job['kind'] == 'continuous' and service.get('LoadState') == 'loaded' and service.get('ActiveState') != 'active':
                mark('FAILED', 'Expected continuous service is not running')
            if job['report']:
                try:
                    state, reason, age = self.report(job, now)
                    row['age_hours'] = age
                    mark(state, reason)
                except (OSError, ValueError, UnicodeError) as exc:
                    mark('UNKNOWN', f'Report missing/unreadable/invalid ({type(exc).__name__})')
            if job['kind'] in ('backup', 'restore'):
                if not job['service']:
                    mark('UNKNOWN', 'No monitoring adapter registered for the selected backup provider')
                try:
                    state, reason, age = self.backup_evidence(config, now, job['kind'] == 'restore')
                    row['age_hours'] = age
                    mark(state, reason)
                except FileNotFoundError as exc:
                    name = Path(exc.filename).name if exc.filename else 'evidence file'
                    mark('UNKNOWN', f'{name} is missing; see the evidence paths in details')
                except json.JSONDecodeError:
                    mark('UNKNOWN', 'Backup/restore metadata is invalid JSON; inspect the evidence paths in details')
                except (OSError, ValueError, TypeError, OverflowError, UnicodeError):
                    mark('UNKNOWN', 'Backup/restore format or timestamp could not be verified; inspect evidence and journal')
            if job['kind'] == 'event':
                try:
                    baseline, _ = read_local(self.path('.local/state/workstation-post-update/versions.json'))
                    baseline_data = json.loads(baseline)
                    if not isinstance(baseline_data, dict) or not baseline_data:
                        raise ValueError('empty baseline')
                except (OSError, ValueError, UnicodeError):
                    mark('UNKNOWN', 'Post-update version baseline missing or invalid; review the journal before establishing one')
            if job['kind'] == 'unit' and (not service.get('ExecMainStartTimestamp') or not service.get('ExecMainExitTimestamp') or not service.get('Result')):
                mark('UNKNOWN', 'No recorded completed service execution; schedule alone is not success')
            if job['kind'] == 'unit' and service.get('ExecMainExitTimestamp') and not job['report']:
                row['reasons'].append('Local invocation passed; notification delivery is not verified' if job['id'] in ('alerts', 'update-alerts')
                                      else 'Last local invocation passed; this does not authorize upgrades or a reboot')
            if job['kind'] == 'continuous':
                row['reasons'].append('Service availability only; peer connectivity and synchronization are not verified')
            rows.append(row)
        overall = max((row['state'] for row in rows), key=lambda state: RANK[state], default='UNKNOWN')
        if warning and RANK[overall] < RANK['UNKNOWN']:
            overall = 'UNKNOWN'
        return dict(schema_version=1, observed_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
                    host=self.host, profile=config.get('profile', 'unknown'), inventory_host=config.get('inventory_host', 'unknown'),
                    config_path=str(self.config_path), config_warning=warning, providers=config.get('providers', {}),
                    overall=overall, systemd_errors=errors, jobs=rows)

    def logs(self, row):
        self.log_error = False
        if not row['service']:
            self.log_error = True
            return 'No service registered for this item.'
        argv = ['journalctl'] + (['--user'] if row['scope'] == 'user' else [])
        rc, out, err = self.runner(argv + ['--no-pager', '--quiet', '-n', '40', '-o', 'short-iso', '-u', row['service']])
        self.log_error = bool(rc)
        return clean(out or ('Journal unavailable; check permissions.' if rc else 'No journal entries available.'))


def details(row, report=None):
    lines = [row['label'] + ' — ' + row['state'], '', 'Evidence age: ' + age_label(row['age_hours']),
             'Observed service: ' + str(row['service'] or 'not registered'),
             'Scope: ' + row['scope'], 'Activity: ' + row['activity'],
             'Timer: ' + str(row['timer'] or 'not registered'),
             'Last trigger: ' + row['last_trigger'], 'Next run: ' + row['next_run'], '',
             *['• ' + reason for reason in row['reasons']], '',
             'Next: inspect the evidence and journal; refresh a helper only after reviewing the failure.']
    if row['report']:
        lines.extend(['', 'Report path: ~/' + row['report']])
    if row['kind'] in ('backup', 'restore'):
        lines.append('Backup status: ~/.local/state/workstation-backup/status.json')
    if row['kind'] == 'restore':
        lines.append('Restore history: ~/.local/state/workstation-backup/restore-tests.jsonl')
    if report is not None:
        lines.extend(['', 'LOCAL REPORT (may contain private paths; not exported automatically)', '', report])
    return '\n'.join(lines)


def text_status(snapshot):
    lines = [f'WORKSTATION  {clean(snapshot["host"])}  profile={clean(snapshot["profile"])}',
             f'Observed: {snapshot["observed_at"]}   Overall: {snapshot["overall"]}',
             'Intent: deployed console configuration, not a live comparison with Git.']
    if snapshot['config_warning']:
        lines.append(snapshot['config_warning'])
    for row in snapshot['jobs']:
        lines.append(f'{row["state"]:9} {clean(row["label"]):36.36} {age_label(row["age_hours"]):>7}  ' + clean('; '.join(row['reasons'])))
    return '\n'.join(lines)


# Only these existing user oneshot services may be started by the console.
# Configured custom report paths can never introduce executable commands.
RUNNABLE = {
    'health': ('workstation-health.service', 'Checks local disks/services and replaces the health report.'),
    'drift': ('workstation-drift.service', 'Checks selected files and replaces the drift report; records observed baseline history. Does not acknowledge drift or change the baseline.'),
    'summary': ('workstation-weekly-report.service', 'Reads existing reports and replaces the weekly summary. Does not rerun source checks.'),
    'updates': ('workstation-tool-update-check.service', 'Queries upstream version sources and cached APT candidates; replaces the update report. Installs nothing.'),
    'alerts': ('workstation-desktop-alerts.service', 'Reads saved reports and may send GNOME notifications and update notification deduplication state. Requires a graphical session for delivery.'),
    'update-alerts': ('workstation-tool-update-alerts.service', 'Reads the update report and may send GNOME notifications and update notification deduplication state. Installs nothing.'),
}


def category_for(row):
    key = row['id']
    if key in ('health', 'drift'):
        return 'health'
    if key in ('backup', 'restore') or key.startswith(('other-backup-', 'other-restore-')):
        return 'backup'
    if key in ('updates', 'post-update', 'update-alerts', 'apt-lists', 'apt-upgrades'):
        return 'updates'
    if key in ('alerts', 'sync'):
        return 'services'
    return 'reports'


def action_plan(snapshot, job_id):
    """Fail closed; a missing report may be checked, untrusted intent may not."""
    if snapshot.get('config_warning'):
        raise ValueError('Console intent is unavailable or belongs to another host; reconcile its configuration first.')
    if job_id not in RUNNABLE:
        raise ValueError('Manual execution is not available for this job. Backup/restore, upgrades, continuous services and custom reports remain inspection-only.')
    row = next((row for row in snapshot['jobs'] if row['id'] == job_id), None)
    service, effect = RUNNABLE[job_id]
    if not row or row['enabled'] is not True or row['scope'] != 'user' or row['service'] != service:
        raise ValueError('This job is disabled or its deployed intent does not match a supported user service.')
    props = row['service_properties']
    if props.get('LoadState') != 'loaded':
        raise ValueError('The service is missing, masked or unavailable; deploy/inspect it first.')
    if props.get('ActiveState') not in ('inactive', 'failed'):
        raise ValueError('The service is running, transitioning or its activity is unknown. Inspect its journal before trying again.')
    return dict(id=job_id, host=snapshot['host'], label=row['label'], service=service, effect=effect,
                command=['systemctl', '--user', '--no-ask-password', 'start', service])


def run_service(argv):
    """Explicit mutation boundary: invoked only after a user confirms a plan."""
    try:
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=120, check=False,
                                env={**os.environ, 'LC_ALL': 'C', 'SYSTEMD_COLORS': '0', 'SYSTEMD_PAGER': 'cat'})
        return result.returncode
    except subprocess.TimeoutExpired:
        return None  # systemctl timing out does not stop the systemd job.
    except OSError:
        return 2


def run_job(collector, confirmed_plan, runner=run_service):
    # Recheck on the worker immediately before execution; never trust a cached row.
    try:
        plan = action_plan(collector.snapshot(), confirmed_plan['id'])
        if plan != confirmed_plan:
            raise ValueError('Job intent changed after confirmation; review a new plan.')
    except ValueError as exc:
        return 'NOT STARTED: ' + str(exc)
    code = runner(plan['command'])
    if code is None:
        return 'OUTCOME UNKNOWN: timed out waiting for ' + plan['service'] + '. It may still be running. Inspect its journal; no stop or automatic retry was issued.'
    if code:
        return f'FAILED: {plan["service"]} returned systemctl exit {code}. Inspect its journal and report before retrying.'
    return 'COMPLETED: ' + plan['service'] + '. The service invocation finished; inspect the reread evidence for the job outcome. This does not prove notification delivery.'


EDITABLE = {
    'workstation_backup_on_calendar': str,
    'workstation_backup_restore_test_calendar': str,
    'workstation_backup_sources': list,
    'workstation_backup_excludes': list,
    'workstation_backup_timer_enabled': bool,
    'workstation_tool_update_alerts_enabled': bool,
    'workstation_python_versions': list,
    'workstation_role_gnome': bool,
    'workstation_role_containers': bool,
    'workstation_role_virtualization': bool,
    'workstation_role_languages': bool,
}


class SetupManager:
    """Reviewable host-file edits and an interactive Ansible execution boundary."""
    def __init__(self, collector, repo=None):
        self.collector = collector
        self.repo = Path(repo or collector.home / 'Projects/ubuntu-workstations').resolve()
        self.preview_token = None

    def context(self):
        config, warning = load_config(self.collector.config_path)
        if warning or config.get('hostname') not in (self.collector.host, self.collector.host.split('.')[0]):
            raise ValueError('Trusted local console intent is required. Reinstall the console for this machine.')
        host = config['inventory_host']
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', host):
            raise ValueError('Invalid local inventory target.')
        if not (self.repo / 'ansible/playbooks/workstation.yml').is_file():
            raise ValueError('Repository unavailable. Start with --repo /path/to/ubuntu-workstations.')
        target = self.repo / 'ansible/inventory/host_vars' / (host + '.yml')
        if target.is_symlink() or not target.resolve().is_relative_to(self.repo):
            raise ValueError('Host configuration must be a regular file inside the repository.')
        return config, target

    def document(self, target):
        import yaml
        class UniqueLoader(yaml.SafeLoader):
            def construct_mapping(self, node, deep=False):
                self.flatten_mapping(node)
                keys = [self.construct_object(key, deep=deep) for key, _ in node.value]
                if not all(isinstance(key, str) for key in keys) or len(keys) != len(set(keys)):
                    raise ValueError('Configuration has duplicate or non-string YAML keys; edit it manually.')
                return super().construct_mapping(node, deep)
        text, _ = read_local(target)
        try:
            data = yaml.load(text, Loader=UniqueLoader)
        except yaml.YAMLError as exc:
            raise ValueError('Host configuration is invalid YAML; fix it manually before editing.') from exc
        if not isinstance(data, dict):
            raise ValueError('Host configuration must be a YAML mapping.')
        return text, data

    def settings(self):
        config, target = self.context()
        _, data = self.document(target)
        effective = dict(config.get('settings', {}))
        effective.update({key: value for key, value in data.items() if key in EDITABLE})
        return {key: effective[key] for key in EDITABLE if key in effective}

    def propose(self, edited):
        import yaml
        if not isinstance(edited, dict) or set(edited) - EDITABLE.keys():
            raise ValueError('Use only the supported setting names shown in the editor.')
        for key, value in edited.items():
            if type(value) is not EDITABLE[key]:
                raise ValueError(key + ' has the wrong value type.')
            values = value if isinstance(value, list) else [value] if isinstance(value, str) else []
            if len(values) > 256 or any(not isinstance(item, str) or not item.strip() or
                                      len(item) > 4096 or any(c in item for c in ('\x00', '\n', '\r', '{{', '{%'))
                                      for item in values):
                raise ValueError(key + ' requires plain, nonempty strings without templates.')
        config, target = self.context()
        before, data = self.document(target)
        if 'workstation_device_name' in data:
            raise ValueError('Move machine identity to the documented local identity file before editing here.')
        current = self.settings()
        updates = {key: value for key, value in edited.items() if current.get(key) != value}
        # Replace only changed value spans; retain unrelated comments/formatting.
        # Anchors can couple otherwise unrelated settings, so require manual edits.
        if any(isinstance(token, (yaml.tokens.AnchorToken, yaml.tokens.AliasToken)) for token in yaml.scan(before)):
            raise ValueError('YAML anchors/aliases require manual editing.')
        node = yaml.compose(before)
        spans, additions = [], dict(updates)
        for key_node, value_node in node.value:
            key = key_node.value
            if key in updates:
                value = yaml.safe_dump(updates[key], default_flow_style=True, width=4096,
                                       allow_unicode=True).strip().removesuffix('\n...')
                end = value_node.end_mark.index
                if isinstance(value_node, yaml.SequenceNode) and not value_node.flow_style and value_node.value:
                    end = value_node.value[-1].end_mark.index
                old = before[value_node.start_mark.index:end]
                if old.endswith('\n'):
                    value += '\n'
                spans.append((value_node.start_mark.index, end, value))
                additions.pop(key)
        after = before
        for start, end, value in sorted(spans, reverse=True):
            after = after[:start] + value + after[end:]
        if additions:
            after += ('' if after.endswith('\n') else '\n') + yaml.safe_dump(additions, sort_keys=False)
        expected = {**data, **updates}
        if len(after.encode()) > LIMIT or yaml.safe_load(after) != expected:
            raise ValueError('Cannot safely represent this edit. Edit the inventory manually.')
        diff = ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                           fromfile=str(target), tofile=str(target)))
        return dict(host=config['inventory_host'], path=target, before=before, after=after, diff=diff)

    def save(self, plan):
        config, target = self.context()
        if target != plan['path'] or config['inventory_host'] != plan['host'] or read_local(target)[0] != plan['before']:
            raise ValueError('Configuration changed during review. Edit and review it again.')
        # Exclusive lock prevents concurrent console writers; atomic replacement
        # preserves the old file if writing fails. No other inventory file changes.
        temporary = target.with_name(target.name + '.console-tmp')
        created = False
        try:
            with temporary.open('x', encoding='utf-8') as stream:
                created = True
                if read_local(target)[0] != plan['before']:
                    raise ValueError('Configuration changed during review. Edit and review it again.')
                os.chmod(temporary, target.stat().st_mode & 0o777)
                stream.write(plan['after'])
            os.replace(temporary, target)
        except Exception:
            if created and temporary.exists():
                temporary.unlink()
            raise
        self.preview_token = None

    def fingerprint(self):
        digest = hashlib.sha256()
        for folder in ('ansible', 'profiles', 'scripts', 'dotfiles', 'assets'):
            for path in sorted((self.repo / folder).rglob('*')):
                if path.is_file() and '__pycache__' not in path.parts and not path.name.endswith('.pyc'):
                    digest.update(str(path.relative_to(self.repo)).encode())
                    digest.update(path.read_bytes())
        return digest.hexdigest()

    def command(self, operation):
        config, _ = self.context()
        # Read inventory afresh without displaying potentially private variables.
        rc, out, _ = self.collector.runner(['ansible-inventory', '--playbook-dir', str(self.repo / 'ansible'),
            '-i', str(self.repo / 'ansible/inventory/hosts.yml'), '--host', config['inventory_host']])
        try:
            intent = json.loads(out)
        except ValueError:
            intent = {}
        if rc or not isinstance(intent, dict) or intent.get('ansible_connection') != 'local':
            raise ValueError('Cannot verify a local inventory connection; no Ansible action started.')
        identity = intent.get('workstation_device_name', '')
        if not isinstance(identity, str):
            raise ValueError('Invalid declared machine identity.')
        if identity and not identity.startswith('<') and identity not in (self.collector.host, self.collector.host.split('.')[0]):
            raise ValueError('Inventory identity does not match this machine.')
        if operation not in ('preview', 'apply', 'audit'):
            raise ValueError('Unsupported Ansible action.')
        if operation == 'apply' and self.preview_token != self.fingerprint():
            raise ValueError('A successful preview of the current repository is required before apply.')
        play = 'validate-workstation.yml' if operation == 'audit' else 'workstation.yml'
        args = ['ansible-playbook', '-i', 'inventory/hosts.yml', 'playbooks/' + play,
                '--limit', config['inventory_host'], '-K']
        if operation == 'preview':
            args.extend(['--check', '--diff'])
        if operation == 'audit':
            args.extend(['-e', 'audit_enforce=true'])
        return args


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, help='Deployed console JSON (default: ~/.config/workstation/console.json)')
    parser.add_argument('--repo', type=Path, help='Configuration repository (default: ~/Projects/ubuntu-workstations)')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--status', action='store_true', help='Print a local status snapshot')
    mode.add_argument('--json', action='store_true', help='Print schema-versioned status; excludes raw report bodies/logs')
    mode.add_argument('--detail', metavar='JOB', help='Print one job and its existing report; may show private paths')
    mode.add_argument('--logs', metavar='JOB', help='Print last 40 selected service journal lines; may show private data')
    mode.add_argument('--dashboard', action='store_true', help='Serve the local web dashboard (default)')
    parser.add_argument('--port', type=int, default=8765, help='Loopback dashboard port (default: 8765)')
    parser.add_argument('--demo', action='store_true', help='Dashboard with sample data; no host reads or actions')
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error('--port must be between 0 and 65535')
    if args.demo and any((args.status, args.json, args.detail, args.logs)):
        parser.error('--demo is only available for the dashboard')
    collector = Collector(args.config)
    if any((args.status, args.json, args.detail, args.logs)):
        snapshot = collector.snapshot()
        if args.json:
            print(json.dumps(snapshot, indent=2, ensure_ascii=True))
        elif args.detail or args.logs:
            job = next((row for row in snapshot['jobs'] if row['id'] == (args.detail or args.logs)), None)
            if job is None:
                parser.error('unknown job; available IDs: ' + ', '.join(row['id'] for row in snapshot['jobs']))
            print(collector.logs(job) if args.logs else clean(details(job, collector.reports.get(job['id'], 'No saved report.'))))
        else:
            print(text_status(snapshot))
        return 0 if snapshot['overall'] in ('HEALTHY', 'DISABLED') and not collector.log_error else 1
    import importlib.util
    source_assets = Path(__file__).resolve().parent / 'web'
    assets = source_assets if source_assets.is_dir() else Path.home() / '.local/share/workstation/web'
    try:
        spec = importlib.util.spec_from_file_location('workstation_web', assets / 'server.py')
        web = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(web)
        backend = sys.modules.get(__name__)
        if backend is None:
            # main() is also exercised through importlib by repository tests.
            from types import SimpleNamespace
            backend = SimpleNamespace(**globals())
        web.serve(backend, collector, SetupManager(collector, args.repo), assets, args.port, args.demo)
    except KeyboardInterrupt:
        return 0
    except (OSError, ImportError) as exc:
        parser.exit(2, f'Dashboard unavailable ({type(exc).__name__}): {exc}. Use --status meanwhile.\n')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
