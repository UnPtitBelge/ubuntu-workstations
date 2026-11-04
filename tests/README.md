# Repository regression tests

Run the same gate locally and in CI, from the repository root:

```fish
python3 scripts/maintenance-check.py
```

Requires Ansible and PyYAML (listed in `requirements.txt`). The gate compiles
Python, audits configuration, runs tests, syntax-checks every playbook and
parses inventory. It never runs the workstation provisioning playbook.

For tests alone:

```fish
python3 -m unittest discover -s tests -v
```

The provider tests execute Ansible against temporary homes on localhost.
Contract tests use the actual file/copy tasks from all selectable provider
roles, check convergence despite a changed run date, and verify that changing
an action list still updates the record.

Disable tests execute the actual import conditions and stat tasks from the
backup and Syncthing roles. Only the systemd module is replaced by a test
double that records unit state in temporary JSON files. Packaged Syncthing
unit paths are redirected into the fixture. Scenarios cover enabled, disabled,
scheduling disabled, missing and partially installed units, check mode and a
second pass. Unrelated units and running backup services must stay unchanged.

These are isolated task integration tests, not full provisioning tests. They
do not install packages, contact providers, access credentials, upload data,
or manage real services. A disposable Ubuntu VM rehearsal, target-host strict
audit, live service checks and full-playbook idempotency remain separate.
