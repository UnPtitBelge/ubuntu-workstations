#!/usr/bin/python3
"""Test double: store unit state in a temporary JSON file; never call systemd."""
import json
from pathlib import Path

from ansible.module_utils.basic import AnsibleModule


def main():
    module = AnsibleModule(
        argument_spec={
            'name': {'type': 'str', 'required': True},
            'scope': {'type': 'str', 'required': True},
            'daemon_reload': {'type': 'bool'},
            'enabled': {'type': 'bool', 'required': True},
            'state': {'type': 'str', 'required': True},
            'state_file': {'type': 'path', 'required': True},
        },
        supports_check_mode=True,
    )
    params = module.params
    path = Path(params['state_file'])
    units = json.loads(path.read_text())
    if params['name'] not in units:
        module.fail_json(msg='Attempt to manage an absent unit')
    if params['scope'] != 'user':
        module.fail_json(msg='Only user units are expected')
    desired = {'enabled': params['enabled'], 'state': params['state']}
    changed = units[params['name']] != desired
    if changed and not module.check_mode:
        units[params['name']] = desired
        path.write_text(json.dumps(units))
    module.exit_json(changed=changed)


if __name__ == '__main__':
    main()
