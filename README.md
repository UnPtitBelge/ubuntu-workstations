# Ubuntu Workstations

**One Git repository. One Ansible configuration. Reproducible Ubuntu workstations.**

An opinionated, personal workstation setup for **Ubuntu Desktop 26.04 LTS**, built with **Ansible + Git**. The goal is to give a laptop and a future desktop the same development environment and GNOME experience while keeping machine-specific hardware, device identities, and credentials separate.

> **Status:** Stable baseline candidate (`v1.0.0`). Tag the repository only after confirming the final checks on your machine. The existing laptop inventory host is `laptop` (`Omnissiah-pocket`); a future `desktop` host can be added when that machine exists.

## What it manages

| Area | Components |
| --- | --- |
| Desktop | GNOME 50, Yaru Blue Dark, wallpaper, Ubuntu Dock, shortcuts, Resource Monitor |
| Shell | Fish, Ghostty, Starship, zoxide, shell configuration |
| Development | Git and base tooling, mise, Node.js, Java, uv/Python, rustup/Rust |
| Containers | Docker Engine, Compose, Buildx, Containerlab |
| Virtualization | QEMU and Multipass; hardware/KVM detection |
| Synchronization | Syncthing user service and a selected shared directory |
| Proton | Drive CLI, Pass, Mail; existing VPN configuration is preserved |
| Backups | Filtered Proton Drive file uploads, file revisions, optional user timer |
| Quality | Read-only health checks, clean-install rehearsal, repository audit |

The configuration is intentionally **not** a complete disk image. It installs software and applies selected settings; user logins, encryption keys, Proton sessions, Syncthing device pairing, monitor arrangements, and files outside the configured backups need separate handling.

## Repository layout

```text
.
├── ansible/
│   ├── ansible.cfg
│   ├── inventory/
│   │   ├── hosts.yml
│   │   ├── group_vars/all.yml
│   │   └── host_vars/
│   │       ├── laptop.yml
│   │       └── desktop.yml.example
│   ├── playbooks/
│   │   ├── workstation.yml             # Main provisioning
│   │   ├── validate-workstation.yml    # Read-only health audit
│   │   └── rehearsal-headless.yml      # Disposable VM foundation test
│   └── roles/
│       ├── backup/
│       ├── base/
│       ├── bootstrap/
│       ├── containers/
│       ├── gnome/
│       ├── hardware/
│       ├── languages/
│       ├── proton/
│       ├── shell/
│       ├── syncthing/
│       └── virtualization/
├── assets/                              # Versioned appearance assets, if configured
├── docs/
│   ├── WORKSTATION-INSTALL.md
│   ├── WORKSTATION-RECOVERY.md
│   └── REPOSITORY-AUDIT.md
└── scripts/audit-workstation.py
```

**Shared settings** live in role defaults and `ansible/inventory/group_vars/all.yml`. **Machine-specific overrides** belong in `ansible/inventory/host_vars/`. The laptop is the reference configuration; avoid duplicating shared values in individual host files.

## Quick start: provision a workstation

> Run on the **target machine**, while logged into its normal **GNOME desktop session**. The commands below are compatible with Fish. Ubuntu's default shell also accepts these particular commands.

### 1. Bootstrap

```sh
sudo apt-get update
sudo apt-get install -y git ansible-core ca-certificates
```

Clone your own repository (replace the placeholder with its real URL):

```sh
mkdir -p ~/Projects
cd ~/Projects
git clone <YOUR_GIT_REMOTE_URL> ubuntu-workstations
cd ubuntu-workstations/ansible
```

If you already have the repository, **do not clone over it**. Review its status and update it through your normal Git workflow.

### 2. Select the inventory host

```sh
ansible-inventory --graph
ansible-inventory --host laptop
```

Use `laptop` only on the laptop. For a new desktop, add its **real** inventory entry and copy the host-variable example to `host_vars/desktop.yml`, adjusting only settings that genuinely differ. Confirm that local provisioning points to the **current machine** (`ansible_connection: local`, or the equivalent in the existing inventory) before proceeding.

### 3. Validate, preview, apply

```sh
ansible-playbook playbooks/workstation.yml --syntax-check
ansible-playbook playbooks/workstation.yml --check --diff -K --limit laptop
ansible-playbook playbooks/workstation.yml -K --limit laptop
```

Replace `laptop` with `desktop` **only after** adding the desktop inventory entry. Review the proposed changes before applying to an existing installation. The GNOME role requires an active GNOME session; a skipped GNOME role is **not** proof the desktop is configured.

**Ubuntu 26.04 sudo note:** On the reference laptop, Ansible privilege escalation required selecting traditional `sudo` instead of the default `sudo-rs` alternative. If `-K` fails unexpectedly, inspect the system's configured sudo alternative rather than weakening permissions.

### 4. Verify and check idempotency

```sh
ansible-playbook playbooks/validate-workstation.yml -e audit_enforce=true --limit laptop
ansible-playbook playbooks/workstation.yml -K --limit laptop
```

