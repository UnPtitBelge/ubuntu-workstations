"""Loopback-only dashboard. No cloud calls, shell dispatch or persistent daemon."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
from pathlib import Path
import secrets
import shlex
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
from urllib.parse import urlsplit

FIELDS = [
    ('workstation_backup_timer_enabled', 'Scheduled backups', 'Run the selected backup on its managed schedule. Enable only after authentication and a tested restore.', 'backup', 'boolean'),
    ('workstation_backup_on_calendar', 'Backup schedule', 'A systemd calendar expression, such as daily or *-*-* 20:00:00.', 'backup', 'string'),
    ('workstation_backup_restore_test_calendar', 'Restore check schedule', 'Schedule a single-file restore drill. An upload alone does not prove recovery.', 'backup', 'string'),
    ('workstation_backup_sources', 'Included folders', 'One absolute folder path per line. Review coverage before applying.', 'backup', 'list'),
    ('workstation_backup_excludes', 'Excluded patterns', 'One rsync/rclone filter pattern per line.', 'backup', 'list'),
    ('workstation_role_languages', 'Language toolchains', 'Manage the language toolchains selected in inventory.', 'development', 'boolean'),
    ('workstation_python_versions', 'Python versions', 'One approved version per line. Existing projects may depend on installed versions.', 'development', 'list'),
    ('workstation_role_containers', 'Containers', 'Manage Docker and the container tools declared in inventory.', 'development', 'boolean'),
    ('workstation_role_virtualization', 'Virtualization', 'Manage the declared virtualization tools.', 'development', 'boolean'),
    ('workstation_role_gnome', 'GNOME desktop', 'Manage the desktop configuration. Turning this off skips its role; it does not uninstall it.', 'desktop', 'boolean'),
    ('workstation_tool_update_alerts_enabled', 'Update notifications', 'Show notifications from update discovery. Does not authorize installation.', 'desktop', 'boolean'),
]


def terminal_ansible(args, cwd):
    if not sys.stdin.isatty():
        raise ValueError('Start workstation in an interactive terminal to use Ansible actions. Passwords are never accepted in the browser.')
    print('\nDashboard action: ' + shlex.join(args), flush=True)
    # Inherit the terminal for getpass/sudo; never capture or relay credentials.
    return subprocess.run(args, cwd=cwd, check=False).returncode


class DashboardState:
    def __init__(self, backend, collector, manager, demo=False, action_runner=None, ansible_runner=None):
        self.backend, self.collector, self.manager = backend, collector, manager
        self.demo = demo
        self.action_runner = action_runner or backend.run_service
        self.ansible_runner = ansible_runner or terminal_ansible
        self.terminal = ansible_runner is not None or sys.stdin.isatty()
        self.lock = threading.RLock()
        self.collect_lock = threading.Lock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='workstation-action')
        self.plans, self.activities = {}, []
        self.busy = False

    def close(self):
        self.executor.shutdown(wait=True)

    def snapshot(self):
        with self.collect_lock:
            snapshot = demo_snapshot() if self.demo else self.collector.snapshot()
            for row in snapshot['jobs']:
                row['category'] = self.backend.category_for(row)
                row['runnable'] = row['id'] in self.backend.RUNNABLE and not self.demo
            return snapshot

    def settings(self):
        if self.demo:
            return dict(available=False, demo=True, error='Sample data. Changes are disabled in demo mode.',
                        values=demo_settings(), fields=FIELDS, providers=demo_snapshot()['providers'],
                        profile='developer_gnome', terminal=False)
        try:
            config, target = self.manager.context()
            return dict(available=True, values=self.manager.settings(), fields=FIELDS,
                        providers=config['providers'], profile=config['profile'],
                        path=str(target), repo=str(self.manager.repo), terminal=self.terminal,
                        preview_ready=self.manager.preview_token is not None and
                        self.manager.preview_token == self.manager.fingerprint())
        except (ValueError, OSError, ImportError) as exc:
            return dict(available=False, error=str(exc), values={}, fields=FIELDS, terminal=self.terminal)

    def machines(self):
        snapshot = self.snapshot()
        names = {snapshot['inventory_host']}
        if self.demo:
            names.update(('desktop', 'laptop'))
        else:
            try:
                import yaml
                try:
                    data = yaml.safe_load((self.manager.repo / 'ansible/inventory/hosts.yml').read_text())
                except yaml.YAMLError:
                    data = {}
                names.update(data['all']['children']['workstations']['hosts'])
            except (OSError, ValueError, KeyError, TypeError, ImportError):
                pass
        return [dict(id=name, local=name == snapshot['inventory_host'],
                     host=snapshot['host'] if name == snapshot['inventory_host'] else None)
                for name in sorted(names) if isinstance(name, str)]

    def evidence(self, job_id, logs=False):
        if self.demo:
            row = next((row for row in self.snapshot()['jobs'] if row['id'] == job_id), None)
            if row is None:
                raise ValueError('Unknown job.')
            return 'SAMPLE EVIDENCE\n\n' + row['label'] + '\n' + '\n'.join(row['reasons'])
        with self.collect_lock:
            snapshot = self.collector.snapshot()
            row = next((row for row in snapshot['jobs'] if row['id'] == job_id), None)
            if row is None:
                raise ValueError('Unknown job.')
            return (self.collector.logs(row) if logs else self.backend.details(
                row, self.collector.reports.get(job_id, 'No saved report available.')))

    def plan(self, data):
        with self.lock:
            if self.demo:
                raise ValueError('Demo mode is read-only. Launch without --demo to manage this workstation.')
            if self.busy:
                raise ValueError('Another operation is running. Wait for its result before creating a plan.')
            kind = data.get('kind')
            if kind == 'settings':
                payload = self.manager.propose(data.get('values'))
                if not payload['diff']:
                    raise ValueError('No configuration changes to save.')
                title, effect = 'Save configuration', 'Save the reviewed host-file changes to Git working state. This does not provision the machine or commit anything.'
                public = dict(diff=payload['diff'], host=payload['host'], command=None)
            elif kind == 'job':
                payload = self.backend.action_plan(self.snapshot(), data.get('job'))
                title, effect = payload['label'], payload['effect']
                public = dict(host=payload['host'], command=shlex.join(payload['command']))
            elif kind in ('preview', 'apply', 'audit'):
                if not self.terminal:
                    raise ValueError('Ansible actions require the interactive terminal where workstation was launched.')
                args = self.manager.command(kind)
                payload = dict(args=args, fingerprint=self.manager.fingerprint())
                title = {'preview': 'Preview configuration', 'apply': 'Apply configuration', 'audit': 'Run strict audit'}[kind]
                effect = ('Continue in the terminal where workstation is running for sudo and full Ansible output. '
                          'Apply may install packages and start/restart services. Preview is check mode, not an integration test. '
                          'Stop at the first failed task; no retry or rollback is automatic.')
                public = dict(host=self.manager.context()[0]['inventory_host'], command=shlex.join(args))
            else:
                raise ValueError('Unsupported action. Commands cannot be supplied by the browser.')
            now = time.monotonic()
            self.plans = {key: plan for key, plan in self.plans.items() if now - plan['created'] < 600}
            if len(self.plans) >= 32:
                raise ValueError('Too many pending reviews. Cancel old reviews or wait for them to expire.')
            plan_id = secrets.token_urlsafe(24)
            self.plans[plan_id] = dict(kind=kind, payload=payload, created=now, title=title)
            return dict(id=plan_id, kind=kind, title=title, effect=effect, **public)

    def confirm(self, plan_id):
        with self.lock:
            if self.busy:
                raise ValueError('An operation is already running.')
            plan = self.plans.pop(plan_id, None)
            if not plan or time.monotonic() - plan['created'] >= 600:
                raise ValueError('This review expired or was already used. Review the action again.')
            self.busy = True
            activity = dict(id=secrets.token_hex(8), title=plan['title'], kind=plan['kind'],
                            state='RUNNING', started_at=datetime.now(timezone.utc).isoformat(),
                            message='Continue in the launching terminal for sudo and Ansible output.'
                            if plan['kind'] in ('preview', 'apply', 'audit') else 'Operation started.')
            self.activities.insert(0, activity)
            self.activities = self.activities[:50]
            self.executor.submit(self.execute, plan, activity)
            return dict(activity)

    def execute(self, plan, activity):
        status, message = 'FAILED', 'Operation did not complete.'
        try:
            kind, payload = plan['kind'], plan['payload']
            if kind == 'settings':
                self.manager.save(payload)
                status, message = 'COMPLETED', 'Host configuration saved. Preview before applying. No commit or provisioning occurred.'
            elif kind == 'job':
                message = self.backend.run_job(SimpleNamespace(snapshot=self.snapshot), payload, self.action_runner)
                status = ('COMPLETED' if message.startswith('COMPLETED:') else
                          'UNKNOWN' if message.startswith('OUTCOME UNKNOWN:') else 'FAILED')
            else:
                if self.manager.fingerprint() != payload['fingerprint'] or self.manager.command(kind) != payload['args']:
                    raise ValueError('Repository or inventory changed since review. Create a new plan.')
                self.manager.preview_token = None
                code = self.ansible_runner(payload['args'], self.manager.repo / 'ansible')
                if kind == 'preview' and code == 0 and self.manager.fingerprint() == payload['fingerprint']:
                    self.manager.preview_token = payload['fingerprint']
                status = 'COMPLETED' if code == 0 else 'FAILED'
                message = f'Ansible exited {code}. ' + ('Review terminal output. After apply, audit and verify idempotency.'
                           if code == 0 else 'Inspect the first failed task before trying again. A fresh preview is required.')
        except (ValueError, OSError, ImportError) as exc:
            message = str(exc)
        except Exception:
            status, message = 'UNKNOWN', 'Unexpected worker failure. Inspect the service or terminal before retrying.'
            self.manager.preview_token = None
        finally:
            with self.lock:
                activity.update(state=status, message=self.backend.clean(message),
                                finished_at=datetime.now(timezone.utc).isoformat())
                self.busy = False


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, state, assets, port=8765):
        self.state, self.assets = state, Path(assets)
        self.token = secrets.token_urlsafe(32)
        super().__init__(('127.0.0.1', port), DashboardHandler)
        self.origin = 'http://127.0.0.1:' + str(self.server_port)


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # No access log of private paths or session credentials.

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def respond(self, status, body, mime='application/json; charset=utf-8'):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=True).encode()
        self.send_response(status)
        for key, value in {
            'Content-Type': mime, 'Content-Length': str(len(body)), 'Cache-Control': 'no-store',
            'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
            'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
            'Cross-Origin-Resource-Policy': 'same-origin',
        }.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def allowed(self, api):
        if self.headers.get('Host') != urlsplit(self.server.origin).netloc:
            self.respond(403, dict(error='Untrusted dashboard host. Use the printed loopback URL.'))
            return False
        origin = self.headers.get('Origin')
        if (origin and origin != self.server.origin) or self.headers.get('Sec-Fetch-Site') == 'cross-site':
            self.respond(403, dict(error='Cross-origin requests are not allowed.'))
            return False
        if api and not hmac.compare_digest(self.headers.get('Authorization', '').encode('utf-8'), ('Bearer ' + self.server.token).encode('utf-8')):
            self.respond(401, dict(error='Open the session link printed by workstation to connect.'))
            return False
        return True

    def do_GET(self):
        path = urlsplit(self.path).path
        if not self.allowed(path.startswith('/api/')):
            return
        state = self.server.state
        try:
            if path == '/api/status':
                self.respond(200, dict(snapshot=state.snapshot(), demo=state.demo))
            elif path == '/api/settings':
                self.respond(200, state.settings())
            elif path == '/api/machines':
                self.respond(200, dict(machines=state.machines()))
            elif path == '/api/activity':
                with state.lock:
                    self.respond(200, dict(busy=state.busy, activities=state.activities))
            elif path.startswith('/api/evidence/'):
                parts = path.split('/')
                if len(parts) != 5 or parts[4] not in ('report', 'logs'):
                    raise ValueError('Unknown evidence path.')
                self.respond(200, dict(text=state.evidence(parts[3], parts[4] == 'logs')))
            elif path in ('/', '/index.html', '/app.css', '/app.js', '/theme.js'):
                name = 'index.html' if path == '/' else path[1:]
                mime = {'html': 'text/html', 'css': 'text/css', 'js': 'text/javascript'}[name.rsplit('.', 1)[1]]
                self.respond(200, (self.server.assets / name).read_bytes(), mime + '; charset=utf-8')
            else:
                self.respond(404, dict(error='Not found.'))
        except (ValueError, OSError, ImportError) as exc:
            self.respond(400, dict(error=str(exc)))
        except Exception:
            self.respond(500, dict(error='Cannot read local evidence. Inspect the launching terminal/configuration.'))

    def do_POST(self):
        if not self.allowed(True):
            return
        try:
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError('JSON is required.')
            length = int(self.headers.get('Content-Length', '0'))
            if length <= 0 or length > 262144 or self.headers.get('Transfer-Encoding'):
                raise ValueError('Invalid request size.')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('Expected a JSON object.')
            path = urlsplit(self.path).path
            if path == '/api/plan':
                self.respond(200, self.server.state.plan(data))
            elif path == '/api/confirm' and isinstance(data.get('id'), str):
                self.respond(202, self.server.state.confirm(data['id']))
            elif path == '/api/cancel' and isinstance(data.get('id'), str):
                with self.server.state.lock:
                    self.server.state.plans.pop(data['id'], None)
                self.respond(200, dict(cancelled=True))
            else:
                self.respond(404, dict(error='Unknown action.'))
        except (ValueError, OSError, ImportError) as exc:
            self.respond(400, dict(error=str(exc)))
        except Exception:
            self.respond(500, dict(error='Action could not be accepted. Inspect activity before retrying.'))


def demo_settings():
    return dict(workstation_backup_timer_enabled=True, workstation_backup_on_calendar='*-*-* 20:00:00',
                workstation_backup_restore_test_calendar='monthly', workstation_backup_sources=['/home/demo/Documents', '/home/demo/Sync'],
                workstation_backup_excludes=['node_modules/', '.cache/', '.venv/'], workstation_python_versions=['3.12.13', '3.13.14'],
                workstation_role_languages=True, workstation_role_containers=True, workstation_role_virtualization=True,
                workstation_role_gnome=True, workstation_tool_update_alerts_enabled=True)


def demo_snapshot():
    rows = []
    for key, label, state, age, reason in (
        ('health', 'System health', 'HEALTHY', .3, 'Saved disk and service checks passed.'),
        ('drift', 'Configuration drift', 'HEALTHY', .3, 'No changes in the selected managed files.'),
        ('backup', 'Backup upload', 'HEALTHY', 14, 'Matching upload record. Recovery is verified separately.'),
        ('restore', 'Restore verification', 'STALE', 1152, 'The last single-file restore is older than the 45-day threshold.'),
        ('updates', 'Update discovery', 'HEALTHY', 2, 'Discovery completed. Open the report to review available versions.'),
        ('summary', 'Weekly report', 'HEALTHY', 24, 'Summary generated from saved source reports.'),
        ('sync', 'File synchronization', 'HEALTHY', None, 'Syncthing is active. Peer synchronization is not verified.'),
        ('alerts', 'Desktop notifications', 'HEALTHY', None, 'Last local invocation passed. Delivery is not verified.'),
    ):
        rows.append(dict(id=key, label=label, state=state, age_hours=age, reasons=[reason],
                         activity='active' if key == 'sync' else 'inactive', enabled=True,
                         scope='user', service='sample.service', timer='sample.timer',
                         kind='report', report=None, next_run='Tomorrow, 20:00', last_trigger='Today',
                         service_properties={}, timer_properties={}))
    return dict(schema_version=1, host='ubuntu-desktop', inventory_host='desktop', profile='developer_gnome',
                overall='STALE', observed_at=datetime.now(timezone.utc).isoformat(), config_warning='',
                providers=dict(backup='proton/drive', sync='syncthing', vpn='proton/vpn', mail='proton/mail', passwords='proton/pass'),
                jobs=rows)


def serve(backend, collector, manager, assets, port, demo=False):
    state = DashboardState(backend, collector, manager, demo)
    server = DashboardServer(state, assets, port)
    print('Workstation dashboard' + (' · DEMO (sample data, read-only)' if demo else ''), flush=True)
    print('Open this private session link in your browser:\n' + server.origin + '/#token=' + server.token, flush=True)
    print('Loopback only. Ctrl+C stops the server. Ansible prompts stay in this terminal.', flush=True)
    try:
        server.serve_forever(poll_interval=.25)
    finally:
        server.server_close()
        state.close()
