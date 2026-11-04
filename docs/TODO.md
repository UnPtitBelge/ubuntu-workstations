# TODO — Ubuntu Workstations

**Baseline:** `v1.3.0` (public repository) · **Hosts:** `my-desktop` (`desktop`) and `my-laptop` (`laptop`)
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

## P0 — Correctness and recoverability (shipped post-v1.3.0)

- [x] **Verify backup recovery, not just upload success.** _Done post-v1.3.0:_ each backup provider deploys a monthly restore drill (`workstation-proton-backup-restore-test.*` / `workstation-rclone-backup-restore-test.*`) that downloads one random small file from the remote dataset to a separate temp location and compares SHA-256; results land in `~/.local/state/workstation-backup/restore-tests.jsonl` and `status.json` (`verified_restore_at`), and the backup monitor warns when the last verified restore is older than `workstation_backup_monitor_restore_max_age_hours` (default 1080h = 45d). Read-only on the remote; never overwrites source files. Manual run: `~/.local/bin/workstation-proton-backup-restore-test`.
- [x] **Make backup monitoring independent of one provider.** _Done in v1.3.0:_ providers write a normalized record (`~/.local/state/workstation-backup/status.json`: provider, dataset, host, timestamp, result, `verified_restore_at`) consumed by `workstation-backup-health-check`, and the monitor follows the selected provider's units via `workstation_backup_monitor_service/_timer` facts — no Proton-specific commands or unit names in the monitor logic.
- [x] **Audit sensitive data exposure.** _Done in v1.3.0:_ full-history gitleaks scan (no leaks) plus manual blob scan, recorded in [PUBLIC-RELEASE-AUDIT.md](PUBLIC-RELEASE-AUDIT.md); gitleaks now runs in CI on every push/PR and GitHub secret scanning + push protection are enabled.
- [x] **Harden drift semantics.** _Done post-v1.3.0:_ the drift checker now logs every provisioning re-baseline to `~/.local/state/workstation-drift/baseline-updates.jsonl` and shows a `[REBASELINED]` section in the report, and out-of-band edits can be explicitly acknowledged with `workstation-drift-ack <label>` (reported as `[ACCEPTED]`, still visible, not an issue). Unacknowledged edits stay `[DRIFT]` until resolved. Functional-tested end to end (clean → drift → ack → re-baseline).
- [x] **Surface post-update validation failures reliably.** _Done post-v1.3.0:_ `workstation-post-update-validate --self-test` proves failure (exit 1, ATTENTION REQUIRED, baseline untouched), success, change detection and watch no-op; `workstation-desktop-alerts --self-test` proves failure → notify, duplicate suppression, fresh-failure alerting and recovery (fingerprint cleared) with a stubbed notifier; `validate-workstation.yml` now also checks the alert timer and post-update timer/path are enabled (enforced with `audit_enforce=true`). The GNOME-session delivery itself still needs the manual check in [WORKSTATION-ROUTINE-CHECKLIST.md](WORKSTATION-ROUTINE-CHECKLIST.md) (logged-in session and after logout/login).
- [x] **Document release-to-release compatibility.** _Done post-v1.3.0:_ `workstation_supported_distribution`/`workstation_supported_release`, `workstation_min_ansible_core` (2.18.0) and `workstation_min_python` (3.12) in `group_vars/all.yml`, asserted by `workstation.yml` pre-tasks before any role runs; prerequisites documented in [DEPLOY.md](DEPLOY.md) §2 and README. The clean-VM rehearsal remains the integration proof (see [PUBLIC-RELEASE-AUDIT.md](PUBLIC-RELEASE-AUDIT.md)).

## P1 — Generic deployment (see [DEPLOY.md](DEPLOY.md))

