"""Read-only console regression tests: synthetic reports/units, no cloud or live services."""
import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'ansible/roles/workstation_console/files/workstation.py'
spec = importlib.util.spec_from_file_location('workstation_console', SOURCE)
console = importlib.util.module_from_spec(spec)
spec.loader.exec_module(console)


def ago(hours=0):
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


class FakeSystemd:
    def __init__(self):
        self.overrides = {}
        self.calls = []
        self.unavailable = False
        self.backup_provider = 'proton/drive'

    def __call__(self, argv):
        self.calls.append(argv)
        if self.unavailable:
            return 1, '', 'Failed to connect to bus'
        if argv[0] == 'journalctl':
            return 0, 'Example log\x1b[31m with terminal controls\x1b[0m\n', ''
        assert argv[0] == 'systemctl' and 'show' in argv
        names = [arg for arg in argv if console.UNIT.fullmatch(arg)]
        blocks = []
        for name in names:
            props = dict(Id=name, LoadState='loaded', ActiveState='active' if name.endswith('.timer') or name == 'syncthing.service' else 'inactive',
                         UnitFileState='enabled' if name.endswith('.timer') or name == 'syncthing.service' else 'static',
                         Result='success', ExecMainStatus='0', ExecMainStartTimestamp='Wed 2026-11-04 08:00:00 UTC',
                         ExecMainExitTimestamp='Wed 2026-11-04 08:00:01 UTC',
                         LastTriggerUSec='Wed 2026-11-04 08:00:00 UTC', NextElapseUSecRealtime='Thu 2026-11-05 08:00:00 UTC')
            other = 'rclone' if self.backup_provider == 'proton/drive' else 'proton'
            if name.startswith('workstation-' + other + '-backup'):
                props.update(LoadState='not-found', ActiveState='inactive', UnitFileState='', ExecMainStartTimestamp='', ExecMainExitTimestamp='')
            props.update(self.overrides.get(name, {}))
            blocks.append('\n'.join(f'{key}={value}' for key, value in props.items()))
        return 0, '\n\n'.join(blocks), ''


class ConsoleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='workstation-console-test-')
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.config_path = self.home / '.config/workstation/console.json'
        self.config = dict(schema_version=1, hostname='test-host', inventory_host='desktop', profile='developer_gnome',
                           capabilities={key: {'enabled': True} for key in ('backup', 'sync', 'vpn', 'mail', 'passwords')},
                           providers=dict(backup='proton/drive', sync='syncthing', vpn='proton/vpn', mail='proton/mail', passwords='proton/pass'),
                           dataset_id='home-selected', backup_enabled=True, backup_timer_enabled=True,
                           syncthing_enabled=True, syncthing_service_enabled=True, tool_update_alerts_enabled=True,
                           security_updates_enabled=True, thresholds=dict(backup_hours=48, restore_hours=1080), reports=[])
        self.write_config()
        self.runner = FakeSystemd()
        self.collector = console.Collector(self.config_path, self.home, self.runner, host='test-host')
        for job in console.jobs_for(self.config):
            if job['report']:
                self.write(job['report'], 'Private report detail\nOVERALL: ' + job['expected'] + '\n')
        self.write('.local/state/workstation-post-update/versions.json', '{"docker": {"docker-ce": "approved"}}')
        self.record = dict(schema_version=1, capability='backup', provider='proton/drive', host='test-host',
                           dataset_id='home-selected', checked_at=ago(1), result='success', verified_restore_at=ago(2))
        self.write_record()
        self.restore_history()

    def write(self, relative, text):
        path = self.home / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def write_config(self):
        self.write('.config/workstation/console.json', json.dumps(self.config))

    def write_record(self):
        self.write('.local/state/workstation-backup/status.json', json.dumps(self.record))

    def restore_history(self, **updates):
        entry = dict(provider=self.record['provider'], host=self.record['host'], dataset_id=self.record['dataset_id'],
                     time=self.record['verified_restore_at'], result='success')
        entry.update(updates)
        self.write('.local/state/workstation-backup/restore-tests.jsonl', json.dumps(entry) + '\n')

    def rows(self):
        return {row['id']: row for row in self.collector.snapshot()['jobs']}

    def setup_manager(self):
        repo = self.home / 'repo'
        target = repo / 'ansible/inventory/host_vars/desktop.yml'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('# Keep unrelated settings\nworkstation_backup_timer_enabled: true\nworkstation_custom_value: preserved\n')
        play = repo / 'ansible/playbooks/workstation.yml'
        play.parent.mkdir()
        play.write_text('---\n[]\n')
        return console.SetupManager(self.collector, repo), target

    def test_setup_edit_review_save_and_stale_write_protection(self):
        import yaml
        manager, target = self.setup_manager()
        original = target.read_text()
        plan = manager.propose({'workstation_backup_timer_enabled': False})
        self.assertEqual(target.read_text(), original)
        self.assertIn('-workstation_backup_timer_enabled: true', plan['diff'])
        manager.save(plan)
        self.assertIn('# Keep unrelated settings', target.read_text())
        self.assertEqual(yaml.safe_load(target.read_text()),
                         dict(workstation_backup_timer_enabled=False, workstation_custom_value='preserved'))
        with self.assertRaisesRegex(ValueError, 'changed during review'):
            manager.save(plan)
        target.write_text('# coverage\nworkstation_backup_sources:\n  - /old\n  - /other\n'
                          '# unrelated comment\nworkstation_custom_value: preserved\n')
        manager.save(manager.propose({'workstation_backup_sources': ['/new']}))
        self.assertEqual(yaml.safe_load(target.read_text())['workstation_backup_sources'], ['/new'])
        self.assertIn('# unrelated comment', target.read_text())
        self.config['settings'] = {'workstation_python_versions': ['3.14.0']}
        self.write_config()
        plan = manager.propose({'workstation_python_versions': ['3.14.0']})
        self.assertEqual(plan['diff'], '')  # Do not pin unchanged deployed defaults.
        for edits in ({'ansible_connection': 'ssh'}, {'workstation_backup_timer_enabled': 'false'},
                      {'workstation_backup_sources': ['{{ lookup("pipe", "bad") }}']},
                      {'workstation_python_versions': [3.14]}):
            with self.assertRaises(ValueError):
                manager.propose(edits)
        target.write_text('workstation_backup_timer_enabled: true\nworkstation_backup_timer_enabled: false\n')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            manager.settings()
        target.write_text('invalid: [\n')
        with self.assertRaisesRegex(ValueError, 'invalid YAML'):
            manager.settings()
        target.unlink()
        target.symlink_to(self.config_path)
        with self.assertRaisesRegex(ValueError, 'regular file'):
            manager.settings()

    def test_setup_apply_requires_preview_and_local_identity(self):
        manager, target = self.setup_manager()
        intent = dict(ansible_connection='local', workstation_device_name='test-host')
        self.collector.runner = lambda argv: (0, json.dumps(intent), '')
        with self.assertRaisesRegex(ValueError, 'successful preview'):
            manager.command('apply')
        preview = manager.command('preview')
        self.assertIn('--check', preview)
        self.assertEqual(preview[preview.index('--limit') + 1], 'desktop')
        manager.preview_token = manager.fingerprint()
        self.assertNotIn('--check', manager.command('apply'))
        target.write_text(target.read_text() + '\n# concurrent edit\n')
        with self.assertRaisesRegex(ValueError, 'successful preview'):
            manager.command('apply')
        intent['ansible_connection'] = 'ssh'
        with self.assertRaisesRegex(ValueError, 'local inventory'):
            manager.command('preview')
        intent.update(ansible_connection='local', workstation_device_name='other-host')
        with self.assertRaisesRegex(ValueError, 'does not match'):
            manager.command('preview')


    def test_healthy_oneshot_and_no_mutations(self):
        before = {str(path): (path.read_bytes(), path.stat().st_mtime_ns) for path in self.home.rglob('*') if path.is_file()}
        snapshot = self.collector.snapshot()
        self.assertEqual(snapshot['overall'], 'HEALTHY', snapshot)
        self.assertEqual(self.rows()['backup']['activity'], 'inactive')
        after = {str(path): (path.read_bytes(), path.stat().st_mtime_ns) for path in self.home.rglob('*') if path.is_file()}
        self.assertEqual(before, after)
        self.assertTrue(all(call[0] == 'systemctl' and 'show' in call for call in self.runner.calls))
        self.assertEqual(len(self.runner.calls), 4)  # Two snapshots, two batched scope reads each.
        self.assertNotIn('Private report detail', json.dumps(snapshot))

    def test_missing_malformed_duplicate_future_and_stale_reports(self):
        report = self.home / '.local/state/workstation-health/latest.txt'
        cases = [('nothing', 'UNKNOWN'), ('OVERALL: HEALTHY\nOVERALL: HEALTHY\n', 'UNKNOWN'),
                 ('OVERALL: ATTENTION REQUIRED\n', 'FAILED')]
        for text, state in cases:
            report.write_text(text)
            self.assertEqual(self.rows()['health']['state'], state)
        report.write_text('OVERALL: HEALTHY\n')
        old = datetime.now().timestamp() - 49 * 3600
        os.utime(report, (old, old))
        self.assertEqual(self.rows()['health']['state'], 'STALE')
        future = datetime.now().timestamp() + 3600
        os.utime(report, (future, future))
        self.assertEqual(self.rows()['health']['state'], 'UNKNOWN')
        report.unlink()
        self.assertEqual(self.rows()['health']['state'], 'UNKNOWN')

    def test_failed_service_is_not_hidden_by_a_healthy_report(self):
        self.runner.overrides['workstation-health.service'] = dict(Result='exit-code', ExecMainStatus='1')
        self.assertEqual(self.rows()['health']['state'], 'FAILED')

    def test_missing_units_and_unavailable_bus_are_unknown(self):
        self.runner.overrides['workstation-health.timer'] = dict(LoadState='not-found')
        self.assertEqual(self.rows()['health']['state'], 'UNKNOWN')
        self.runner.unavailable = True
        self.assertEqual(self.rows()['backup']['state'], 'UNKNOWN')

    def test_disabled_intent_detects_leftover_running_schedule(self):
        self.config['backup_timer_enabled'] = False
        self.write_config()
        self.assertEqual(self.rows()['backup']['state'], 'FAILED')
        for stem in ('workstation-proton-backup', 'workstation-proton-backup-restore-test'):
            self.runner.overrides[stem + '.timer'] = dict(ActiveState='inactive', UnitFileState='disabled')
        self.assertEqual(self.rows()['backup']['state'], 'DISABLED')
        self.assertEqual(self.rows()['restore']['state'], 'DISABLED')
        self.runner.unavailable = True
        self.assertEqual(self.rows()['backup']['state'], 'UNKNOWN')

    def test_unselected_provider_is_disabled_not_missing(self):
        self.config['providers']['backup'] = 'none'
        self.write_config()
        self.assertEqual(self.rows()['backup']['state'], 'DISABLED')

    def test_skipped_provider_still_exposes_leftover_old_timers(self):
        self.config['providers']['backup'] = 'none'
        self.write_config()
        rows = self.rows()
        self.assertEqual(rows['backup']['state'], 'DISABLED')
        self.assertEqual(rows['other-backup-proton']['state'], 'FAILED')
        self.assertEqual(rows['other-restore-proton']['state'], 'FAILED')
        self.assertEqual(rows['other-backup-rclone']['state'], 'DISABLED')

    def test_unsupported_selected_provider_does_not_look_healthy(self):
        self.config['providers']['backup'] = 'custom'
        self.write_config()
        self.assertEqual(self.rows()['backup']['state'], 'UNKNOWN')

    def test_backup_attribution_and_malformed_json(self):
        for field, value in [('host', 'other-host'), ('dataset_id', 'other-data'), ('provider', 'google/drive')]:
            with self.subTest(field=field):
                original = self.record[field]
                self.record[field] = value
                self.write_record()
                self.assertEqual(self.rows()['backup']['state'], 'UNKNOWN')
                self.record[field] = original
        for data in ('[]', 'null', '{"schema_version":1,broken}', '{"verified_restore_at":2026-11-04T00:00:00Z}'):
            self.write('.local/state/workstation-backup/status.json', data)
            self.assertEqual(self.rows()['backup']['state'], 'UNKNOWN')

    def test_backup_age_and_future_or_timezone_less_timestamp(self):
        for value, expected in [(ago(49), 'STALE'), (ago(-3), 'UNKNOWN'), ('2026-01-01T00:00:00', 'UNKNOWN')]:
            self.record['checked_at'] = value
            self.write_record()
            self.assertEqual(self.rows()['backup']['state'], expected)

    def test_legacy_restore_timestamp_alone_cannot_turn_green(self):
        self.restore_history(host=None, dataset_id=None)
        self.assertEqual(self.rows()['restore']['state'], 'UNKNOWN')
        self.restore_history(result='mismatch')
        self.assertEqual(self.rows()['restore']['state'], 'FAILED')
        self.restore_history(time=ago(3))
        self.assertEqual(self.rows()['restore']['state'], 'UNKNOWN')

    def test_rclone_uses_its_own_units_and_evidence(self):
        self.config['providers']['backup'] = 'google/drive'
        self.runner.backup_provider = 'google/drive'
        self.write_config()
        self.assertEqual(self.rows()['backup']['state'], 'UNKNOWN')
        self.record['provider'] = 'google/drive'
        self.write_record()
        self.restore_history()
        rows = self.rows()
        self.assertEqual(rows['backup']['state'], 'HEALTHY')
        self.assertEqual(rows['backup']['service'], 'workstation-rclone-backup.service')
        self.assertEqual(rows['restore']['state'], 'HEALTHY')

    def test_event_success_may_be_old_but_baseline_must_exist(self):
        report = self.home / '.local/state/workstation-post-update/latest.txt'
        os.utime(report, (1, 1))
        self.assertEqual(self.rows()['post-update']['state'], 'HEALTHY')
        (self.home / '.local/state/workstation-post-update/versions.json').unlink()
        self.assertEqual(self.rows()['post-update']['state'], 'UNKNOWN')

    def test_never_run_service_is_not_healthy_just_because_timer_is_active(self):
        self.runner.overrides['apt-daily-upgrade.service'] = dict(ExecMainStartTimestamp='', ExecMainExitTimestamp='')
        self.assertEqual(self.rows()['apt-upgrades']['state'], 'UNKNOWN')

    def test_report_source_overrides_and_custom_reports(self):
        self.config['reports'] = [dict(name='Health', path='.local/state/workstation-health/latest.txt', expected='HEALTHY', max_age_hours=1),
                                  dict(name='Custom monitor', path='.local/state/custom/latest.txt', expected='OK')]
        self.write_config()
        path = self.home / '.local/state/workstation-health/latest.txt'
        old = datetime.now().timestamp() - 2 * 3600
        os.utime(path, (old, old))
        self.write('.local/state/custom/latest.txt', 'OVERALL: OK\n')
        rows = self.rows()
        self.assertEqual(rows['health']['state'], 'STALE')
        self.assertEqual(rows['report-1']['state'], 'HEALTHY')

    def test_missing_bad_foreign_config_never_assumes_default_host_intent(self):
        for data in ('{}', '[]', '{bad'):
            self.config_path.write_text(data)
            snap = self.collector.snapshot()
            self.assertTrue(snap['config_warning'])
            self.assertEqual(snap['profile'], 'unknown')
        self.config['hostname'] = 'other-host'
        self.write_config()
        self.assertIn('another host', self.collector.snapshot()['config_warning'])
        self.config_path.unlink()
        self.assertIn('missing', self.collector.snapshot()['config_warning'])

    def test_bounded_files_control_characters_and_path_escape(self):
        self.assertNotIn('\x1b', console.clean('\x1b[31mred\x1b[0m\x00'))
        with self.assertRaises(ValueError):
            self.collector.path('/etc/passwd')
        oversized = self.write('.local/state/oversized', 'x' * (console.LIMIT + 1))
        with self.assertRaises(ValueError):
            console.read_local(oversized)
        fifo = self.home / 'fifo'
        os.mkfifo(fifo)
        with self.assertRaises(ValueError):
            console.read_local(fifo)

    def test_logs_are_explicit_bounded_and_sanitized(self):
        rows = self.rows()
        self.assertFalse(any(call[0] == 'journalctl' for call in self.runner.calls))
        output = self.collector.logs(rows['backup'])
        self.assertNotIn('\x1b', output)
        self.assertIn('-n', self.runner.calls[-1])
        self.assertIn('40', self.runner.calls[-1])
        self.assertIn('workstation-proton-backup.service', self.runner.calls[-1])

    def test_command_timeout_is_handled(self):
        with patch.object(console.subprocess, 'run', side_effect=subprocess.TimeoutExpired('systemctl', 4)):
            rc, out, err = console.run_readonly(['systemctl', 'show'])
        self.assertNotEqual(rc, 0)
        self.assertIn('timed out', err)


    def test_action_allowlist_and_preflight_reject_unsafe_jobs(self):
        snapshot = self.collector.snapshot()
        for key in console.RUNNABLE:
            plan = console.action_plan(snapshot, key)
            self.assertEqual(plan['command'], ['systemctl', '--user', '--no-ask-password', 'start', console.RUNNABLE[key][0]])
        for key in ('backup', 'restore', 'apt-lists', 'apt-upgrades', 'sync', 'post-update', 'other-backup-rclone', 'report-0', 'health;reboot'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                console.action_plan(snapshot, key)
        for field, value in (('enabled', False), ('enabled', None), ('scope', 'system'), ('service', 'apt-daily.service')):
            bad = copy.deepcopy(snapshot)
            bad['jobs'][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                console.action_plan(bad, 'health')
        for prop, value in (('LoadState', 'not-found'), ('LoadState', 'masked'),
                            ('ActiveState', 'active'), ('ActiveState', 'activating'), ('ActiveState', 'deactivating'), ('ActiveState', '')):
            bad = copy.deepcopy(snapshot)
            bad['jobs'][0]['service_properties'][prop] = value
            with self.subTest(prop=prop, value=value), self.assertRaises(ValueError):
                console.action_plan(bad, 'health')
        snapshot['config_warning'] = 'Foreign host'
        with self.assertRaises(ValueError):
            console.action_plan(snapshot, 'health')

    def test_action_revalidates_intent_and_propagates_failure_or_timeout(self):
        plan = console.action_plan(self.collector.snapshot(), 'health')
        calls = []
        def runner(argv):
            calls.append(argv)
            return 0
        self.assertIn('COMPLETED:', console.run_job(self.collector, plan, runner))
        self.assertEqual(calls, [plan['command']])
        self.assertIn('FAILED:', console.run_job(self.collector, plan, lambda argv: 1))
        self.assertIn('OUTCOME UNKNOWN:', console.run_job(self.collector, plan, lambda argv: None))
        self.runner.overrides['workstation-health.service'] = {'ActiveState': 'activating'}
        self.assertIn('NOT STARTED:', console.run_job(self.collector, plan, runner))
        self.assertEqual(len(calls), 1)
        self.runner.overrides.clear()
        tampered = {**plan, 'command': ['reboot']}
        self.assertIn('NOT STARTED:', console.run_job(self.collector, tampered, runner))
        self.config['hostname'] = 'another-host'
        self.write_config()
        self.assertIn('NOT STARTED:', console.run_job(self.collector, plan, runner))
        self.assertEqual(len(calls), 1)

    def test_action_command_boundary_handles_timeouts_and_uses_no_shell(self):
        import subprocess
        command = ['systemctl', '--user', '--no-ask-password', 'start', 'workstation-health.service']
        with patch.object(console.subprocess, 'run', side_effect=subprocess.TimeoutExpired(command, 120)) as run:
            self.assertIsNone(console.run_service(command))
            self.assertEqual(run.call_args.kwargs['timeout'], 120)
            self.assertNotIn('shell', run.call_args.kwargs)
        with patch.object(console.subprocess, 'run', side_effect=FileNotFoundError):
            self.assertEqual(console.run_service(command), 2)


class ConsoleInstallationTests(unittest.TestCase):
    def test_isolated_role_install_is_idempotent_and_records_profile_intent(self):
        import yaml
        with tempfile.TemporaryDirectory(prefix='workstation-console-install-') as tmp:
            root = Path(tmp)
            home = root / 'home'
            home.mkdir()
            config = root / 'ansible.cfg'
            config.write_text('[defaults]\nroles_path = ' + str(ROOT / 'ansible/roles') + '\n[privilege_escalation]\nbecome_ask_pass = False\n')
            variables = dict(ansible_facts={'env': {'HOME': str(home)}, 'hostname': 'test-host'},
                             ansible_python_interpreter=sys.executable, ansible_remote_tmp=str(root / 'remote-tmp'),
                             workstation_console_install_dependencies=False,
                             workstation_profile='minimal', workstation_backup_dataset_id='home-selected',
                             workstation_capabilities={key: {'enabled': False} for key in ('backup', 'sync', 'vpn', 'mail', 'passwords')},
                             workstation_providers={key: 'none' for key in ('backup', 'sync', 'vpn', 'mail', 'passwords')},
                             workstation_backup_enabled=False, workstation_backup_timer_enabled=False,
                             workstation_syncthing_enabled=False, workstation_report_sources=[])
            variables.update(workstation_backup_on_calendar='daily',
                             workstation_backup_restore_test_calendar='monthly',
                             workstation_backup_sources=[], workstation_backup_excludes=[],
                             workstation_python_versions=[])
            playbook = root / 'install.yml'
            playbook.write_text(yaml.safe_dump([dict(hosts='localhost', gather_facts=False, become=False,
                                                     vars=variables, roles=['workstation_console'])]))
            env = dict(os.environ, ANSIBLE_CONFIG=str(config), ANSIBLE_LOCAL_TEMP=str(root / 'ansible-tmp'))
            command = ['ansible-playbook', '-i', 'localhost,', '-c', 'local', str(playbook)]
            for second in (False, True):
                result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, timeout=90)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                if second:
                    self.assertRegex(result.stdout, r'changed=0\s')
            deployed = home / '.local/bin/workstation'
            manifest = home / '.config/workstation/console.json'
            data, error = console.load_config(manifest)
            self.assertFalse(error)
            self.assertEqual(data['profile'], 'minimal')
            self.assertFalse(data['backup_enabled'])
            self.assertEqual(manifest.stat().st_mode & 0o777, 0o600)
            self.assertTrue(os.access(deployed, os.X_OK))
            assets = home / '.local/share/workstation/web'
            self.assertEqual({path.name for path in assets.iterdir()}, {'index.html', 'app.css', 'app.js', 'theme.js', 'server.py'})
            for name in ('index.html', 'app.css', 'app.js', 'theme.js', 'server.py'):
                self.assertTrue((assets / name).is_file(), name)
                self.assertEqual((assets / name).stat().st_mode & 0o777, 0o644)
            result = subprocess.run([sys.executable, str(deployed), '--help'], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0)
            self.assertIn('--json', result.stdout)
            self.assertIn('--dashboard', result.stdout)
            self.assertNotIn('textual', deployed.read_text().lower())


if __name__ == '__main__':
    unittest.main()
