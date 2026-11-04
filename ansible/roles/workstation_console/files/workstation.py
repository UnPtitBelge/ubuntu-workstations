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


def draw_dashboard(screen, snapshot, selected, mode, content, scroll, busy):
    """Render only; safe for small/resized terminals and independently testable."""
    import curses
    height, width = screen.getmaxyx()
    screen.erase()
    def color(number):
        try:
            return curses.color_pair(number)
        except curses.error:
            return 0
    def put(y, x, value, attr=0):
        if 0 <= y < height and 0 <= x < width - 1:
            try:
                screen.addnstr(y, x, clean(value).replace('\t', '    '), max(0, width - x - 1), attr)
            except curses.error:
                pass
    if height < 18 or width < 72:
        put(0, 0, 'Workstation — resize to at least 72 columns x 18 rows. q quits.')
        screen.refresh()
        return
    put(0, 2, 'WORKSTATION  /  local operations', curses.A_BOLD | color(1))
    put(1, 2, f'{snapshot["host"]}  •  {snapshot["profile"]}  •  {snapshot["overall"]}' if snapshot else 'Reading local evidence…')
    put(2, 2, 'READ ONLY  |  Deployed intent + observed jobs  |  No cloud requests or repairs', curses.A_DIM)
    if snapshot and snapshot['config_warning']:
        put(3, 2, snapshot['config_warning'], color(3))
    elif snapshot:
        put(3, 2, 'Selected: ' + '  '.join(f'{key}={value}' for key, value in snapshot['providers'].items()), curses.A_DIM)
    if not snapshot:
        put(5, 2, 'Loading… q remains available.')
    elif mode == 'overview':
        rows = snapshot['jobs']
        visible = max(1, min(len(rows), (height - 9) // 2))
        start = max(0, min(selected - visible + 1, len(rows) - visible))
        put(4, 2, '  JOB                                 EVIDENCE   STATE      SERVICE', curses.A_BOLD)
        for offset, row in enumerate(rows[start:start + visible]):
            index = start + offset
            state_color = {'HEALTHY': 2, 'FAILED': 4, 'STALE': 3, 'UNKNOWN': 3, 'DISABLED': 5}[row['state']]
            attr = curses.A_REVERSE if index == selected else color(state_color)
            put(5 + offset, 2, f'{">" if index == selected else " "} {row["label"]:34.34} {age_label(row["age_hours"]):>7}   {row["state"]:9}  {row["activity"]}', attr)
        row = rows[selected]
        y = 6 + visible
        put(y, 2, row['label'], curses.A_BOLD)
        summary = [*row['reasons'][:2], 'Last trigger: ' + row['last_trigger'],
                   'Next run: ' + row['next_run'], 'Activity: ' + row['activity'],
                   'Enter for saved report; l for the local service journal.']
        for index, line in enumerate(summary):
            if y + index + 1 >= height - 3:
                break
            put(y + index + 1, 2, line)
    else:
        put(4, 2, mode.upper() + '  /  ' + (snapshot['jobs'][selected]['label'] if mode != 'help' else 'keys and effects'), curses.A_BOLD)
        lines = content.splitlines()
        for index, line in enumerate(lines[scroll:scroll + height - 8]):
            put(6 + index, 2, line)
    put(height - 2, 2, '↑↓/jk select  Enter report  l logs  r reread  ? help  Esc overview  q quit', curses.A_BOLD)
    put(height - 1, 2, 'Reading local evidence…' if busy else 'r only rereads evidence; it does not run monitoring jobs.', curses.A_DIM)
    screen.refresh()


HELP = '''Navigation
  Up/Down or j/k: select a job; in report/log views, scroll.
  Enter: open existing report and status evidence.
  l: read the selected service's last 40 journal lines (may contain private data).
  r: reread files and systemd properties; never runs a check/upload/restore.
  Escape: return to overview. q: quit. Terminal resize is supported.

Evidence
  HEALTHY: the available local checks passed; read the scope/limitations.
  FAILED: a report, service outcome or desired/observed schedule disagrees.
  STALE: available evidence is older than its configured freshness threshold.
  UNKNOWN: evidence, attribution, baseline/configuration or user bus is unavailable.
  DISABLED: not selected/scheduled in deployed intent and no conflicting schedule observed.

Reports and logs are displayed locally only when requested; no uploads/exports.
Inactive oneshot services can be successful. A schedule alone is not execution.
Legacy restore metadata without host/dataset attribution stays UNKNOWN.
This interface cannot prove all cloud files are recoverable or that a notification arrived.
Configuration comes from the last console deployment, not live Git inventory.
'''


def tui(collector, interval):
    import curses
    def app(screen):
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        if curses.has_colors():
            curses.start_color()
            try:
                curses.use_default_colors()
                background = -1
            except curses.error:
                background = curses.COLOR_BLACK
            for index, color in enumerate((curses.COLOR_CYAN, curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_RED, curses.COLOR_WHITE), 1):
                curses.init_pair(index, color, background)
        screen.keypad(True)
        screen.timeout(100)
        snapshot, selected, mode, content, scroll = None, 0, 'overview', '', 0
        with ThreadPoolExecutor(max_workers=1) as worker:
            future = worker.submit(collector.snapshot)
            log_future = None
            last_read = time.monotonic()
            while True:
                if future is not None and future.done():
                    snapshot = future.result()
                    selected = min(selected, len(snapshot['jobs']) - 1)
                    future = None
                    last_read = time.monotonic()
                    if mode == 'report':
                        row = snapshot['jobs'][selected]
                        content = details(row, collector.reports.get(row['id'], 'No report available for this item.'))
                if log_future is not None and log_future.done():
                    content = log_future.result()
                    log_future = None
                if future is None and log_future is None and time.monotonic() - last_read >= interval:
                    future = worker.submit(collector.snapshot)
                draw_dashboard(screen, snapshot, selected, mode, content, scroll, future is not None or log_future is not None)
                key = screen.getch()
                if key in (ord('q'), ord('Q')):
                    break
                if key == ord('?'):
                    mode, content, scroll = 'help', HELP, 0
                elif key == 27:
                    mode, scroll = 'overview', 0
                elif key in (ord('r'), ord('R')) and future is None and log_future is None:
                    future = worker.submit(collector.snapshot)
                elif snapshot:
                    if key in (curses.KEY_UP, ord('k'), curses.KEY_DOWN, ord('j')):
                        change = -1 if key in (curses.KEY_UP, ord('k')) else 1
                        if mode == 'overview':
                            selected = (selected + change) % len(snapshot['jobs'])
                        else:
                            scroll = max(0, min(scroll + change, max(0, len(content.splitlines()) - 1)))
                    elif key in (10, 13, curses.KEY_ENTER):
                        row = snapshot['jobs'][selected]
                        mode, content, scroll = 'report', details(row, collector.reports.get(row['id'], 'No report available for this item.')), 0
                    elif key in (ord('l'), ord('L')) and log_future is None and future is None:
                        mode, content, scroll = 'logs', 'Reading selected local journal…', 0
                        log_future = worker.submit(collector.logs, snapshot['jobs'][selected])
    curses.wrapper(app)


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
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        parser.exit(2, f'Terminal interface unavailable ({type(exc).__name__}); use --status.\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