- [x] **Create a generic host profile.** _Done in v1.3.0:_ reusable profiles in `profiles/<name>.yml` selected by `workstation_profile`, plus `setup.yml.example` + `scripts/setup-workstation.py` to generate a new host's inventory entry and `host_vars` from one fill-in file. Adding a host = inventory/profile data + documented manual enrollment only.
- [x] **Introduce capability flags and a provider selection schema.** Implemented as `workstation_capabilities` / `workstation_providers` (defaults in `group_vars/all.yml`, bundled per profile), dispatched by `playbooks/workstation.yml` to vendor-namespaced `roles/providers/<vendor>/<name>/`. Provider values are paths: built-ins `proton/drive`, `google/drive`, `syncthing`, `proton/vpn`, `wireguard`, `proton/mail`, `google/mail`, `proton/pass`, `keepassxc`, `custom`; `none` skips a capability. Swapping a provider is an inventory-variable change only; unknown providers fail with a list of available roles. Remaining: more built-in adapters (see P1 provider-migration items).
- [x] **Split common capability contracts from provider implementations.** _Done in v1.3.0:_ the monolithic `proton` role is split into `proton/{drive,vpn,pass,mail}` (+ shared `_deb`), and every capability has at least two selectable implementations (backup: `proton/drive`/`google/drive`; vpn: `proton/vpn`/`wireguard`; mail: `proton/mail`/`google/mail`; passwords: `proton/pass`/`keepassxc`).
- [x] **Standardize paths, service names and health output.** _Done in v1.3.0:_ backup providers emit the normalized `status.json` record and set `workstation_backup_monitor_service/_timer`, so the monitor, weekly report and alerts are provider-agnostic; other capabilities emit `latest.txt` with an `OVERALL` line. Systemd unit names stay provider-specific by design (side-by-side migration).
- [x] **Make machine identity explicit.** _Done post-v1.3.0:_ each host declares `workstation_device_name` in `host_vars/`; `workstation.yml` asserts it matches the runtime hostname and is unique across the whole inventory (via `hostvars`), backup destinations derive from it, and `scripts/setup-workstation.py` refuses a hostname already declared by another host. Syncthing device IDs / VPN keys / secrets remain manual per machine by design (never cloned).
- [x] **Build a genuinely clean-install test.** _Done in v1.3.0:_ `playbooks/rehearsal-headless.yml` executed on a clean Ubuntu 26.04 Multipass VM (2026-11-04): idempotent (`changed=0`), toolchains verified — see [PUBLIC-RELEASE-AUDIT.md](PUBLIC-RELEASE-AUDIT.md). Run with `--limit <host> -f 1`. Remaining: an interactive GNOME/user-session rehearsal.
- [x] **Handle differences gracefully.** _Done post-v1.3.0:_ the hardware role now also detects battery presence (`workstation_hardware_has_battery`); `qemu-system-x86` installs only when KVM exists or the host is a VM (clear skip message otherwise, `qemu-utils` always); the pinned Proton Pass/Mail DEBs skip with a clear message on non-amd64 unless `workstation_proton_desktop_apps_require_amd64: true`; GNOME remains gated on a detected graphical session. Profiles (`minimal`, `headless`) make optional programs opt-in per host.

## P1 — Provider migration framework (see [MIGRATE.md](MIGRATE.md))

