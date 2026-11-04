# TODO — Ubuntu Workstations

**Baseline:** `v1.2.0` · **Hosts:** `Omnissiah-desktop` (`desktop`) and `Omnissiah-pocket` (`laptop`)  
**Purpose:** A prioritized, honest roadmap. Checked items are shipped capabilities; unchecked items are proposed work, **not** implemented features.

> **Operating principle:** Keep both workstations reproducible, observable, recoverable, and provider-independent. Prefer small reviewed Ansible changes over autonomous changes that could destroy data or break access.

## Current baseline (shipped in v1.2.0)

- [x] Provision both Ubuntu 26.04 workstations from one Ansible/Git repository.
- [x] Manage Fish, Ghostty, GNOME, development toolchains, Docker, virtualization, and Syncthing.
- [x] Configure Proton Drive backups and scheduled backup monitoring on both machines.
- [x] Enable Ubuntu security updates without automatic reboots.
- [x] Run health, selected-file drift, backup, update-discovery, and post-update monitors.
- [x] Deliver GNOME alerts, weekly reports, controlled update proposals, and a release audit.
- [x] Publish a command cheatsheet and a routine maintenance checklist.

These features **do not** yet make the system a generic workstation installer or provider-agnostic migration framework.

## P0 — Correctness and recoverability (next maintenance release)

- [ ] **Verify backup recovery, not just upload success.** Document and periodically test an actual restore from each host's remote backup path to a separate location; compare hashes/content. _Done when:_ a dated recovery result exists for both hosts and does not require overwriting source files.
- [ ] **Make backup monitoring independent of one provider.** Define a normalized success record (provider, dataset, host, timestamp, result, optional remote confirmation) consumed by the backup monitor. _Done when:_ monitor logic does not invoke or name Proton-specific commands.
- [ ] **Audit sensitive data exposure.** Search tracked/config-generated content for tokens, local auth files, secrets and accidental report data; add explicit `.gitignore` coverage. _Done when:_ scans and human review show no sensitive material staged.
- [ ] **Harden drift semantics.** Prevent routine provisioning from silently redefining a previously mismatched baseline without visibility; distinguish `expected from Git` versus `accepted after deployment`. _Done when:_ an out-of-band edit stays visible until explicitly resolved.
- [ ] **Surface post-update validation failures reliably.** Verify the alert integration in both a logged-in GNOME session and after logout/login. _Done when:_ failure, duplicate-suppression and recovery tests pass on both hosts.
- [ ] **Document release-to-release compatibility.** Pin minimum Ansible/core, Python and Ubuntu versions; exercise a fresh provisioning rehearsal. _Done when:_ a clean target passes validation without undocumented manual patches.

## P1 — Generic deployment (see [DEPLOY.md](DEPLOY.md))

- [ ] **Create a generic host profile.** Separate reusable defaults from `desktop`/`laptop` names and per-host secrets. _Done when:_ adding `workstation3` requires an inventory entry, profile selection and documented manual enrollment only.
- [x] **Introduce capability flags and a provider selection schema.** Implemented as `workstation_capabilities` / `workstation_providers` in `group_vars/all.yml`, dispatched by `playbooks/workstation.yml` to `roles/providers/<provider>/` (built-ins: proton_drive, syncthing, proton_vpn, proton_mail, proton_pass, custom). _Done:_ enabling/disabling or swapping a provider is an inventory-variable change only; unknown providers fail with a list of available roles. Remaining: more built-in adapters (see P1 provider-migration items).
- [ ] **Split common capability contracts from provider implementations.** Avoid a monolithic `proton` role that owns VPN, mail, passwords, Drive, and backup together. _Done when:_ providers are independently selectable and at least two implementations satisfy a capability contract.
- [ ] **Standardize paths, service names and health output.** Define consistent install, timer, logs, dataset manifests and success metadata. _Done when:_ the weekly report consumes normalized records regardless of provider.
- [ ] **Make machine identity explicit.** Generate and retain unique hostname, Syncthing/device IDs, VPN identity, backup destination, and local secrets per host. _Done when:_ provisioning cannot accidentally clone identities.
- [ ] **Build a genuinely clean-install test.** Exercise a disposable VM/container for non-GNOME portions and an interactive test for GNOME/user services. _Done when:_ the documented bootstrap reaches a clean Ansible recap on a fresh supported host.
- [ ] **Handle differences gracefully.** GNOME availability, GPU/display, KVM, laptop battery, architecture, and optional programs should be capability-detected or opt-in. _Done when:_ an unsupported optional capability skips clearly instead of failing unrelated provisioning.

