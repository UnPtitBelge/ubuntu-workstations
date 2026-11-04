# Ubuntu Workstations

**One Git repository. One Ansible configuration. Two reproducible Ubuntu workstations.**

An opinionated personal workstation setup for **Ubuntu Desktop 26.04 LTS**, managed with **Ansible + Git**. It keeps the development environment, GNOME configuration and maintenance policy consistent while preserving each machine's hardware settings, device identity, credentials and backup destination.

**Current release:** `v1.2.0` — deployed and validated on both workstations.

| Inventory host | Machine | Role in the workflow |
| --- | --- | --- |
| `desktop` | `Omnissiah-desktop` | Primary development and configuration machine |
| `laptop` | `Omnissiah-pocket` | Secondary workstation; receives reviewed changes from Git |

> **Start here:** [Command cheatsheet](docs/WORKSTATION-CHEATSHEET.md) · [Routine maintenance checklist](docs/WORKSTATION-ROUTINE-CHECKLIST.md) · [Deployment & portability](docs/DEPLOY.md) · [Provider migration](docs/MIGRATE.md) · [Roadmap / TODO](docs/TODO.md) · [Installation](docs/WORKSTATION-INSTALL.md) · [Recovery](docs/WORKSTATION-RECOVERY.md)

## What Ansible manages

| Area | Components |
| --- | --- |
| Desktop | GNOME 50, Yaru Blue Dark, appearance settings, Ubuntu Dock, shortcuts and Resource Monitor |
| Shell | Fish, Ghostty, Starship, zoxide and shell configuration |
| Development | Git, mise (Node.js 22, Java and selected npm CLIs), uv/Python, rustup/Rust |
| Containers | Docker Engine, Compose, Buildx and Containerlab |
| Virtualization | QEMU and Multipass; hardware/KVM detection |
| Synchronization | Syncthing user service; approved shared folders and file versioning |
| Proton | Drive CLI, Pass, Mail and Proton VPN |
| Backups | Filtered, machine-specific Proton Drive uploads via a scheduled systemd user service |
| Security | Automatic eligible Ubuntu security updates; no automatic reboot |
| Monitoring | System health, selected-file drift, backup freshness, weekly reports and GNOME failure alerts |
| Update management | Read-only version discovery, update notifications, controlled mise/APT review and post-update validation |
| Release checks | Strict Ansible validation, local release audit and Git-tagged releases |

**Scope:** This repository is not a disk image or a fully unattended account bootstrapper. Syncthing identities, Proton logins, SSH keys, secrets, GNOME login state and data outside the configured backup selection remain machine-specific. An active timer is not proof of a successful job; read its report or journal.

## Repository layout

```text
.
├── .github/workflows/               # CI: gitleaks secret scan + YAML/Python/Ansible static checks
├── .gitattributes                   # LF normalization; binary assets untouched
├── LICENSE                          # MIT
├── SECURITY.md                      # private vulnerability reporting
├── CONTRIBUTING.md                  # change and validation workflow
├── ansible/
│   ├── ansible.cfg
│   ├── inventory/
│   │   ├── hosts.yml (+ hosts.yml.example for new machines)
│   │   ├── group_vars/all.yml
│   │   └── host_vars/
│   │       ├── desktop.yml
│   │       ├── laptop.yml
│   │       └── *.yml.example           # inert per-host templates
│   ├── playbooks/
│   │   ├── workstation.yml             # Main provisioning
│   │   ├── validate-workstation.yml    # Strict workstation validation
│   │   └── rehearsal-headless.yml      # Optional disposable-VM test
│   └── roles/
│       ├── backup/                     # Proton Drive backup
│       ├── backup_monitor/             # Backup success and freshness
│       ├── base/
│       ├── bootstrap/
│       ├── containers/
│       ├── desktop_alerts/             # GNOME failure alerts
│       ├── drift/                      # Selected-file checksums
│       ├── gnome/
│       ├── hardware/
│       ├── health/
│       ├── languages/
│       ├── maintenance/                # Ubuntu security-update policy
│       ├── post_update_validation/
│       ├── proton/
│       ├── release_audit/
│       ├── shell/
│       ├── syncthing/
│       ├── tool_update_alerts/
│       ├── tool_update_policy/
│       ├── tool_updates/
│       ├── apt_update_review/
│       ├── virtualization/
│       └── weekly_report/
├── assets/                              # Optional versioned appearance assets
├── docs/
│   ├── WORKSTATION-CHEATSHEET.md
│   ├── WORKSTATION-ROUTINE-CHECKLIST.md
│   ├── DEPLOY.md                     # New hosts and provider architecture
│   ├── MIGRATE.md                    # Provider cutover and rollback
│   ├── TODO.md                       # Prioritized implementation gaps
│   ├── WORKSTATION-INSTALL.md
│   ├── WORKSTATION-RECOVERY.md
│   ├── REPOSITORY-AUDIT.md
│   └── v1.2.0-release-checklist.md
└── scripts/                             # repository utilities (read-only audit, bootstrap, maintenance gate)
```

