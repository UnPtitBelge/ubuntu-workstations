#!/usr/bin/env python3
"""Local, read-only workstation dashboard. Never runs jobs or contacts providers."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
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


def create_app(collector, interval):
    """Lazy UI imports keep the status/JSON CLI usable without Textual."""
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import VerticalScroll
    from textual.widgets import DataTable, Footer, Header, Static
    from rich.text import Text

    class ConsoleApp(App):
        TITLE = 'Workstation'
        ENABLE_COMMAND_PALETTE = False
        CSS = '''
        Screen { background: $surface; }
        #identity { height: auto; padding: 1 2; background: $panel; }
        #summary { height: auto; padding: 0 2; color: $accent; }
        #jobs { height: 1fr; margin: 1 2 0 2; border: round $primary; }
        #preview { height: 6; padding: 0 2; border-top: solid $primary; }
        #reader { height: 1fr; margin: 1 2; border: round $primary; display: none; }
        #document { height: auto; padding: 1 2; }
        #notice { height: auto; padding: 0 2; color: $text-muted; }
        .reading #jobs, .reading #preview { display: none; }
        .reading #reader { display: block; }
        .compact #identity { height: 1; padding: 0 1; }
        .compact #summary { height: 1; padding: 0 1; }
        .compact #jobs, .compact #reader { margin: 0; }
        .compact #preview { height: 3; padding: 0 1; }
        '''
        BINDINGS = [
            Binding('space', 'open_report', 'Open report', priority=True),
            Binding('enter', 'open_report', 'Open report', show=False, priority=True),
            Binding('escape', 'overview', 'Back', priority=True),
            Binding('l', 'logs', 'Journal'), Binding('r', 'reread', 'Reread'),
            Binding('?', 'help', 'Help'), Binding('q', 'quit', 'Quit', priority=True),
            Binding('j', 'move(1)', show=False), Binding('k', 'move(-1)', show=False),
        ]

        def __init__(self):
            super().__init__()
            self.snapshot = None
            self.mode = 'overview'
            self.busy = False
            self.request = 0

        def compose(self) -> ComposeResult:
            yield Header()
            yield Static('Reading local evidence…', id='identity', markup=False)
            yield Static('', id='summary', markup=False)
            yield DataTable(id='jobs', cursor_type='row', zebra_stripes=True)
            yield Static('Select a job, then press Space to open its report.', id='preview', markup=False)
            with VerticalScroll(id='reader', can_focus=True):
                yield Static('', id='document', markup=False)
            yield Static('READ ONLY • Deployed intent • No cloud requests or repairs', id='notice', markup=False)
            yield Footer()

        def on_mount(self):
            table = self.query_one(DataTable)
            table.add_columns('Job', 'State', 'Evidence age', 'Service')
            table.focus()
            self.executor = ThreadPoolExecutor(max_workers=1)
            self.pending = None
            self.last_read = time.monotonic()
            self.set_interval(0.1, self.poll)
            self.action_reread()

        def on_unmount(self):
            self.executor.shutdown(wait=False, cancel_futures=True)

        def on_resize(self, event):
            self.screen.set_class(event.size.height < 24 or event.size.width < 80, 'compact')

        def selected(self):
            if self.snapshot and self.snapshot['jobs']:
                index = min(self.query_one(DataTable).cursor_row, len(self.snapshot['jobs']) - 1)
                return self.snapshot['jobs'][index]
            return None

        def poll(self):
            if self.pending and self.pending[0].done():
                future, kind, request = self.pending
                self.pending, self.busy = None, False
                try:
                    result = future.result()
                except Exception as exc:
                    self.query_one('#notice', Static).update(f'Cannot read evidence ({type(exc).__name__}); press r to retry.')
                    self.last_read = time.monotonic()
                    return
                self.query_one('#notice', Static).update('READ ONLY • r rereads evidence; it never runs monitoring jobs.')
                if kind == 'snapshot':
                    self.apply_snapshot(result)
                    self.last_read = time.monotonic()
                elif self.mode == 'logs' and request == self.request:
                    self.query_one('#document', Static).update(clean(result))
            if not self.busy and time.monotonic() - self.last_read >= interval:
                self.action_reread()

        def apply_snapshot(self, snapshot):
            previous = self.selected()
            self.snapshot = snapshot
            table = self.query_one(DataTable)
            table.clear()
            colors = {'HEALTHY': 'green', 'FAILED': 'red', 'STALE': 'yellow', 'UNKNOWN': 'yellow', 'DISABLED': 'dim'}
            for row in snapshot['jobs']:
                table.add_row(Text(clean(row['label'])), Text(row['state'], style=colors[row['state']]),
                              Text(age_label(row['age_hours'])), Text(clean(row['activity'])), key=row['id'])
            if previous:
                index = next((i for i, row in enumerate(snapshot['jobs']) if row['id'] == previous['id']), 0)
                table.move_cursor(row=index)
            identity = f"{snapshot['host']}  /  {snapshot['profile']}  /  {snapshot['overall']}\n"
            identity += '  '.join(f'{k}={v}' for k, v in snapshot['providers'].items())
            self.query_one('#identity', Static).update(clean(identity))
            counts = '   '.join(f'{state}: {sum(row["state"] == state for row in snapshot["jobs"])}'
                                for state in ('FAILED', 'STALE', 'UNKNOWN', 'HEALTHY', 'DISABLED'))
            self.query_one('#summary', Static).update(counts + '\nObserved: ' + clean(snapshot['observed_at'])
                                                    + ('\n' + clean(snapshot['config_warning']) if snapshot['config_warning'] else ''))
            self.update_preview()
            if self.mode == 'report' and self.selected():
                row = self.selected()
                self.query_one('#document', Static).update(clean(
                    details(row, collector.reports.get(row['id'], 'No saved report.'))))

        def update_preview(self):
            row = self.selected()
            if row:
                self.query_one('#preview', Static).update(clean('\n'.join([
                    row['label'] + ' • ' + row['state'], '; '.join(row['reasons']),
                    'Last trigger: ' + row['last_trigger'], 'Next run: ' + row['next_run']])))

        def on_data_table_row_highlighted(self, event):
            self.update_preview()

        def on_data_table_row_selected(self, event):
            self.action_open_report()

        def show_document(self, mode, title, content):
            self.request += 1
            self.mode = mode
            self.screen.add_class('reading')
            reader = self.query_one('#reader', VerticalScroll)
            reader.border_title = clean(title)
            self.query_one('#document', Static).update(clean(content))
            reader.scroll_home(animate=False)
            reader.focus()

        def action_open_report(self):
            row = self.selected()
            if row:
                self.show_document('report', row['label'] + ' / saved report',
                                   details(row, collector.reports.get(row['id'], 'No saved report.')))

        def action_overview(self):
            self.request += 1
            self.mode = 'overview'
            self.screen.remove_class('reading')
            self.query_one(DataTable).focus()

        def action_logs(self):
            row = self.selected()
            if row and not self.busy:
                self.show_document('logs', row['label'] + ' / local journal', 'Reading selected local journal…')
                self.busy = True
                self.pending = (self.executor.submit(collector.logs, row), 'logs', self.request)

        def action_reread(self):
            if not self.busy:
                self.busy = True
                self.query_one('#notice', Static).update('Reading local evidence…')
                self.pending = (self.executor.submit(collector.snapshot), 'snapshot', self.request)

        def action_help(self):
            self.show_document('help', 'Keys and evidence', HELP)

        def action_move(self, change):
            if self.mode == 'overview':
                table = self.query_one(DataTable)
                if table.row_count:
                    table.move_cursor(row=(table.cursor_row + change) % table.row_count)
            else:
                reader = self.query_one('#reader', VerticalScroll)
                reader.scroll_relative(y=change, animate=False)

    return ConsoleApp()


HELP = '''Navigation
  Space or Enter: open the selected saved report.
  Up/Down or j/k: select a job; scroll in a report/journal.
  Mouse: select jobs, scroll, or click footer actions. Tab: change focus.
  PageUp/PageDown, Home/End: navigate long tables and documents.
  l: read the selected service's last 40 journal lines (may contain private data).
  r: reread files and systemd properties; never runs a check/upload/restore.
  Escape: return to overview. q: quit. ?: help.

Evidence
  HEALTHY: available local checks passed; read their scope/limitations.
  FAILED: a report, service outcome or desired/observed schedule disagrees.
  STALE: evidence is older than its configured freshness threshold.
  UNKNOWN: evidence, attribution, baseline/configuration or user bus is unavailable.
  DISABLED: not selected/scheduled and no conflicting schedule observed.

Reports and logs appear locally only on request; no uploads/exports.
Inactive oneshot services can be successful. A schedule alone is not execution.
Legacy restore metadata without host/dataset attribution stays UNKNOWN.
This interface cannot prove recoverability or notification delivery.
Configuration comes from the last console deployment, not live Git inventory.
'''


def tui(collector, interval):
    create_app(collector, interval).run()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, help='Deployed console JSON (default: ~/.config/workstation/console.json)')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--status', action='store_true', help='Print a local status snapshot')
    mode.add_argument('--json', action='store_true', help='Print schema-versioned status; excludes raw report bodies/logs')
    mode.add_argument('--detail', metavar='JOB', help='Print one job and its existing report; may show private paths')
    mode.add_argument('--logs', metavar='JOB', help='Print last 40 selected service journal lines; may show private data')
    parser.add_argument('--interval', type=int, default=30, help='TUI local observation interval in seconds (5–3600; default: 30)')
    args = parser.parse_args(argv)
    if not 5 <= args.interval <= 3600:
        parser.error('--interval must be between 5 and 3600')
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
    if not sys.stdin.isatty() or not sys.stdout.isatty() or os.environ.get('TERM', '') in ('', 'dumb'):
        parser.exit(2, 'An interactive terminal is required. Use --status or --json for noninteractive output.\n')
    try:
        tui(collector, args.interval)
    except ModuleNotFoundError as exc:
        if exc.name == 'textual':
            parser.exit(2, 'Textual is required for the TUI; install python3-textual through the console role. Use --status or --json meanwhile.\n')
        raise
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        parser.exit(2, f'Terminal interface unavailable ({type(exc).__name__}); use --status.\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
