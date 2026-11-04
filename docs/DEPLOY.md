# DEPLOY — From two named workstations to a reusable Ubuntu profile

**Status:** Design and runbook based on the working `v1.2.0` deployment. The **current** repository provisions `Omnissiah-desktop` (`desktop`) and `Omnissiah-pocket` (`laptop`). It is **not yet** a generic, fully unattended installer.

See [TODO.md](TODO.md) for the implementation backlog and [MIGRATE.md](MIGRATE.md) for changing providers after deployment. For existing operational commands, see [WORKSTATION-CHEATSHEET.md](WORKSTATION-CHEATSHEET.md).

## Goal and boundaries

**Desired future behavior:** Given a supported Ubuntu machine, a repository clone, a host profile and a set of capabilities/providers, provision the workstation repeatably. A new device should require only machine-specific facts, enrollment of credentials/identities, and final verification—**not** editing dozens of roles.

**Current guarantees:** Tested on two Ubuntu 26.04 workstations with local Ansible execution; common shell, GNOME, language runtimes, Docker, virtualization, Syncthing, Proton and maintenance automation are Ansible-managed. Authentication and device identity require manual enrollment.

**Not guaranteed:** Unattended encrypted-disk setup, cloning a home directory, hardware-specific layouts, provider export/import, seamless VPN/keyring login, or successful remote backup restoration without a test.

## 1. Existing architecture

```text
Git repository
  ansible/inventory/hosts.yml                host identities
  ansible/inventory/group_vars/all.yml        shared defaults
  ansible/inventory/host_vars/<host>.yml       host overrides
  ansible/playbooks/workstation.yml           role orchestration
  ansible/roles/                            implementation
  docs/                                     runbooks

On each workstation:
  Ansible (local) → system packages, configurations, user services and timers
  Syncthing       → selected synchronized files (not backups)
  Backup service  → filtered, host-specific Proton Drive copies
  Monitors        → health, selected-file drift, backup state, updates and alerts
```

Most maintenance timers are **systemd user units**. `Linger=yes` allows user services to run after logout, but GNOME notifications require a suitable graphical session and cloud credentials still need valid unattended access.

## 2. Provision an existing supported inventory host (implemented)

Run these **on the machine being configured**, from its own login; don't target the other machine using an inventory entry with `ansible_connection: local`.

```fish
# On Omnissiah-desktop:
set target desktop
# On Omnissiah-pocket, instead:
# set target laptop

cd ~/Projects/ubuntu-workstations
git status --short
# If clean and tracking the correct remote:
git pull --ff-only

cd ansible
ansible-inventory -i inventory/hosts.yml --host $target
ansible-playbook playbooks/workstation.yml --syntax-check
and ansible-playbook playbooks/workstation.yml --check --diff -K --limit $target
# Review expected changes; then run for real:
ansible-playbook playbooks/workstation.yml -K --limit $target
and ansible-playbook playbooks/validate-workstation.yml -e audit_enforce=true --limit $target
# Test idempotency:
ansible-playbook playbooks/workstation.yml -K --limit $target
```

Aim for `failed=0`, `unreachable=0` and `changed=0` on the second stable run. Check mode is a preview, not a substitute for real execution. If GNOME configuration is skipped, inspect graphical-session preconditions.

### New install prerequisites

For a future machine, first install a supported Ubuntu release and configure disk encryption, user login, networking, Git access, and a usable sudo implementation. Then install Ansible and Git if needed:

```fish
sudo apt-get update
sudo apt-get install -y git ansible-core ca-certificates
mkdir -p ~/Projects
# Clone your VERIFIED repository URL into ~/Projects/ubuntu-workstations.
```

**Do not paste a sample `git clone` URL as-is.** Keep bootstrap secrets, private keys and personal credentials out of Git.

## 3. Adding a third machine today (partially manual)