On a stable machine, aim for `failed=0` and **`changed=0` on the second provisioning run**. Some operations require logging out and back into GNOME before visual changes are visible.

## User services and first-time setup

Ansible manages packages and service definitions, but it deliberately **does not copy machine identities or log in to personal accounts**.

### Syncthing

Syncthing runs as a **systemd user service**. Inspect it with:

```sh
systemctl --user status syncthing.service
```

Open the local interface at <http://127.0.0.1:8384> to pair devices and approve shared folders. Each workstation must retain its **own Syncthing identity**. The configured `~/Sync` workspace and staggered file versioning complement backups; synchronization alone is **not** a backup.

### Proton

The Proton role manages the **Drive CLI, Pass, and Mail**. The already-working **VPN installation is intentionally left untouched**. Authenticate applications interactively on each machine; do not put account tokens, passwords, or keyring contents in Git.

```sh
proton-drive version
proton-drive auth login
proton-drive filesystem list /my-files
```

### Proton Drive backups

The backup role sends selected data (initially `~/Documents` and `~/Sync`) to the machine-specific path:

```text
/my-files/Workstation-Backups/<actual-hostname>/
```

The **remote parent folder must already exist**. Backups exclude common development caches and generated content, including Python virtual environments, Node dependencies and build products. Review the exact ignore patterns in `ansible/roles/backup/defaults/main.yml`; important generated outputs may require an exception.

```sh
~/.local/bin/workstation-proton-backup --show-excludes
~/.local/bin/workstation-proton-backup --dry-run
~/.local/bin/workstation-proton-backup
```

**Before enabling the daily timer**, complete a successful manual backup **and restore a sample file into a separate location**. The script uses Proton Drive's file-revision strategy, **not immutable or point-in-time snapshots**; old remote files are not automatically deleted when new exclusions are added.

To inspect scheduling and its logs:

```sh
systemctl --user status workstation-proton-backup.timer
journalctl --user -u workstation-proton-backup.service -n 50 --no-pager
```

The timer is disabled by default in role defaults; enable it through your inventory after a successful restore test. Test a systemd-service-triggered backup too: keyring access can differ from an interactive terminal session. A timer being active does **not** prove backups are succeeding.

## Development and design principles

- **Preserve working state.** Audit first; apply focused changes; validate; commit.
- **Idempotency matters.** A second Ansible run should make no unnecessary changes.
- **Single source of truth.** Git and Ansible for configuration; Syncthing for approved shared files; Proton Drive for off-site file copies.
- **User context matters.** GNOME settings and systemd user services generally require a live user session and its D-Bus environment.
- **No secrets in Git.** Keep SSH keys, Syncthing certificates, Proton sessions and backup credentials machine-local or in appropriate secure storage.
- **Hardware differs.** Graphics/display layout, CPU architecture and KVM access are detected or handled per machine.
- **Prefer tested packages and pinned releases.** Don't automatically reinstall or replace working GNOME components to enforce cosmetic settings.

## Tests and diagnostics

Run the repository audit from the root:

```sh
python3 scripts/audit-workstation.py .
```

This is **read-only**. References to legacy Restic in the backup role are intentional migration cleanup; the active backup backend is Proton Drive. Multiple variable definitions across role defaults and host variables can also be intentional overrides.

The headless rehearsal playbook (`ansible/playbooks/rehearsal-headless.yml`) tests foundation provisioning in a disposable Multipass VM. **It does not validate GNOME visuals, Proton authentication, or user-session services.** See the installation guide for VM preparation and account-creation precautions.

## Recovery and documentation

- **[Fresh installation](docs/WORKSTATION-INSTALL.md)** — bootstrap Ubuntu, choose inventory, provision, validate.
- **[Recovery](docs/WORKSTATION-RECOVERY.md)** — restore selected files, rebuild a workstation, and test backup recoverability.
- **[Repository audit](docs/REPOSITORY-AUDIT.md)** — audit findings and safe cleanup procedures.

Syncthing and Proton Drive backups do **not** cover every file or disaster scenario. They do not reconstruct VM disks, live Docker volumes, excluded caches, private SSH keys or authenticated application sessions. Keep your Git remote and Proton account recovery methods accessible independently of the laptop.

## Releases

The intended first stable baseline is **`v1.0.0`**. Once the strict health audit passes, provisioning is idempotent and all intended changes are committed, create an annotated tag:

```sh
git status --short
git tag -a v1.0.0 -m "Ubuntu Workstations v1.0.0 - stable baseline"
git show v1.0.0 --no-patch
```

If the tag already exists, **inspect it instead of recreating it**. Push only to your verified Git remote, if configured:

```sh
git remote -v
git push origin main
git push origin v1.0.0
```

This is a **personal configuration repository**, not a universal Ubuntu installer. Adapt inventory, paths and optional services to the target workstation before running it.
