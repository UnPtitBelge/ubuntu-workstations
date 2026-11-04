# DEPLOY — From two named workstations to a reusable Ubuntu profile

**Status:** Based on the working, public `v1.3.0` repository. It provisions `Omnissiah-desktop` (`desktop`) and `Omnissiah-pocket` (`laptop`), and ships reusable **profiles** (`profiles/`) plus a fill-in onboarding script (`setup.yml.example` + `scripts/setup-workstation.py`) so a third party can add a machine with inventory/profile data only. Enrollment of credentials, device identities and backup destinations is still manual, so this is **not** a fully unattended installer.

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

1. **Inventory:** Add a unique host entry to `ansible/inventory/hosts.yml`, with an explicit inventory name, real hostname, and the same local-connection conventions used by `desktop`/`laptop`. Do not duplicate a host's identity. Confirm with `ansible-inventory --host <new-host>`. **Easy path:** fill in `setup.yml.example`, copy it to `setup.local.yml` (gitignored), and run `python3 scripts/setup-workstation.py --verify` — it generates the entry and variables for you.
2. **Host overrides:** Create `ansible/inventory/host_vars/<new-host>.yml` using the nearest existing host as a *template for nonsecret settings only*. Remove laptop/desktop-only assumptions, hard-coded paths, displays and backup destinations. Prefer shared settings from `group_vars/all.yml`. Generic starting points are provided as inert `.example` files that Ansible never loads: `ansible/inventory/hosts.yml.example` and `ansible/inventory/host_vars/workstation.yml.example`.
3. **Capabilities:** Choose them in the profile (`workstation_capabilities`) and their providers (`workstation_providers`; values are `vendor/name` paths under `ansible/roles/providers/` or `none`). Since v1.3.0 the dispatch and backup monitoring are provider-following, so a third host that opts out of a capability needs **no playbook change** — just the profile/host variables.
4. **Bootstrap:** Install prerequisite packages and clone the repo on the new host. Authenticate the Git remote without sharing SSH private keys from another computer.
5. **Dry run → real run:** From the new host, run syntax check, `--check --diff`, then the actual playbook with `--limit <new-host>`. Never run another local inventory host from the wrong machine.
6. **Manual enrollment:** Sign in to providers; establish the host's unique Syncthing identity and pairing; verify VPN, mail/password-manager sessions as selected; create a **host-specific** backup destination.
7. **Prove data paths:** Check Syncthing two-way transfer, a real Proton backup and a restore to a separate directory; verify credentials work when the backup runs under systemd.
8. **Validate:** Strict audit, timers, lingering, notification delivery in GNOME, backup freshness, health and drift reports, then idempotency.
9. **Record the host:** Document supported hardware, selected capabilities, recovery contacts/locations (not secrets), and known exceptions. Commit only reviewed nonsecret host configuration.

The capability/provider schema below is **implemented** (defaults reproduce the original Proton + Syncthing setup); provider adapters beyond the built-ins in `ansible/roles/providers/` are still future work:

```yaml
workstation_profile: developer_gnome      # profiles/developer_gnome.yml supplies these defaults
workstation_capabilities:
  shell: {enabled: true}
  containers: {enabled: true}
  virtualization: {enabled: true}
  sync: {enabled: true}
  backup: {enabled: true}
  vpn: {enabled: true}
  mail: {enabled: true}
  passwords: {enabled: true}
workstation_providers:                     # vendor/name paths; use "none" to skip a capability
  sync: syncthing
  backup: proton/drive                     # or google/drive (rclone), custom, <vendor>/<name>
  vpn: proton/vpn                          # or wireguard
  mail: proton/mail                        # or google/mail
  passwords: proton/pass                   # or keepassxc
workstation_backup_destination: "<computed/validated per-host destination>"
```

Do not put plaintext access tokens, password-vault exports, recovery phrases or provider session databases in inventory YAML.

## 4. Target architecture for generic deployments (schema implemented; more adapters planned)

```text
Profiles (developer_gnome, headless, lightweight ...)
  └── Capabilities (backup, sync, vpn, mail, passwords, containers ...)
       └── Selected providers (proton/drive, google/drive, syncthing, custom, ...)
            └── Implementation adapters (install/configure/health/export/import)
                 └── Normalized monitoring and migration metadata
```