1. **Inventory:** Add a unique host entry to `ansible/inventory/hosts.yml`, with an explicit inventory name, real hostname, and the same local-connection conventions used by `desktop`/`laptop`. Do not duplicate a host's identity. Confirm with `ansible-inventory --host <new-host>`.
2. **Host overrides:** Create `ansible/inventory/host_vars/<new-host>.yml` using the nearest existing host as a *template for nonsecret settings only*. Remove laptop/desktop-only assumptions, hard-coded paths, displays and backup destinations. Prefer shared settings from `group_vars/all.yml`. Generic starting points are provided as inert `.example` files that Ansible never loads: `ansible/inventory/hosts.yml.example` and `ansible/inventory/host_vars/workstation.yml.example`.
3. **Capabilities:** Audit each role's `when:` conditions and defaults. At `v1.2.0`, Proton and backup-monitoring logic still have provider-specific expectations, so a third host that opts out may need a reviewed playbook change.
4. **Bootstrap:** Install prerequisite packages and clone the repo on the new host. Authenticate the Git remote without sharing SSH private keys from another computer.
5. **Dry run → real run:** From the new host, run syntax check, `--check --diff`, then the actual playbook with `--limit <new-host>`. Never run another local inventory host from the wrong machine.
6. **Manual enrollment:** Sign in to providers; establish the host's unique Syncthing identity and pairing; verify VPN, mail/password-manager sessions as selected; create a **host-specific** backup destination.
7. **Prove data paths:** Check Syncthing two-way transfer, a real Proton backup and a restore to a separate directory; verify credentials work when the backup runs under systemd.
8. **Validate:** Strict audit, timers, lingering, notification delivery in GNOME, backup freshness, health and drift reports, then idempotency.
9. **Record the host:** Document supported hardware, selected capabilities, recovery contacts/locations (not secrets), and known exceptions. Commit only reviewed nonsecret host configuration.

Example inventory variables below are **design sketches**, not supported by the current roles:

```yaml
# PROPOSED future profile, NOT active v1.2.0 schema
workstation_profile: developer_gnome
workstation_capabilities:
  shell: {enabled: true}
  containers: {enabled: true}
  virtualization: {enabled: true}
  sync: {enabled: true}
  backup: {enabled: true}
  vpn: {enabled: true}
  mail: {enabled: true}
  passwords: {enabled: true}
workstation_providers:
  sync: syncthing
  backup: proton_drive
  vpn: proton_vpn
  mail: proton_mail
  passwords: proton_pass
workstation_backup_destination: "<computed/validated per-host destination>"
```

Do not put plaintext access tokens, password-vault exports, recovery phrases or provider session databases in inventory YAML.

## 4. Target architecture for generic deployments (not implemented)

```text
Profiles (developer_gnome, headless, lightweight ...)
  └── Capabilities (backup, sync, vpn, mail, passwords, containers ...)
       └── Selected providers (proton_drive, another_backup, syncthing, ...)
            └── Implementation adapters (install/configure/health/export/import)
                 └── Normalized monitoring and migration metadata
```

### Capability contracts

A capability should specify its **inputs**, **outputs** and **observable state**. For example:

| Capability | Common inputs | Common health output | Provider-specific work |
| --- | --- | --- | --- |
| Backup | Dataset manifest, destination, schedule, encryption policy | Last *verified* success, age, restore evidence | Authentication, upload, remote verification, restore |
| Sync | Folder IDs, paths, sharing policy, versioning | Peer reachability, freshness, conflicts | Pairing, service config, device identity |
| VPN | Connection policy, routing/DNS requirements | Client installed, service state, connectivity evidence | Provider login, tunnel/profile format |
| Password manager | Browser/desktop integration, export policy | App availability; vault health may be manual | Export/import, organization and sharing metadata |
| Mail | Accounts, domains, local client preferences | Application availability; delivery tests | Migration of messages, folders, contacts, aliases |

Provider adapters should be independently selectable; installing an alternative backup provider must not require installing Proton Pass or Proton VPN. Where provider APIs don't support export/import or verification, declare manual steps instead of silently reporting success.

### Standardized paths and reports (proposal)

Use stable capability names in timers and reports, with provider metadata in the payload. E.g., a future `workstation-backup.service` could call the selected adapter and emit `~/.local/state/workstation-backup/status.json`. Today the working units are named `workstation-proton-backup.*`, and monitoring is tied to them—**do not rename them in place without migration and cleanup tasks**.

### Safety requirements for profiles

- Validate profile/provider combinations *before* changing packages or services.
- Be explicit about provider ownership and uninstall policy. Never delete old data as a side effect of switching a provider variable.
- Avoid unbounded `latest` upgrades; keep version and update policy separate from provider selection.
- Support `enabled: false` without a dependent monitoring role asserting an enabled timer.
- Make backup paths and credentials unique per host; ensure the destination is not shared accidentally.
- Keep `--check` safe and avoid generated baselines masking preexisting drift.