## P1 — Provider migration framework (see [MIGRATE.md](MIGRATE.md))

- [ ] **Inventory data and authentication per capability.** Identify export formats, volume, metadata, API limits, retention and recovery dependencies. _Done when:_ a preflight inventory can be produced without copying secrets into Git.
- [ ] **Define provider adapters:** `install`, `configure`, `health`, `export`, `import`, `verify`, `disable` where technically supported; document manual-only steps. _Done when:_ each adapter states its supported actions and failure semantics.
- [ ] **Support side-by-side migration.** Configure old and new providers concurrently while keeping one declared source of truth. _Done when:_ a test migration can verify data before cutover without clobbering old state.
- [ ] **Provide dataset-level checksums and manifest reports.** Compare file count, sizes, checksums and meaningful metadata (where supported); avoid relying on remote UI totals alone. _Done when:_ discrepancies are visible and attributable.
- [ ] **Implement safe cutover / rollback runbooks.** Include write-freeze, delta sync, dependency switch, monitoring transfer and rollback window. _Done when:_ a simulated migration can revert without losing writes.
- [ ] **Build at least one non-Proton backup adapter.** Choose an interoperable target/backend after assessing encryption and restore. _Done when:_ backups and restores work with two different destinations using the same capability interface.
- [ ] **Add migration-specific checks for password manager, mail, VPN and sync.** These have different data semantics and may need guided/manual migration. _Done when:_ each has a validated capability-specific acceptance test.

## P2 — Operations improvements

- [ ] **Provider-neutral update review** and validation where third-party APT clients change.
- [ ] **Audit log and report retention**; rotate old reports without deleting backup data.
- [ ] **Alert on missing scheduled executions**, not only failed last runs; verify stale-data thresholds against timer schedules.
- [ ] **Make monitoring robust across sleep/offline intervals** and report missed executions with actionable context.
- [ ] **Test idempotency automatically in CI**, with Ansible lint, YAML syntax, Python compilation and secret scanning.
- [ ] **Document approved upgrade policy** for pinned Node, Java, Rust and npm CLIs; keep update approval separate from installation.
- [ ] **Improve rollback between repository revisions**; distinguish config rollback from data restoration.
- [ ] **Version and test backup selection/exclusions** so changing tools cannot silently alter protected datasets.
- [ ] **Document environmental caveats:** GNOME notifications need a graphical session; lingering alone is insufficient for notification delivery or unlocked secrets.

## Deferred / explicitly out of scope for now

- [ ] Automatic Docker volume pruning or broad `apt autoremove` without a reviewed cleanup policy.
- [ ] Fully unattended major-version upgrades of language runtimes or distro releases.
- [ ] Automatically copying credential vaults, SSH keys, Syncthing identity, Proton sessions or recovery codes between hosts.
- [ ] Claiming that Syncthing mirroring is a backup or that a green backup timer proves restorable data.

## Suggested implementation sequence

1. **v1.2.x hardening:** restore drills, normalized backup-health record, secrets/drift reliability.
2. **Generic deployment:** host profiles and independent provider selection; establish the capability contract.
3. **First provider swap:** move one low-risk dataset to a second backup backend and prove rollback.
4. **Migrations by capability:** sync, VPN, password manager and mail, with their own explicit runbooks.
5. **CI and integration tests:** ensure new providers never regress the two working hosts.

## Definition of done for any new role or migration

- [ ] Relevant host/profile variables and defaults are documented.
- [ ] `--syntax-check`, a real limited deployment, and strict validation pass.
- [ ] Second Ansible run is idempotent or a documented exception is justified.
- [ ] Health/backup status is reported and failures are visible in journals and notifications.
- [ ] Secrets remain outside the repository and per-machine identities stay distinct.
- [ ] A disable/uninstall plan and a rollback path are documented.
- [ ] At least one test demonstrates the data or service **actually works**, not merely that a timer exists.