The selection is implemented in `ansible/inventory/group_vars/all.yml` (`workstation_capabilities`, `workstation_providers`) and dispatched in `ansible/playbooks/workstation.yml` to roles under `ansible/roles/providers/<vendor>/<name>/` (vendor-namespaced, so the project grows by contribution — see [CONTRIBUTING.md](../CONTRIBUTING.md) "Adding a provider"). Built-in providers today: `proton/drive`, `google/drive`, `syncthing`, `proton/vpn`, `wireguard`, `proton/mail`, `google/mail`, `proton/pass`, `keepassxc`, and the guidance-only `custom` — see [PROVIDERS.md](PROVIDERS.md) for the full table, account/secret requirements, and the self-hosted VPS example. To add your own (self-hosted VPS, another vendor), create `ansible/roles/providers/<vendor>/<name>/` in your clone and set `workstation_providers.<capability>: <vendor>/<name>` — no playbook edit needed. Set a provider to `none` to skip a capability. Scope: Ubuntu 26.04 LTS only.

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

Use stable capability names in timers and reports, with provider metadata in the payload. Since v1.3.0 this is implemented for backup: each provider writes `~/.local/state/workstation-backup/status.json` and sets `workstation_backup_monitor_service/_timer`, so monitoring follows the selected provider without renaming anything. Systemd unit names stay provider-specific (`workstation-proton-backup.*`, `workstation-rclone-backup.*`) so old and new can run side by side during a migration—**do not rename them in place without migration and cleanup tasks**.

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

## 6. Where v1.3.0 still falls short

| Ideal | Current status (v1.3.0) | Work required |
| --- | --- | --- |
| Add any machine by choosing a profile | Implemented: `profiles/` + onboarding script; two named hosts tested, one clean-VM rehearsal passed | More clean-install rehearsals per profile; interactive GNOME rehearsal |
| Select providers independently | Implemented: `workstation_providers` dispatch to vendor-namespaced roles; monitoring provider-following | More built-in adapters (see [PROVIDERS.md](PROVIDERS.md)) |
| Switch backup provider without code edits | Selection is a variable change; data migration is a runbook ([MIGRATE.md](MIGRATE.md) §3) | Automated export/import/verify per adapter |
| Preserve cross-provider datasets and metadata | No universal exporter/importer | Format- and provider-specific migration tooling |
| Recover after a host loss | Selected Drive copies + documentation | Regular verified restores, identity and secret enrollment runbook |
| Support any distro/desktop | Ubuntu 26.04 LTS only (explicit scope) | Keep the scope explicit, or add a support matrix later |

**Recommendation:** Make *Ubuntu 26.04 GNOME developer workstation* the first supported generic profile. Expand only after a third-host rehearsal passes; genericity is valuable only if it remains reliable.

## 7. Registering an additional tool in backup and maintenance (implemented)

Adding a tool to the managed set is configuration-only — no playbook or script edits are required:

| Concern | Variable | Defined in |
| --- | --- | --- |
| Tool data to back up | `workstation_backup_sources` | `ansible/inventory/group_vars/all.yml` (or `host_vars/`; provider defaults in e.g. `ansible/roles/providers/proton/drive/defaults/main.yml`) |
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

## 8. Profiles — multiple setups from one repository (implemented)

A **profile** is one YAML file in `profiles/<name>.yml` that bundles a coherent setup: capabilities, providers, foundation-role toggles and health-check lists. Select it per host:

```yaml
# host_vars/<host>.yml (or `profile:` in setup.local.yml, or -e workstation_profile=<name>)
workstation_profile: developer_gnome
```

The playbook validates the profile exists (unknown name → error listing available profiles) and the profile supplies defaults at inventory level, so `host_vars` can still override any individual key per machine. Built-in profiles:

| Profile | Contents | Providers |
| --- | --- | --- |
| `developer_gnome` (default) | Full GNOME desktop: GNOME, toolchains, Docker/Containerlab, QEMU/Multipass, backups, full monitoring | proton/drive, syncthing, proton/vpn, proton/mail, proton/pass |
| `minimal` | Base packages, Fish/Ghostty, mise/uv/rustup bootstrap, security updates, monitoring only | none |
| `headless` | Server: base, shell, languages, containers, monitoring; no GNOME | google/drive (rclone), syncthing, wireguard |

Switching an existing host to a smaller profile: first set the legacy enable flags (`workstation_backup_enabled: false`, `workstation_syncthing_enabled: false`) and run once with the previous provider still selected so its units are stopped, then switch the profile. Never let a profile change delete data (see [MIGRATE.md](MIGRATE.md)).

Adding a profile = adding one `profiles/<name>.yml` file — no playbook or role edits (see [CONTRIBUTING.md](../CONTRIBUTING.md) "Adding a profile"). Scope remains Ubuntu 26.04 LTS only.
