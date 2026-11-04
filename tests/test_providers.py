"""Run real Ansible file tasks in temp homes; simulate systemd, never provision."""
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROVIDERS = ROOT / 'ansible/roles/providers'


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='workstation-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        config = self.root / 'ansible.cfg'
        config.write_text('[defaults]\nretry_files_enabled = False\n')
        self.env = dict(os.environ, ANSIBLE_CONFIG=str(config), ANSIBLE_NOCOLOR='1',
                        ANSIBLE_LOCAL_TEMP=str(self.root / 'ansible-tmp'),
                        ANSIBLE_LIBRARY=str(ROOT / 'tests/fixtures/library'))

    def run_play(self, tasks, check=False):
        playbook = self.root / 'test.yml'
        playbook.write_text(yaml.safe_dump([{
            'name': 'Isolated provider regression', 'hosts': 'localhost',
            'gather_facts': False, 'become': False,
            'vars': {'ansible_python_interpreter': sys.executable,
                     'ansible_remote_tmp': str(self.root / 'remote-tmp')},
            'tasks': tasks,
        }], sort_keys=False))
        command = ['ansible-playbook', '-i', 'localhost,', '-c', 'local', str(playbook)]
        if check:
            command.append('--check')
        result = subprocess.run(command, cwd=self.root, env=self.env,
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        recap = re.search(r'changed=(\d+)', result.stdout)
        self.assertIsNotNone(recap, result.stdout)
        return int(recap.group(1))

    def test_contracts_converge_and_update_when_actions_change(self):
        blocks = []
        for path in sorted(PROVIDERS.rglob('tasks/main.yml')):
            tasks = yaml.safe_load(path.read_text())
            contract = [task for task in tasks if task.get('name') in (
                'Ensure provider contract state directory exists', 'Record provider adapter contract')]
            if not contract:
                continue  # Private installation helper, not a selectable provider.
            provider = path.parent.parent.relative_to(PROVIDERS).as_posix()
            defaults = yaml.safe_load((path.parent.parent / 'defaults/main.yml').read_text())
            blocks.append({'name': provider, 'block': contract, 'vars': {
                'ansible_facts': {'env': {'HOME': str(self.root)},
                                  'date_time': {'iso8601': '2026-01-01T00:00:00Z'}},
                'workstation_provider_path': provider, 'workstation_capability': 'test',
                'workstation_provider_supported_actions': defaults['workstation_provider_supported_actions'],
                'workstation_provider_manual_actions': defaults['workstation_provider_manual_actions'],
            }})
        self.assertEqual(len(blocks), 10)
        self.assertGreater(self.run_play(blocks), 0)
        records = self.root / '.local/state/workstation-provider'
        before = {p.name: p.read_bytes() for p in records.glob('*.json')}
        self.assertEqual(len(before), 10)
        for block in blocks:
            block['vars']['ansible_facts']['date_time']['iso8601'] = '2026-01-02T00:00:00Z'
        self.assertEqual(self.run_play(blocks), 0, 'Unchanged contracts must converge despite a new run date')
        self.assertEqual(before, {p.name: p.read_bytes() for p in records.glob('*.json')})
        blocks[0]['vars']['workstation_provider_supported_actions'] = ['test-new-action']
        self.assertEqual(self.run_play(blocks), 1, 'A contract change must still be written')
        record = records / (blocks[0]['name'].replace('/', '__') + '.json')
        self.assertEqual(json.loads(record.read_text())['supported_actions'], ['test-new-action'])

    def test_disable_guards_missing_units_check_mode_and_idempotency(self):
        blocks = []
        expectations = []
        for provider, prefix in (('proton/drive', 'proton'), ('google/drive', 'rclone'), ('syncthing', None)):
            role_tasks = PROVIDERS / provider / 'tasks'
            source = yaml.safe_load((role_tasks / 'main.yml').read_text())
            entry = next(task for task in source if task.get('ansible.builtin.import_tasks') == 'disable.yml')
            for scenario, enabled, scheduled, present in (
                ('enabled', True, True, True), ('disabled', False, True, True),
                ('scheduling-disabled', True, False, True), ('absent', False, False, False),
                ('partial', False, False, 'partial'),
            ):
                home = self.root / provider.replace('/', '-') / scenario
                unit_dir = home / '.config/systemd/user'
                unit_dir.mkdir(parents=True)
                names = ([f'workstation-{prefix}-backup.timer', f'workstation-{prefix}-backup-restore-test.timer']
                         if prefix else ['syncthing.service'])
                units = {'unrelated.timer': {'enabled': True, 'state': 'started'}}
                if prefix:
                    units[f'workstation-{prefix}-backup.service'] = {'enabled': False, 'state': 'started'}
                if present:
                    for name in names[:1] if present == 'partial' else names:
                        (unit_dir / name).touch()
                        units[name] = {'enabled': True, 'state': 'started'}
                state_file = home / 'units.json'
                state_file.write_text(json.dumps(units))
                initial = copy.deepcopy(units)
                if not (enabled and scheduled):
                    for name in names:
                        if name in units:
                            units[name] = {'enabled': False, 'state': 'stopped'}
                expectations.append((state_file, initial, units))
                disable = yaml.safe_load((role_tasks / 'disable.yml').read_text())
                for task in disable:
                    if 'ansible.builtin.systemd_service' in task:
                        params = task.pop('ansible.builtin.systemd_service')
                        params['state_file'] = str(state_file)
                        task['simulated_systemd_service'] = params
                    if provider == 'syncthing' and 'loop' in task:
                        task['loop'] = [str(home / 'packaged' / p.lstrip('/')) if p.startswith('/') else p
                                        for p in task['loop']]
                fixture = home / 'disable.yml'
                fixture.write_text(yaml.safe_dump(disable, sort_keys=False))
                dispatch = copy.deepcopy(entry)
                dispatch['ansible.builtin.import_tasks'] = str(fixture)
                blocks.append({'name': f'{provider}: {scenario}', 'block': [dispatch], 'vars': {
                    'ansible_facts': {'env': {'HOME': str(home)}, 'user_uid': os.getuid()},
                    'workstation_backup_enabled': enabled, 'workstation_backup_timer_enabled': scheduled,
                    'workstation_syncthing_enabled': enabled, 'workstation_syncthing_service_enabled': scheduled,
                }})
        self.assertGreater(self.run_play(blocks, check=True), 0)
        for path, initial, _ in expectations:
            self.assertEqual(json.loads(path.read_text()), initial, 'Check mode must not modify unit state')
        self.assertGreater(self.run_play(blocks), 0)
        for path, _, desired in expectations:
            self.assertEqual(json.loads(path.read_text()), desired)
        self.assertEqual(self.run_play(blocks), 0, 'A repeated disable must converge')


if __name__ == '__main__':
    unittest.main()
