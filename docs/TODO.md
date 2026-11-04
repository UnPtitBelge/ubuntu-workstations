# TODO — Ubuntu Workstations

**Baseline:** `v1.3.0` (public repository) · **Hosts:** `Omnissiah-desktop` (`desktop`) and `Omnissiah-pocket` (`laptop`)
**Purpose:** A prioritized, honest roadmap. Checked items are shipped capabilities; unchecked items are proposed work, **not** implemented features.

> **Operating principle:** Keep both workstations reproducible, observable, recoverable, and provider-independent. Prefer small reviewed Ansible changes over autonomous changes that could destroy data or break access.

## Current baseline (shipped in v1.3.0)

- [x] Provision both Ubuntu 26.04 workstations from one Ansible/Git repository.
- [x] Manage Fish, Ghostty, GNOME, development toolchains, Docker, virtualization, and Syncthing.
- [x] Configure cloud backups (Proton Drive by default) and scheduled backup monitoring on both machines.
- [x] Enable Ubuntu security updates without automatic reboots.
- [x] Run health, selected-file drift, backup, update-discovery, and post-update monitors.
- [x] Deliver GNOME alerts, weekly reports, controlled update proposals, and a release audit.
- [x] Publish a command cheatsheet and a routine maintenance checklist.
- [x] **Multi-setup profiles:** `profiles/{developer_gnome,minimal,headless}.yml`, selected per host via `workstation_profile` (see [DEPLOY.md](DEPLOY.md) §8).
- [x] **Vendor-namespaced providers:** `workstation_providers` values are `vendor/name` paths dispatched to `ansible/roles/providers/<vendor>/<name>/` — built-ins `proton/drive`, `proton/vpn`, `proton/pass`, `proton/mail`, `google/drive`, `google/mail`, `syncthing`, `wireguard`, `keepassxc`, `custom` (see [PROVIDERS.md](PROVIDERS.md)).
- [x] **Third-party onboarding:** `setup.yml.example` → gitignored `setup.local.yml` → `scripts/setup-workstation.py` generates the inventory entry and `host_vars/<host>.yml`.
- [x] **Normalized backup status:** providers write `~/.local/state/workstation-backup/status.json`; the backup monitor follows the selected provider's units (`workstation_backup_monitor_service/_timer`) instead of hardcoding Proton.
- [x] **Public-release hardening:** MIT `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`, gitleaks CI + Dependabot, `.gitattributes`, example inventories; published on GitHub with annotated tag `v1.3.0` (see [PUBLIC-RELEASE-AUDIT.md](PUBLIC-RELEASE-AUDIT.md)).

A new host is now a **configuration-only** change plus documented manual enrollment (provider sign-in, Syncthing pairing, backup destination). A fully unattended installer and automated cross-provider data migration remain out of scope.

## P0 — Correctness and recoverability (next maintenance release)

- [ ] **Verify backup recovery, not just upload success.** Document and periodically test an actual restore from each host's remote backup path to a separate location; compare hashes/content. _Done when:_ a dated recovery result exists for both hosts and does not require overwriting source files.
- [x] **Make backup monitoring independent of one provider.** _Done in v1.3.0:_ providers write a normalized record (`~/.local/state/workstation-backup/status.json`: provider, dataset, host, timestamp, result, `verified_restore_at`) consumed by `workstation-backup-health-check`, and the monitor follows the selected provider's units via `workstation_backup_monitor_service/_timer` facts — no Proton-specific commands or unit names in the monitor logic.
- [x] **Audit sensitive data exposure.** _Done in v1.3.0:_ full-history gitleaks scan (no leaks) plus manual blob scan, recorded in [PUBLIC-RELEASE-AUDIT.md](PUBLIC-RELEASE-AUDIT.md); gitleaks now runs in CI on every push/PR and GitHub secret scanning + push protection are enabled.
- [ ] **Harden drift semantics.** Prevent routine provisioning from silently redefining a previously mismatched baseline without visibility; distinguish `expected from Git` versus `accepted after deployment`. _Done when:_ an out-of-band edit stays visible until explicitly resolved.
- [ ] **Surface post-update validation failures reliably.** Verify the alert integration in both a logged-in GNOME session and after logout/login. _Done when:_ failure, duplicate-suppression and recovery tests pass on both hosts.
- [ ] **Document release-to-release compatibility.** Pin minimum Ansible/core, Python and Ubuntu versions; exercise a fresh provisioning rehearsal. _Done when:_ a clean target passes validation without undocumented manual patches.

## P1 — Generic deployment (see [DEPLOY.md](DEPLOY.md))

