# Roadmap

This file lists open work and acceptance criteria. Current operations live in
[Operations](OPERATIONS.md); previous implementation history lives in
[the archive](archive/ROADMAP-v1.3.0.md). A feature in source is not evidence that
it is deployed or has passed a real cloud/restore test.

## Local web dashboard and future CLI

`workstation` starts an on-demand loopback web dashboard;
`--status`, `--json`, `--detail` and `--logs` retain read-only CLI
inspection. Remote workstation management is deferred.

- [x] Designed browser interface with Overview, Machines, Setup, Operations,
  Changes, Activity, Lifecycle and orientation views; responsive layouts.
- [x] Higher-contrast light/dark themes with persistent preference, clear action
  buttons and direct monitoring-job review from Operations.
- [x] Dedicated forms for supported backup, development, desktop and notification
  settings; reviewed host-file diffs and stale-write protection.
- [x] Confirmed Ansible preview/apply/audit with local identity checks, preview
  invalidation and terminal-only password handling.
- [x] Search jobs and filter categories/attention states; inspect reports/journals
  as literal text without exporting raw bodies in ordinary snapshots.
- [x] Confirm selected monitoring jobs with fresh intent/unit checks, single-use
  reviews, single-operation execution and explicit failure/unknown results.
- [x] Show evidence freshness, next/last schedules and last service results;
  distinguish desired intent, observation, missing data and disabled features.
- [x] Per-process local session, loopback/Host/origin restrictions, bounded API
  requests, fixed static assets and no arbitrary browser-supplied commands.
- [x] Read-only synthetic demo; isolated API, collector and Ansible role tests.
- [ ] Fully resolved inventory/provenance and richer version policy editors.
- [ ] Backup action correctness prerequisites below, then confirmed backup
  preview/upload/restore and reviewed update installation workflows.
- [ ] Profile/provider transition planning and explicit component disable/remove
  workflows with separate cutover/decommission approval.
- [ ] Expand the easy-to-use CLI after the browser workflows settle; keep
  existing status/JSON semantics stable.

The [operations guide](OPERATIONS.md#web-dashboard) documents implemented
behavior and evidence limits. Browser verification uses synthetic data and
fake executors; it does not prove real provisioning, cloud backup or recovery.

## Correctness before more automation

These are code-review findings or missing verification, not live-host diagnoses:

- [ ] **Harden backup/restore metadata.** Test both adapters after a successful restore timestamp exists; scripts currently interpolate an unquoted timestamp into JSON. Restore-history generation uses jq without an explicit null input. Cover noninteractive runs, early failures and valid dated records before relying on them for CLI status.
- [ ] **Isolate provider evidence.** `status.json`, manifest and restore timestamps are shared latest state. Prevent one provider's run from satisfying another provider/dataset's health check; validate host/provider/dataset identity and concurrent writes.
- [ ] **Rehearse migration cutover/rollback.** The helper provisions a role, can enable its timers and does not reconcile every restore timer or monitor. Freeze the original provider identity and prove rollback independently of a later inventory selection change.
- [ ] **Make audits and monitoring profile-aware.** Strict validation still requires full desktop tools. Reduced profiles can retain alert jobs, stale report expectations and some desktop packages. Prove disabled features are represented correctly, including existing-host transitions.
- [ ] **Verify recovery in service context.** Prove chosen-file recovery and a scheduled restore drill for each intended host/provider. A manifest, timer, declaration or past release pass is insufficient.

## Further work

- [ ] Full provisioning/idempotency CI in disposable Ubuntu VMs for supported profiles, plus an interactive GNOME rehearsal. Isolated contract/disable tests already exist; they are not whole-machine proof.
- [ ] Provider-specific export/import/verify tests and a real small-dataset provider swap with a proven rollback window.
- [ ] Report retention and missed-run detection across sleep/offline intervals, without removing backup data or clearing failures.
- [ ] Provider-neutral update review; explicit version policies beyond the current Node proposal and Docker/Proton VPN groups.
- [ ] Configuration rollback guidance that accounts for package versions and data compatibility; tested backup selection/exclusions.
- [ ] Ansible lint alongside the existing shared gate and separate CI secret scan.

## Completion evidence

For an implemented change, record the revision, actual checks run, target hosts,
real deployment/audit results where applicable, second-pass changes, skipped
checks and rollback plan. Keep credentials and private diagnostic details out of
Git. Release readiness uses the [routine checklist](OPERATIONS.md#before-a-release).

Automatic repair, Docker pruning, broad package cleanup, cloud deletion,
credential copying and unattended provider cutovers remain outside the intended
monitoring/CLI scope.
