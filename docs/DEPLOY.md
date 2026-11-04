# Deploy configuration changes

This guide owns the workflow for applying repository intent to a workstation.
For everyday status use [Operations](OPERATIONS.md); for a fresh installation use
[Tutorial: first installation](../TUTORIAL.md#first-installation). Commands below are Fish-compatible.

## 1. Scope

Provisioning installs/configures packages, dotfiles, user services and maintenance
jobs. It can start enabled timers and refresh drift baselines. Review the preview
before applying; capture unexpected drift first. It does not enroll accounts,
copy device identities or migrate provider data.

## 2. Prerequisites and machine identity

The main playbook asserts Ubuntu **26.04 LTS**, ansible-core **≥ 2.18.0** and
Python **≥ 3.12**. See [shared inventory](../ansible/inventory/group_vars/all.yml)
for the authoritative supported-platform variables and
[compatibility notes](DEPLOY.md#sudo-compatibility) for the recorded sudo issue.

Confirm the actual clone, Git branch/status and local machine before a run:

```fish
cd ~/Projects/ubuntu-workstations
pwd
hostname
git status --short
git branch --show-current
git log -1 --oneline
```

Both `desktop` and `laptop` use `ansible_connection: local`. A different `--limit`
does not switch physical machines. Use the matching inventory name on that
machine. For a new host, use its own inventory entry.

The runtime hostname supplies the default backup identity. An optional
`workstation_device_name` belongs in the gitignored
`ansible/inventory/host_vars/<host>/local.yml`. The playbook checks declared
non-placeholder identities against the runtime hostname and for uniqueness.
Never commit real hostnames, cloud sessions, private keys or Syncthing identities.

### Sudo compatibility

An earlier Ubuntu 26.04 deployment recorded Ansible escalation failures with
sudo-rs (Ubuntu issue #2122414). This is historical evidence, not a claim that
every current sudo-rs version is incompatible. Inspect the installed alternatives
and the actual first error before changing anything:

```fish
sudo --version
update-alternatives --display sudo
```

The recorded workaround selected `/usr/bin/sudo.ws` with
`sudo update-alternatives --set sudo /usr/bin/sudo.ws`; the previous sudo-rs
alternative was `/usr/lib/cargo/bin/sudo`. Only change alternatives after
confirming the available paths and approving the workaround on that machine;
record the previous alternative for reversal. Do not bypass escalation by
weakening permissions or granting passwordless sudo on a real workstation.

## 3. Preview, apply and verify

Set exactly one target, matching the machine you are using:

```fish
set target desktop
# On the laptop use: set target laptop
cd ~/Projects/ubuntu-workstations/ansible
ansible-inventory -i inventory/hosts.yml --host $target
ansible-playbook playbooks/workstation.yml --syntax-check
and ansible-playbook playbooks/workstation.yml --check --diff -K --limit $target
```

Inspect inventory output locally before sharing it. Check mode is a preview;
first-install/bootstrap tasks may be skipped and a successful preview does not
prove that deployment will succeed.

After reviewing the preview, deliberately apply and validate:

```fish
ansible-playbook playbooks/workstation.yml -K --limit $target
and ansible-playbook playbooks/validate-workstation.yml -e audit_enforce=true --limit $target
```

Stop at the first failed task and diagnose it. Do not rerun unrelated installers
or weaken assertions. The strict audit currently assumes the full desktop tool
set; it is not yet a complete profile-aware audit for `minimal` or `headless`.
A reduced profile needs explicit validation of its selected services and tools.

After a successful run and relevant service checks, verify convergence:

```fish
ansible-playbook playbooks/workstation.yml -K --limit $target
```

Expect `failed=0`, `unreachable=0`, `changed=0`. A real second pass is required;
syntax checks and check mode do not establish idempotency. Inspect job outcomes,
GNOME/session behavior and authenticated backups separately where applicable.

Review/stage only intended nonsecret changes. Commit/push are deliberate Git
actions, not provisioning tasks. Apply the reviewed revision to the other machine
separately, after checking its local changes and selecting its own limit.

## 4. Provider selection

`workstation_capabilities` enables backup, sync, VPN, mail and passwords;
`workstation_providers` chooses their role paths. Containers, languages,
virtualization and GNOME use separate `workstation_role_*` toggles.
See [Providers](PROVIDERS.md) for complete selection examples. A variable change
selects implementation; [Migration](MIGRATE.md) owns data transfer and cutover.

## 5. New machines

Use [Tutorial: first installation](../TUTORIAL.md#first-installation). `setup.yml.example` and
`scripts/setup-workstation.py` generate inventory data; even `--verify` **writes
that data before running checks**. The script never provisions. Account sign-in,
Syncthing pairing, backup destinations and recovery proof remain manual.

## 6. Verification limits and rollback

| Evidence | Establishes | Does not establish |
| --- | --- | --- |
| Shared repository gate | Static checks and isolated task regression coverage | Live services or cloud authentication |
| Foundation VM rehearsal | Selected foundation roles in a disposable environment | Full profiles, GNOME, provider enrollment or cloud recovery |
| Strict host audit | The checks implemented in `validate-workstation.yml` | Every configured feature or real restored data |
| Second normal provisioning pass | Convergence for that revision and host | Backup recoverability |

For configuration rollback, review the earlier revision's diff and a check-mode
preview before reapplying it. Reverting Git does not roll back package versions,
provider data or credentials automatically. Keep independent recovery evidence
and use a provider-specific rollback plan for migrations.

## 7. Where to change settings

| Concern | Source of truth |
| --- | --- |
| Common packages, toolchain intent, backup selection and report sources | `ansible/inventory/group_vars/all.yml`, `dotfiles/mise/config.toml` |
| Feature/provider bundles | `profiles/<name>.yml` |
| Per-host hardware and approved exceptions | `ansible/inventory/host_vars/<host>.yml` |
| Private hostname override | Gitignored `ansible/inventory/host_vars/<host>/local.yml` |
| Job schedules, thresholds and monitored services | Relevant role's `defaults/main.yml` and unit templates/files; shared/host overrides where present |
| Drift allowlist | `ansible/roles/drift/defaults/main.yml` |
| Additional APT review/validation groups | `apt_update_review` / `post_update_validation` role defaults |

Ansible precedence applies: inspect higher-precedence inventory overrides before
changing a role default. Some schedules are currently literal unit settings,
not variables. Adding data to backup sources does not automatically add service
health checks, update coverage or restore acceptance tests for that application.

## 8. Profiles

| Profile | Selected features | Providers |
| --- | --- | --- |
| `developer_gnome` | Full desktop, toolchains, containers, virtualization and maintenance | Proton Drive/VPN/Mail/Pass, Syncthing |
| `minimal` | Base, shell/bootstrap and maintenance; no selected provider | None |
| `headless` | Shell/toolchains, containers and maintenance; no GNOME role | rclone, Syncthing, WireGuard; backup scheduling initially disabled |

Select `workstation_profile` per host. Profiles select roles and defaults;
`headless`/`minimal` do not guarantee that all desktop packages and desktop alert
roles are excluded. Inspect the playbook and selected roles before treating them
as a universal unattended installer.

### Provider disabling and profile changes

| Intent | Required configuration while the previous capability/provider is still selected |
| --- | --- |
| Stop backup scheduling | `workstation_backup_enabled: false` or `workstation_backup_timer_enabled: false`; stops existing upload and restore-drill timers |
| Stop Syncthing | `workstation_syncthing_enabled: false` or `workstation_syncthing_service_enabled: false`; stops/disables the existing user service |
| Stop VPN or desktop application runtime | Manual, provider-specific operation; declared manual in adapter contracts |

Capability `enabled: false` or provider `none` **skips** the role and leaves its
existing services alone. Before changing to a smaller profile, keep the previous
profile/capabilities/providers selected, set the explicit disable flags, preview
and apply during an approved maintenance window. Verify stopped schedules or
services, then change the profile. A provider swap never decommissions its
predecessor implicitly.

Backup disablement stops future timer invocations, not an in-progress upload or
download. Data, credentials and Syncthing identities remain. Monitoring units
and old reports also remain and may warn; their retirement is separate work.
To reverse a disable, restore the previous selection and enable flags, preview
and apply on the same host.