## 5. Acceptance criteria for a generic third-workstation deployment

- [ ] A third inventory host can be added with **inventory/profile data only**, without editing the playbook or existing roles.
- [ ] An optional provider can be replaced/disabled without unrelated capabilities failing.
- [ ] A fresh supported machine provisions reproducibly, passes strict validation and a second idempotent run.
- [ ] New host identities and secrets stay separate from all existing machines.
- [ ] Scheduled backup and recovery are validated using real data and a restore test.
- [ ] Monitoring and notifications use capability-neutral status records.
- [ ] The release documents exact prerequisites, unsupported profiles/hardware and a rollback path.

## 6. Where v1.2.0 falls short

| Ideal | Current status | Work required |
| --- | --- | --- |
| Add any machine by choosing a profile | Two named local hosts tested | Generic host inventory/profile and clean-install tests |
| Select providers independently | Proton roles and monitoring are coupled | Capability flags + provider-specific adapters |
| Switch backup provider without code edits | Backup script/monitor reference Proton | Provider-neutral backup contract, migration and rollback |
| Preserve cross-provider datasets and metadata | No universal exporter/importer | Format- and provider-specific migration tooling |
| Recover after a host loss | Selected Proton Drive copies + documentation | Regular verified restores, identity and secret enrollment runbook |
| Support any distro/desktop | Ubuntu 26.04/GNOME focused | Support matrix and conditional roles, or explicitly limit scope |

**Recommendation:** Make *Ubuntu 26.04 GNOME developer workstation* the first supported generic profile. Expand only after a third-host rehearsal passes; genericity is valuable only if it remains reliable.

## 7. Registering an additional tool in backup and maintenance (implemented)

Adding a tool to the managed set is configuration-only — no playbook or script edits are required:

| Concern | Variable | Defined in |
| --- | --- | --- |
| Tool data to back up | `workstation_backup_sources` | `ansible/roles/backup/defaults/main.yml` (or `host_vars/`) |
| Tool caches excluded from backups | `workstation_backup_excludes` | same |
| Backup dataset label | `workstation_backup_dataset_id` | same |
| Health-checked units | `workstation_health_system_services`, `workstation_health_user_services`, `workstation_health_system_timers` | `ansible/roles/health/defaults/main.yml` |
| Drift-monitored config files | `workstation_drift_targets` | `ansible/roles/drift/defaults/main.yml` |
| Reports consolidated weekly and alerted on | `workstation_report_sources` (optional per-source `max_age_hours`) | `ansible/inventory/group_vars/all.yml` |
| APT update discovery | `workstation_tool_updates_packages` | `ansible/roles/tool_updates/defaults/main.yml` |
| APT update review groups | `workstation_apt_update_review_groups` | `ansible/roles/apt_update_review/defaults/main.yml` |
| Post-update validation groups | `workstation_post_update_groups` | `ansible/roles/post_update_validation/defaults/main.yml` |
| Toolchains themselves | `dotfiles/mise/config.toml`, `workstation_python_tools`, `workstation_python_versions`, `workstation_rust_toolchain` | repo dotfiles / `group_vars/all.yml` |

Behavior notes:

- mise, uv and rustup tools are discovered automatically by `workstation-tool-update-check` (uv via `uv tool list --outdated`); only APT-packaged tools need the `workstation_tool_updates_packages` entry.
- Tool binaries under `~/.local`, `~/.cargo`, `~/.rustup` and `~/.local/share/mise` are intentionally **not** backed up — they are reproducible from this repository. Back up only tool *data*.
- Each successful backup writes a normalized record to `~/.local/state/workstation-backup/status.json` (schema in [MIGRATE.md](MIGRATE.md) §5: `schema_version`, `capability`, `provider`, `host`, `dataset_id`, `checked_at`, `result`, `verified_restore_at`). `workstation-backup-health-check` consumes that record and falls back to the legacy `last-success` stamp for older deployments, so a future backup provider can be monitored without changing the monitor. The systemd unit names remain Proton-specific until a reviewed migration renames them.
- New APT groups in `workstation_post_update_groups` get a generic "package still installed" check after upgrades; `docker` and `proton` keep their deeper service checks.