The tree above describes the intended v1.2.0 layout; optional assets and documentation may vary. Shared defaults belong in role defaults and `inventory/group_vars/all.yml`; host-specific settings belong in `inventory/host_vars/`. Don't copy device IDs, application sessions or credentials between machines.

## Portability roadmap

The existing v1.2.0 configuration is **tested on two named Ubuntu workstations**; it is not yet a universal installer or fully provider-independent. In particular, Proton backup implementation and monitoring are provider-coupled. The next architectural goal is to separate **capabilities** (backup, sync, VPN, mail, passwords) from **providers** (such as Proton Drive or another backup service), while keeping per-host secrets and data migration explicit.

- **[DEPLOY.md](docs/DEPLOY.md):** deploy an existing host today; design and acceptance criteria for new generic workstations.
- **[MIGRATE.md](docs/MIGRATE.md):** inventory, export/import, verification, cutover and rollback when replacing any provider or tool.
- **[TODO.md](docs/TODO.md):** prioritized, testable work remaining; proposed features are not presented as implemented.

## Quick start

Run Ansible **locally on the workstation being configured**, preferably from its logged-in GNOME session. All commands below are **Fish-compatible**.

### 1. Bootstrap a fresh Ubuntu installation

```fish
sudo apt-get update
sudo apt-get install -y git ansible-core ca-certificates
mkdir -p ~/Projects
cd ~/Projects
git clone <YOUR_GIT_REMOTE_URL> ubuntu-workstations
cd ubuntu-workstations/ansible
```

Replace `<YOUR_GIT_REMOTE_URL>` with your actual private/public repository remote. If the repo already exists, **do not clone over it**; review `git status` and use `git pull --ff-only` after resolving local changes.

### 2. Select the correct machine

```fish
# On Omnissiah-desktop:
set target desktop

# On Omnissiah-pocket, use instead:
# set target laptop

ansible-inventory -i inventory/hosts.yml --graph
ansible-inventory -i inventory/hosts.yml --host $target
```

Ensure the selected inventory host refers to the **local machine** before applying changes. The two named inventory hosts use local provisioning; `--limit` is an important safeguard.

### 3. Validate, preview and apply

```fish
ansible-playbook playbooks/workstation.yml --syntax-check
and ansible-playbook playbooks/workstation.yml --check --diff -K --limit $target

# Review the preview before running the actual deployment:
ansible-playbook playbooks/workstation.yml -K --limit $target
and ansible-playbook playbooks/validate-workstation.yml -e audit_enforce=true --limit $target

# Run a second time to check idempotency:
ansible-playbook playbooks/workstation.yml -K --limit $target
```

Aim for `failed=0` and **`changed=0`** on the second run. A check-mode preview cannot guarantee that a subsequent real run will succeed; some setup tasks are intentionally skipped in check mode. GNOME settings require a suitable graphical session; logging out and back in may be necessary for some changes.

**Ubuntu 26.04 sudo note:** If Ansible privilege escalation fails unexpectedly, inspect the configured `sudo` alternative (`sudo-rs` versus traditional sudo) instead of weakening permissions.

