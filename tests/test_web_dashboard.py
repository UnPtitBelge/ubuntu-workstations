"""Dashboard API tests: temporary inventory, synthetic evidence, fake executors."""
import http.client
import importlib.util
import json
from pathlib import Path
import threading
import time
import unittest

import test_console as fixtures

console, ROOT = fixtures.console, fixtures.ROOT

ASSETS = ROOT / 'ansible/roles/workstation_console/files/web'
spec = importlib.util.spec_from_file_location('dashboard_server', ASSETS / 'server.py')
web = importlib.util.module_from_spec(spec)
spec.loader.exec_module(web)


class DashboardFixture(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ConsoleTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.manager, self.target = self.fixture.setup_manager()
        observer = self.fixture.collector.runner
        self.fixture.collector.runner = lambda argv: ((0, json.dumps(dict(ansible_connection='local',
            workstation_device_name='test-host')), '') if argv[0] == 'ansible-inventory' else observer(argv))
        self.commands = []
        self.ansible_code = 0
        self.state = web.DashboardState(console, self.fixture.collector, self.manager,
            action_runner=lambda args: self.commands.append(args) or 0,
            ansible_runner=lambda args, cwd: self.commands.append(args) or self.ansible_code)
        self.addCleanup(self.state.close)

    def finish(self):
        deadline = time.monotonic() + 5
        while self.state.busy and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertFalse(self.state.busy)
        return self.state.activities[0]


class DashboardTests(DashboardFixture):
    def test_review_does_not_save_until_confirmed_and_cannot_replay(self):
        before = self.target.read_bytes()
        plan = self.state.plan(dict(kind='settings', values=dict(workstation_backup_timer_enabled=False)))
        self.assertEqual(self.target.read_bytes(), before)
        self.assertIn('workstation_backup_timer_enabled: false', plan['diff'])
        self.state.confirm(plan['id'])
        self.assertEqual(self.finish()['state'], 'COMPLETED')
        self.assertIn('workstation_backup_timer_enabled: false', self.target.read_text())
        self.assertEqual(self.commands, [])
        with self.assertRaises(ValueError):
            self.state.confirm(plan['id'])

    def test_stale_save_and_expired_plan_fail_closed(self):
        plan = self.state.plan(dict(kind='settings', values=dict(workstation_backup_timer_enabled=False)))
        self.target.write_text('# changed during review\n' + self.target.read_text())
        before = self.target.read_bytes()
        self.state.confirm(plan['id'])
        self.assertEqual(self.finish()['state'], 'FAILED')
        self.assertEqual(self.target.read_bytes(), before)
        plan = self.state.plan(dict(kind='job', job='health'))
        self.state.plans[plan['id']]['created'] -= 601
        with self.assertRaisesRegex(ValueError, 'expired'):
            self.state.confirm(plan['id'])
        self.assertEqual(self.commands, [])

    def test_apply_needs_preview_and_approval_is_consumed(self):
        with self.assertRaisesRegex(ValueError, 'successful preview'):
            self.state.plan(dict(kind='apply'))
        plan = self.state.plan(dict(kind='preview'))
        self.assertEqual(self.commands, [])
        self.state.confirm(plan['id'])
        self.assertEqual(self.finish()['state'], 'COMPLETED')
        self.assertIn('--check', self.commands[-1])
        plan = self.state.plan(dict(kind='apply'))
        self.state.confirm(plan['id'])
        self.assertEqual(self.finish()['state'], 'COMPLETED')
        self.assertNotIn('--check', self.commands[-1])
        with self.assertRaisesRegex(ValueError, 'successful preview'):
            self.state.plan(dict(kind='apply'))

    def test_changed_inputs_and_failed_previews_block_apply(self):
        plan = self.state.plan(dict(kind='preview'))
        self.state.confirm(plan['id'])
        self.finish()
        plan = self.state.plan(dict(kind='apply'))
        self.target.write_text(self.target.read_text() + '\n# new change\n')
        self.state.confirm(plan['id'])
        self.assertEqual(self.finish()['state'], 'FAILED')
        self.assertEqual(len(self.commands), 1)
        self.ansible_code = 2
        plan = self.state.plan(dict(kind='preview'))
        self.state.confirm(plan['id'])
        self.assertEqual(self.finish()['state'], 'FAILED')
        with self.assertRaisesRegex(ValueError, 'successful preview'):
            self.state.plan(dict(kind='apply'))

    def test_job_allowlist_fresh_intent_and_concurrent_actions(self):
        for data in (dict(kind='shell', command='reboot'), dict(kind='job', job='health;reboot'),
                     dict(kind='job', job='backup'), dict(kind='settings', values=dict(ansible_connection='ssh'))):
            with self.assertRaises(ValueError):
                self.state.plan(data)
        plan = self.state.plan(dict(kind='job', job='health'))
        self.fixture.config['hostname'] = 'another-machine'
        self.fixture.write_config()
        self.state.confirm(plan['id'])
        self.assertEqual(self.finish()['state'], 'FAILED')
        self.assertEqual(self.commands, [])
        self.fixture.config['hostname'] = 'test-host'
        self.fixture.write_config()
        started, release = threading.Event(), threading.Event()
        def runner(args):
            started.set()
            release.wait(3)
            return 0
        self.state.action_runner = runner
        plan = self.state.plan(dict(kind='job', job='health'))
        self.state.confirm(plan['id'])
        try:
            self.assertTrue(started.wait(1))
            with self.assertRaisesRegex(ValueError, 'running'):
                self.state.plan(dict(kind='job', job='updates'))
            # Status inspection stays available while the executor is occupied.
            self.assertEqual(self.state.snapshot()['host'], 'test-host')
        finally:
            release.set()
        self.assertEqual(self.finish()['state'], 'COMPLETED')

    def test_demo_never_reads_host_and_cannot_mutate(self):
        self.state.demo = True
        self.fixture.collector.snapshot = lambda: self.fail('Demo read the host')
        self.assertEqual(self.state.snapshot()['host'], 'ubuntu-desktop')
        self.assertFalse(self.state.settings()['available'])
        self.assertFalse(any(row['runnable'] for row in self.state.snapshot()['jobs']))
        for kind in ('settings', 'job', 'preview', 'apply'):
            with self.assertRaisesRegex(ValueError, 'read-only'):
                self.state.plan(dict(kind=kind))


class DashboardHTTPTests(DashboardFixture):
    def setUp(self):
        super().setUp()
        self.server = web.DashboardServer(self.state, ASSETS, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def request(self, path, body=None, auth=True, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        request_headers = {'Authorization':'Bearer ' + self.server.token} if auth else {}
        if body is not None:
            request_headers.update({'Content-Type':'application/json', 'Origin':self.server.origin})
        request_headers.update(headers or {})
        connection.request('POST' if body is not None else 'GET', path,
                           body=json.dumps(body) if body is not None else None, headers=request_headers)
        response = connection.getresponse()
        data = response.read()
        code, response_headers = response.status, dict(response.getheaders())
        connection.close()
        return code, data, response_headers

    def test_session_origin_and_host_boundaries(self):
        self.assertEqual(self.request('/api/status', auth=False)[0], 401)
        self.assertEqual(self.request('/api/status?token='+self.server.token, auth=False)[0], 401)
        self.assertEqual(self.request('/api/status', headers={'Origin':'https://attacker.example'})[0], 403)
        self.assertEqual(self.request('/api/status', headers={'Host':'attacker.example'})[0], 403)
        self.assertEqual(self.request('/api/status', headers={'Sec-Fetch-Site':'cross-site'})[0], 403)
        self.assertEqual(self.request('/api/status', headers={'Authorization':'Bearer é'})[0], 401)
        self.assertEqual(self.request('/api/plan', dict(kind='job',job='health'), auth=False)[0], 401)
        code, data, headers = self.request('/api/status')
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(data)['snapshot']['host'], 'test-host')
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertNotIn('Access-Control-Allow-Origin', headers)
        self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy'])
        self.assertEqual(self.commands, [])

    def test_static_allowlist_and_literal_evidence(self):
        for path in ('/server.py','/../workstation.py','/%2e%2e/workstation.py','/api/command'):
            self.assertEqual(self.request(path)[0],404)
        for path in ('/','/app.css','/app.js','/theme.js'):
            code, _, _ = self.request(path,auth=False)
            self.assertEqual(code,200)
        self.fixture.write('.local/state/workstation-health/latest.txt', '<script>bad()</script>\nOVERALL: HEALTHY\n')
        code, data, _ = self.request('/api/evidence/health/report')
        self.assertEqual(code,200)
        self.assertIn('<script>bad()</script>',json.loads(data)['text'])
        self.assertEqual(self.request('/api/evidence/nonexistent/report')[0],400)

    def test_api_confirmation_and_validation(self):
        before = self.target.read_bytes()
        code, body, _ = self.request('/api/plan',dict(kind='settings',values=dict(workstation_backup_timer_enabled=False)))
        self.assertEqual(code,200)
        plan = json.loads(body)
        self.assertEqual(self.target.read_bytes(),before)
        self.assertEqual(self.request('/api/cancel',dict(id=plan['id']))[0],200)
        self.assertEqual(self.request('/api/confirm',dict(id=plan['id']))[0],400)
        self.assertEqual(self.target.read_bytes(),before)
        _, body, _ = self.request('/api/plan',dict(kind='settings',values=dict(workstation_backup_timer_enabled=False)))
        plan = json.loads(body)
        self.assertEqual(self.request('/api/confirm',dict(id=plan['id']))[0],202)
        self.assertEqual(self.finish()['state'],'COMPLETED')
        self.assertEqual(self.request('/api/confirm',dict(id=plan['id']))[0],400)
        self.assertEqual(self.request('/api/plan',[])[0],400)
        self.assertEqual(self.request('/api/plan',dict(kind='job',job='health'),headers={'Content-Type':'text/plain'})[0],400)
        self.assertEqual(self.request('/api/plan',dict(kind='job',job='health'),headers={'Content-Length':'999999'})[0],400)


if __name__ == '__main__':
    unittest.main()
