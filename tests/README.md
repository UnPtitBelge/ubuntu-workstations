# Repository regression tests

Run the same gate locally and in CI, from the repository root:

```fish
python3 scripts/maintenance-check.py
```

Requires Ansible and PyYAML (listed in `requirements.txt`). The gate compiles
Python, audits configuration, runs tests, syntax-checks every playbook and
parses inventory. It never runs the workstation provisioning playbook.

Console coverage includes reviewed setup-file saves, stale-write protection,
invalid/duplicate YAML rejection, local-target checks and preview-before-apply
gating. Dashboard Ansible execution is mocked; the console role installation is
tested in an isolated temporary home. These do not certify live provisioning,
strict host audit, cloud backup or recovery.

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

The console tests use synthetic local reports and an injected read-only systemd
runner. They cover freshness, malformed/missing data, provider/host/dataset
attribution, disabled intent versus observed schedules, legacy restore evidence,
missing baselines/bus access, terminal-control sanitization, file limits and
CLI errors. Web tests cover session/Host/origin protection, static allowlists,
literal evidence transport, action allowlisting, cancellation, single-use and
expired confirmations, stale edits, preview-before-apply and concurrent operation
rejection. HTTP tests bind ephemeral loopback ports; executors are fake. The
console role is installed twice into a temporary home to check assets,
configuration privacy and idempotency, with package installation skipped.
No regression test starts real workstation services, reads live journals or
contacts a provider. Browser checks use synthetic data and fake executors;
screenshots are not host health or deployment evidence.

For browser-source edits, also check JavaScript syntax with Node (development
validation only; the installed dashboard does not require Node):

```fish
node --check ansible/roles/workstation_console/files/web/app.js
node --check ansible/roles/workstation_console/files/web/theme.js
```

Verify light/dark themes, persistence, narrow layouts and review/cancellation
flows in the browser using demo data or isolated fake executors. Never use live
provisioning or cloud actions as UI smoke tests.