## Working across two machines

The default workflow is **desktop → test → validate → commit → push → laptop pull → validate**.

On the desktop, make focused changes, then check and push them:

```fish
cd ~/Projects/ubuntu-workstations

git status --short
git diff --check
git diff
# Stage only the files you reviewed:
# git add <paths>
# git diff --cached
# git commit -m '...'
# git push origin main
```

On the laptop:

```fish
cd ~/Projects/ubuntu-workstations
git status --short
git pull --ff-only
cd ansible
ansible-playbook playbooks/workstation.yml -K --limit laptop
and ansible-playbook playbooks/validate-workstation.yml -e audit_enforce=true --limit laptop
```

Never run `--limit desktop` on the laptop or `--limit laptop` on the desktop merely to make the inventory match a different machine.

## Automated maintenance (v1.1.0)

Normal upkeep should require **no daily manual interaction** when the machine is healthy.

| Service | Automation | Important boundary |
| --- | --- | --- |
| Ubuntu updates | Daily unattended eligible security upgrades | Third-party Docker/Proton upgrades and automatic reboots are excluded |
| Health | Daily checks of Docker, Syncthing, disk, update timers and reboot requirement | Detects problems; doesn't repair them |
| Drift | Daily comparison of selected managed files against a deployed baseline | Not a full Git-to-system or whole-machine audit; provisioning can refresh the baseline |
| Backup | Scheduled Proton Drive upload, plus backup freshness/failure monitoring | Requires machine-local authentication; periodically test restores |
| Weekly report | Consolidates health, drift and backup-monitor results | Stale and missing reports require investigation |
| Alerts | GNOME notification on detected failures with suppression | Graphical notifications require an active session |

Systemd **user lingering** is enabled for unattended user timers; a running user manager does not itself provide an active graphical notification session.

### Inspect scheduled jobs and reports

```fish
systemctl --user list-timers --all
systemctl list-timers apt-daily.timer apt-daily-upgrade.timer
loginctl show-user (whoami) -p Linger

cat ~/.local/state/workstation-weekly-report/latest.txt
cat ~/.local/state/workstation-health/latest.txt
cat ~/.local/state/workstation-drift/latest.txt
cat ~/.local/state/workstation-backup-monitor/latest.txt

systemctl --user --failed --no-pager
journalctl --user -u workstation-proton-backup.service -n 50 --no-pager
```

## Development updates (v1.2.0)

Updates to Docker, Proton and pinned language runtimes are **reviewed, not blindly applied**. An approved change belongs in Ansible/Git, followed by validation.

```fish
# Discover available updates without installing them
~/.local/bin/workstation-tool-update-check
~/.local/bin/workstation-tool-update-policy
~/.local/bin/workstation-apt-update-review --group docker --plan
~/.local/bin/workstation-apt-update-review --group proton --plan

# Post-update validation: automatic watcher and manual checks
~/.local/bin/workstation-post-update-validate --watch
~/.local/bin/workstation-post-update-validate --check docker
~/.local/bin/workstation-post-update-validate --check proton

# Release readiness
~/.local/bin/workstation-release-audit
```

The update checker is informational. Exact mise pins may hide newer versions from `mise outdated`; an APT candidate is not automatically an approved upgrade. Docker upgrades may restart workloads, and Proton VPN upgrades may interrupt connectivity. Post-update checks do not prove a VPN is connected or remote backups are recoverable.

## Syncthing, Proton and backups

Syncthing uses its own identity on each machine. Pair devices through <http://127.0.0.1:8384>, approve shared folders and verify bidirectional sync. **Syncthing is synchronization, not backup.**

Proton Drive, Pass, Mail and VPN are installed/configured by their respective roles as applicable, but **sign-in remains interactive and machine-local**. Do not commit account tokens or password-store data.

**External services and accounts:** Proton VPN, Drive, Pass and Mail require a Proton account (Drive storage and VPN need a paid plan); Syncthing needs a second paired device but no account; package installation uses the public Ubuntu, Docker and Proton APT repositories plus upstream project sites (mise, uv, rustup, containerlab, GitHub releases). No role embeds credentials or sends data anywhere except the explicitly configured Proton Drive backup destination.