- [x] **Inventory data and authentication per capability.** _Done post-v1.3.0:_ `playbooks/provider-preflight.yml` (drives `scripts/preflight-collect.py`) produces a read-only per-capability inventory — backup dataset counts/bytes (same rsync filters as the upload), remote destination, last status/manifest/restore drill, unit states; Syncthing folders, connected peers and device-ID *prefix* via the local REST API; WireGuard handshake/transfer; KeePassXC vault presence and backup coverage; mail client profile/package presence. It never prints tokens, keys, full device IDs or credentials. Reports land in `~/.local/state/workstation-migration/` (mode 0600).
- [x] **Define provider adapters:** `install`, `configure`, `health`, `export`, `import`, `verify`, `disable` where technically supported; document manual-only steps. _Done post-v1.3.0:_ every provider role declares `workstation_provider_supported_actions` / `workstation_provider_manual_actions` in its defaults and records the contract at `~/.local/state/workstation-provider/<provider>.json` during provisioning; `workstation.yml` post-tasks verify every selected provider recorded it (a new provider without the contract fails the run). See [MIGRATE.md](MIGRATE.md) §5 and [PROVIDERS.md](PROVIDERS.md).
- [x] **Support side-by-side migration.** _Done post-v1.3.0:_ backup providers use distinct unit names (`workstation-proton-backup.*` vs `workstation-rclone-backup.*`), distinct remote destinations, and append each run to `~/.local/state/workstation-backup/history.jsonl` while `status.json` tracks the currently selected provider — old and new can run concurrently without clobbering each other's state. `migrate-backup.yml` asserts the unit names differ before allowing prepare/cutover. Verified by check-mode runs selecting `google/drive` alongside the default.
- [x] **Provide dataset-level checksums and manifest reports.** _Done post-v1.3.0:_ every backup run builds a manifest (`schema_version 1`: dataset_id, host, generated_at, per-file `path`/`size`/`sha256`, `file_count`, `total_bytes`) via the shared `workstation-backup-manifest` helper, keeps it at `~/.local/state/workstation-backup/manifest-latest.json` and uploads it as `manifest.json` next to the dataset; the status record carries `files`/`bytes` and the backup monitor prints them. Disable with `workstation_backup_manifest_enabled: false`.
- [x] **Implement safe cutover / rollback runbooks.** _Done post-v1.3.0:_ `playbooks/migrate-backup.yml` with modes `observe` (default, read-only), `prepare` (preflight + new-provider dry-run + current-provider restore drill + local plan file), `cutover` and `rollback` (require `migration_confirm=true`; only switch systemd timers and append to `~/.local/state/workstation-migration/cutover.jsonl` — never delete data). Data transfer stays manual per [MIGRATE.md](MIGRATE.md) §3.
- [x] **Build at least one non-Proton backup adapter.** _Done in v1.3.0:_ `google/drive` (rclone) works with any rclone remote — Google Drive or SFTP/S3 to a self-hosted VPS — through the same `workstation_backup_*` capability variables and the normalized status record; side-by-side with `proton/drive` during a migration.
- [x] **Add migration-specific checks for password manager, mail, VPN and sync.** _Done post-v1.3.0:_ the preflight collector checks each capability with provider-specific, read-only probes (see first item); capability acceptance during a real migration remains the staged procedure in [MIGRATE.md](MIGRATE.md) §4.

## P2 — Operations improvements

- [ ] **Provider-neutral update review** and validation where third-party APT clients change.
- [ ] **Audit log and report retention**; rotate old reports without deleting backup data.
- [ ] **Alert on missing scheduled executions**, not only failed last runs; verify stale-data thresholds against timer schedules.
- [ ] **Make monitoring robust across sleep/offline intervals** and report missed executions with actionable context.
- [ ] **Test full provisioning idempotency automatically in a disposable VM**, and add Ansible lint. The shared `scripts/maintenance-check.py` gate now runs YAML audit, Python compilation, all playbook syntax checks, inventory parsing and isolated Ansible regression tests in local development and CI. Tests cover all provider contract records plus backup/Syncthing disable guards, absent units, check mode and second-pass convergence with simulated systemd; they do not prove live service behavior or whole-profile convergence. Secret scanning remains a separate CI job.
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
2. ~~P0 hardening (restore drills, drift semantics, post-update alert self-tests, release compatibility pins) and P1 framework (identity assertions, graceful skips, preflight, adapter contracts, manifests, side-by-side, cutover/rollback playbook, per-capability checks) — done post-v1.3.0.~~
3. **First real provider swap:** move one low-risk dataset to the `google/drive` (rclone) backend using `playbooks/migrate-backup.yml` (observe → prepare → cutover) per [MIGRATE.md](MIGRATE.md) §3 and prove rollback.
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