- [x] **Create a generic host profile.** _Done in v1.3.0:_ reusable profiles in `profiles/<name>.yml` selected by `workstation_profile`, plus `setup.yml.example` + `scripts/setup-workstation.py` to generate a new host's inventory entry and `host_vars` from one fill-in file. Adding a host = inventory/profile data + documented manual enrollment only.
- [x] **Introduce capability flags and a provider selection schema.** Implemented as `workstation_capabilities` / `workstation_providers` (defaults in `group_vars/all.yml`, bundled per profile), dispatched by `playbooks/workstation.yml` to vendor-namespaced `roles/providers/<vendor>/<name>/`. Provider values are paths: built-ins `proton/drive`, `google/drive`, `syncthing`, `proton/vpn`, `wireguard`, `proton/mail`, `google/mail`, `proton/pass`, `keepassxc`, `custom`; `none` skips a capability. Swapping a provider is an inventory-variable change only; unknown providers fail with a list of available roles. Remaining: more built-in adapters (see P1 provider-migration items).
- [x] **Split common capability contracts from provider implementations.** _Done in v1.3.0:_ the monolithic `proton` role is split into `proton/{drive,vpn,pass,mail}` (+ shared `_deb`), and every capability has at least two selectable implementations (backup: `proton/drive`/`google/drive`; vpn: `proton/vpn`/`wireguard`; mail: `proton/mail`/`google/mail`; passwords: `proton/pass`/`keepassxc`).
- [x] **Standardize paths, service names and health output.** _Done in v1.3.0:_ backup providers emit the normalized `status.json` record and set `workstation_backup_monitor_service/_timer`, so the monitor, weekly report and alerts are provider-agnostic; other capabilities emit `latest.txt` with an `OVERALL` line. Systemd unit names stay provider-specific by design (side-by-side migration).
- [ ] **Make machine identity explicit.** Generate and retain unique hostname, Syncthing/device IDs, VPN identity, backup destination, and local secrets per host. _Done when:_ provisioning cannot accidentally clone identities.
- [x] **Build a genuinely clean-install test.** _Done in v1.3.0:_ `playbooks/rehearsal-headless.yml` executed on a clean Ubuntu 26.04 Multipass VM (2026-11-04): idempotent (`changed=0`), toolchains verified — see [PUBLIC-RELEASE-AUDIT.md](PUBLIC-RELEASE-AUDIT.md). Run with `--limit <host> -f 1`. Remaining: an interactive GNOME/user-session rehearsal.
- [ ] **Handle differences gracefully.** GNOME availability, GPU/display, KVM, laptop battery, architecture, and optional programs should be capability-detected or opt-in. _Done when:_ an unsupported optional capability skips clearly instead of failing unrelated provisioning.

## P1 — Provider migration framework (see [MIGRATE.md](MIGRATE.md))

- [ ] **Inventory data and authentication per capability.** Identify export formats, volume, metadata, API limits, retention and recovery dependencies. _Done when:_ a preflight inventory can be produced without copying secrets into Git.
- [~] **Define provider adapters:** `install`, `configure`, `health`, `export`, `import`, `verify`, `disable` where technically supported; document manual-only steps. _Partial in v1.3.0:_ each built-in adapter documents its accounts, secrets and manual enrollment steps in [PROVIDERS.md](PROVIDERS.md); the full machine-readable contract is still proposed in [MIGRATE.md](MIGRATE.md) §5. _Done when:_ each adapter states its supported actions and failure semantics.
- [ ] **Support side-by-side migration.** Configure old and new providers concurrently while keeping one declared source of truth. _Done when:_ a test migration can verify data before cutover without clobbering old state.
- [ ] **Provide dataset-level checksums and manifest reports.** Compare file count, sizes, checksums and meaningful metadata (where supported); avoid relying on remote UI totals alone. _Done when:_ discrepancies are visible and attributable.
- [ ] **Implement safe cutover / rollback runbooks.** Include write-freeze, delta sync, dependency switch, monitoring transfer and rollback window. _Done when:_ a simulated migration can revert without losing writes.
- [x] **Build at least one non-Proton backup adapter.** _Done in v1.3.0:_ `google/drive` (rclone) works with any rclone remote — Google Drive or SFTP/S3 to a self-hosted VPS — through the same `workstation_backup_*` capability variables and the normalized status record; side-by-side with `proton/drive` during a migration.
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

1. ~~v1.2.x hardening + generic deployment (profiles, provider selection, normalized backup status, secret scanning) — done in v1.3.0.~~
2. **Remaining hardening:** restore drills with dated evidence, drift semantics, post-update alert verification, release compatibility pins.
3. **First real provider swap:** move one low-risk dataset to the `google/drive` (rclone) backend per [MIGRATE.md](MIGRATE.md) §3 and prove rollback.
4. **Migrations by capability:** sync, VPN, password manager and mail, with their own explicit runbooks.
5. **CI and integration tests:** idempotency in CI and per-provider adapter tests, so new providers never regress the two working hosts.

## Definition of done for any new role or migration

- [ ] Relevant host/profile variables and defaults are documented.
- [ ] `--syntax-check`, a real limited deployment, and strict validation pass.
- [ ] Second Ansible run is idempotent or a documented exception is justified.
- [ ] Health/backup status is reported and failures are visible in journals and notifications.
- [ ] Secrets remain outside the repository and per-machine identities stay distinct.
- [ ] A disable/uninstall plan and a rollback path are documented.
- [ ] At least one test demonstrates the data or service **actually works**, not merely that a timer exists.