The backup destination is machine-specific:

```text
/my-files/Workstation-Backups/Omnissiah-desktop/
/my-files/Workstation-Backups/Omnissiah-pocket/
```

Scheduled backups are enabled on both workstations. Review selection/exclusions in `ansible/roles/backup/defaults/main.yml` and host variables; do not assume that every personal file, Docker volume or VM disk is included.

```fish
# Inspect what would be backed up (no upload)
~/.local/bin/workstation-proton-backup --show-excludes
~/.local/bin/workstation-proton-backup --dry-run

# Inspect scheduling, success and failures
systemctl --user status workstation-proton-backup.timer --no-pager
stat -c '%y %n' ~/.local/state/workstation-backup-monitor/last-success
journalctl --user -u workstation-proton-backup.service -n 50 --no-pager

# Check Proton Drive access
proton-drive filesystem list /my-files
```

**Recovery assurance:** Periodically restore a real file from Proton Drive into a *separate* location and compare it with the source. A healthy timer or success timestamp is not a substitute for a restore test. Starting `workstation-proton-backup.service` triggers a real upload; do so intentionally.

## Tests, recovery and safe operations

```fish
# Repository audit (read-only)
cd ~/Projects/ubuntu-workstations
python3 scripts/audit-workstation.py .

# Strict machine validation (choose the host you're on)
cd ansible
ansible-playbook playbooks/validate-workstation.yml -e audit_enforce=true --limit desktop
# On the laptop: use --limit laptop.
```

The optional `rehearsal-headless.yml` playbook tests foundational provisioning in a disposable VM; it does **not** validate GNOME visuals, Proton logins, Syncthing pairing or authenticated user-session services.

**Operating principles:** audit first; change narrowly; preserve working state; rerun validation; verify idempotency; commit. Never store credentials in Git. Don't automatically prune Docker volumes, delete backup history, reset Proton sessions or overwrite Syncthing identities to make a health check pass.

## Documentation

- **[Command cheatsheet](docs/WORKSTATION-CHEATSHEET.md)** — important commands, logs, timers, update reviews and common failure triage.
- **[Routine maintenance checklist](docs/WORKSTATION-ROUTINE-CHECKLIST.md)** — what to do weekly, monthly, quarterly and after an alert.
- **[Installation guide](docs/WORKSTATION-INSTALL.md)** — new-machine setup and initial credentials/pairing.
- **[Recovery guide](docs/WORKSTATION-RECOVERY.md)** — restore drills and workstation reconstruction.
- **[Repository audit](docs/REPOSITORY-AUDIT.md)** — configuration inspection and cleanup procedures.
- **[v1.2.0 release checklist](docs/v1.2.0-release-checklist.md)** — release acceptance checks.
- **[Ubuntu 26.04 compatibility notes](docs/ubuntu-26.04-compatibility.md)** — known platform quirk (`sudo-rs` vs Ansible).
- **[Public release audit](docs/PUBLIC-RELEASE-AUDIT.md)** — security, privacy and portability findings before publishing this repository.
- **[Security policy](SECURITY.md)** — how to report a vulnerability privately.
- **[Contributing](CONTRIBUTING.md)** — ground rules and validation workflow for proposed changes.

## Releases

| Release | Milestone |
| --- | --- |
| `v1.0.0` | Reproducible Ubuntu workstation baseline |
| `v1.1.0` | Automated security maintenance, health, drift, backups, weekly reports and failure notifications |
| **`v1.2.0`** | Development-tool update discovery, reviews, notifications and post-update validation |

To inspect the released revision:

```fish
cd ~/Projects/ubuntu-workstations
git describe --tags --always
git show --no-patch v1.2.0
git status --short
```

Create a new annotated version tag **only after** both target validation and Git synchronization pass. Don't retag a published release to incorporate later changes; use a new commit and follow-up version.

---

*Personal configuration repository, not a universal Ubuntu installer. Keep local identities and secrets separate, and adapt hardware-specific settings to each workstation.*
