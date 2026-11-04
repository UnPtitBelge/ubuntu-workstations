# Roadmap

This file lists open work and acceptance criteria. Current operations live in
[Operations](OPERATIONS.md); previous implementation history lives in
[the archive](archive/ROADMAP-v1.3.0.md). A feature in source is not evidence that
it is deployed or has passed a real cloud/restore test.

## Next: management CLI

**Planned; no unified CLI exists yet.** Make the setup understandable from one
entry point, reusing existing reports, systemd units and provider helpers. Start
with inspection before adding actions. Do not introduce another scheduler.

- [ ] Show local host, selected profile/provider intent and installed jobs together, with an explicit distinction between desired and observed state.
- [ ] Summarize health, drift, backup, restore evidence, update discovery and post-update validation with their timestamps and evidence paths.
- [ ] Distinguish healthy, failed, stale, unknown/missing and intentionally disabled/not applicable. Never treat a missing result as success.
- [ ] Show next/last timer execution and the last service outcome; inactive successful oneshot services must not look broken.
- [ ] Tie backup/restore evidence to host, provider and dataset; handle malformed/shared/stale records without false green status.
- [ ] Offer focused detail/log views and explain the next useful action without dumping private data by default.
- [ ] Keep ordinary status inspection read-only and bounded in time. It must not query cloud accounts, refresh baselines, upload, download or repair anything implicitly.
- [ ] Add explicit report refresh, backup preview/run and restore-test actions only with clear effects and failure propagation; persist configuration changes through Ansible.
- [ ] Provide useful help, stable JSON output/exit semantics and Fish completion; test missing helpers, unavailable user buses, stale reports and both backup providers without live accounts.

Command naming and the final interaction design remain to be implemented. The
[operations guide](OPERATIONS.md) is the current behavior/evidence inventory for
that work, not a promise that every monitor already exposes a reliable API.

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
