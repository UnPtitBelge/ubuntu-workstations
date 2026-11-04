#!/usr/bin/env python3
"""Safely add missing disabled-state management to Phase 23 Proton backup role.

Run from the repository root. Does not run Ansible or modify user services.
"""
from pathlib import Path
import sys

path = Path('ansible/roles/providers/proton_drive/tasks/main.yml')
if not path.is_file():
    sys.exit(f'ERROR: {path} not found. Run from repository root.')
text = path.read_text(encoding='utf-8')
marker = '- name: Detect deployed Proton backup timer when backups disabled'
if marker in text:
    print('No change: backup disable fix is already present.')
    sys.exit(0)
anchor = '- name: Ensure Proton Drive backup is not configured for an invalid location\n'
if not text.startswith('---\n') and not text.startswith(anchor):
    sys.exit('ERROR: Unexpected YAML beginning; refusing to patch.')
if text.count(anchor) != 1:
    sys.exit('ERROR: Expected Phase 23 task not found exactly once; refusing to patch.')
if '- name: Manage Proton Drive backup timer (disabled until restore-tested)' not in text:
    sys.exit('ERROR: Expected Proton timer task not found; refusing to patch.')
addition = '''- name: Detect deployed Proton backup timer when backups disabled
  ansible.builtin.stat:
    path: "{{ ansible_facts['env']['HOME'] }}/.config/systemd/user/workstation-proton-backup.timer"
  register: disabled_proton_timer_file
  when: not workstation_backup_enabled | bool

- name: Disable and stop deployed Proton backup timer when backups disabled
  ansible.builtin.systemd_service:
    name: workstation-proton-backup.timer
    scope: user
    daemon_reload: true
    enabled: false
    state: stopped
  environment:
    XDG_RUNTIME_DIR: "/run/user/{{ ansible_facts['user_uid'] }}"
    DBUS_SESSION_BUS_ADDRESS: "unix:path=/run/user/{{ ansible_facts['user_uid'] }}/bus"
  when:
    - not workstation_backup_enabled | bool
    - disabled_proton_timer_file.stat.exists | default(false)
    - not ansible_check_mode

'''
updated = text.replace(anchor, addition + anchor, 1)
try:
    import yaml
    yaml.safe_load(updated)
except ImportError:
    print('Note: PyYAML unavailable; run ansible-playbook --syntax-check afterward.')
except Exception as exc:
    sys.exit(f'ERROR: Generated YAML rejected ({exc}); original left intact.')
path.write_text(updated, encoding='utf-8')
print(f'Patched {path}. Review git diff before deployment.')
