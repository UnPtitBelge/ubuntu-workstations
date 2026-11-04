# Ubuntu workstation installation runbook

**Target:** Ubuntu Desktop 26.04 LTS, project `ubuntu-workstations`.  
**Scope:** first-time local provisioning and verification.  
**Safety:** review the role inventory before running it; the full playbook changes installed system packages and per-user desktop settings. This is a procedure, not a bootstrapping script.

## 0. Preconditions and repository choices

- Have a known-good, committed copy of the repository accessible via Git.
- Have your ordinary Linux user account created and logged into **GNOME on Wayland**. For existing configurations this is `matteo`, but use the actual login name on each machine. Do not blindly reuse an account name or an SSH identity.
- Connect to the network and make sure Ubuntu APT works.
- Have access to the Proton account and the intended Syncthing partner device (when available), but do not put credentials in Git.
- Back up any existing data **before** provisioning an already-used machine. Ansible is not a backup.
- Decide which inventory hostname to use: `laptop` on the existing machine; `desktop` only after it has an inventory entry.
- Preserve machine-specific display/scaling preferences, `/dev/kvm` availability, and local user session requirements.

## 1. Bootstrap Ubuntu (run on the **new** workstation)

Open Terminal in the logged-in desktop session. Commands below are **Fish-compatible** except the optional shell bootstrap command, which runs in Ubuntu's default shell prior to installing Fish.

```sh
sudo apt-get update
sudo apt-get install -y git ansible-core ca-certificates
```

Install prerequisites only; **do not manually install** all tools that the Ansible roles manage. In particular, avoid configuring GNOME themes or application caches by hand.

For the existing configuration, the repository lives here:

```fish
mkdir -p ~/Projects
cd ~/Projects
git clone YOUR-REPOSITORY-URL ubuntu-workstations
cd ~/Projects/ubuntu-workstations
```

Replace `YOUR-REPOSITORY-URL` with your actual Git remote. Do not paste private access tokens into a command line. If you already have the repository, use it rather than cloning over it.

## 2. Review inventory and variables before applying

```fish
cd ~/Projects/ubuntu-workstations/ansible
cat inventory/hosts.yml
ansible-inventory --graph
```

- Keep the existing laptop entry as-is on `Omnissiah-pocket`.
- For the new desktop, add its **actual** host entry and `inventory/host_vars/desktop.yml` from your template. Do not invent a hostname/IP now. For local provisioning the active host should use `ansible_connection: local` or the equivalent current inventory setting.
- Shared settings belong in `inventory/group_vars/all.yml`; actual machine differences belong in `inventory/host_vars/<inventory-name>.yml`.
- Confirm that `proton` precedes `backup`, and `hardware` precedes the roles which inspect its facts.
- **GNOME session guard:** Your `gnome` role is conditionally executed if `workstation_hardware_has_gnome_session` is true. Run provisioning from an active GNOME desktop session; verify the GNOME tasks were **not skipped** in the recap. An absent session should not be mistaken for a fully provisioned desktop.
- Check the backup timer and remote destination. Use the machine's actual host name, not a hard-coded laptop path. For a first run, set `workstation_backup_timer_enabled: false` until recovery has been tested.

## 3. Run provisioning locally

```fish
cd ~/Projects/ubuntu-workstations/ansible
ansible-playbook playbooks/workstation.yml --syntax-check
ansible-playbook playbooks/workstation.yml --check --diff -K --limit laptop
ansible-playbook playbooks/workstation.yml -K --limit laptop
```

On a new desktop replace `laptop` with `desktop` **only once it is present in the inventory**. Do not use `--limit laptop` from the desktop and inadvertently target the wrong inventory entry.

**Sudo note (Ubuntu 26.04):** If Ansible privilege escalation fails when APT works interactively, verify which `sudo` implementation is active. The original laptop needed the traditional sudo alternative rather than `sudo-rs`; inspect and deliberately select the appropriate alternative for the new install instead of bypassing escalation. Never grant passwordless sudo on a real workstation just to paper over this.

Some tasks download binaries from upstream sources; if a download fails with a transient TLS/EOF error, test the URL, retry once, and only then investigate networking. Avoid re-installing already healthy software.

## 4. Enable and inspect user services

Run checks from the **same logged-in user session** that Ansible configured:

```fish
systemctl --user is-active syncthing.service
systemctl --user is-enabled syncthing.service
systemctl --user status workstation-proton-backup.timer
```

- Syncthing should run with a **unique device identity per machine**. Never copy `~/.config/syncthing/` or Syncthing certificate/private-key files from another computer.
- Configure pairing through Syncthing's web UI at `http://127.0.0.1:8384` only after verifying each device ID.
- Sync only explicitly approved folders. Device pairing may create conflicts; resolve them before introducing bidirectional edits.
- The Proton backup timer may remain disabled initially by design. This is not a provisioning failure.

## 5. Authenticate Proton applications (manual; **not** Ansible)

```fish
proton-drive version
proton-drive auth login
proton-drive filesystem list /my-files
```

Sign into Proton VPN, Pass, and Mail interactively in their installed apps. Credentials, token stores, and GNOME Keyring contents stay on each machine. Do not commit them or synchronize them with Syncthing.

For Proton backups, precreate `/my-files/Workstation-Backups/<actual-hostname>` in Proton Drive and test the filtered backup script before enabling the timer:

```fish
~/.local/bin/workstation-proton-backup --show-excludes
~/.local/bin/workstation-proton-backup --dry-run
~/.local/bin/workstation-proton-backup
```

Review exclusions before running: virtual environments, build artifacts and caches should be omitted; code and important project data must remain included. Exclusions **do not** delete old remote files.

## 6. Verify and record the result

```fish
cd ~/Projects/ubuntu-workstations/ansible
ansible-playbook playbooks/validate-workstation.yml -e audit_enforce=true --limit laptop
ansible-playbook playbooks/workstation.yml -K --limit laptop
```

Use the new machine's inventory name in place of `laptop` when appropriate. Target `failed=0` and preferably `changed=0` on the second provisioning run. Check GNOME visuals (including Quick Settings and screenshot icons), Ctrl+Alt+T to open Ghostty, top-bar Resource Monitor, Docker, Multipass/QEMU, Syncthing and Proton apps. The headless VM rehearsal does **not** validate these graphical/session features.

Record the Git commit and the audit result in a personal installation log (without passwords or secrets). Commit only intentional configuration changes.

## 7. Optional: repeat the foundation rehearsal in Multipass

The VM rehearsal tests `base`, `shell`, `bootstrap` and `languages` only. Use `ansible/playbooks/rehearsal-headless.yml` and its existing Phase 24 README. Important lessons from our first rehearsal:

- Multipass often uses a Snap-private `/tmp`; transfer archives from a folder under `$HOME` instead (the Snap cannot read the host's `/tmp` either).
- Extract the archive into a **dedicated directory** (e.g. `mkdir -p ~/Projects/ubuntu-workstations && tar -xzf ... -C ~/Projects/ubuntu-workstations`); `git archive` tarballs have no top-level folder.
- The VM initially has an `ubuntu` user, **not** `matteo`. Prepare the account explicitly inside the disposable VM before trying `sudo -u matteo`.
- `git archive HEAD` contains **committed files only**; push/commit changes before archiving (or tar the working tree instead).
- The rehearsal playbook targets `hosts: all`, and in a single VM both inventory entries (`desktop`, `laptop`) share one `$HOME`. Run it with `--limit <one-host>` (or `-f 1`): with default parallelism, concurrent `rustup`/`mise` installs for the two "hosts" race on the same `~/.cargo`/`~/.rustup`/`~/.local` and can fail with partial-download rename errors.
- The headless test account may use disposable VM-only NOPASSWD sudo. **Never replicate this shortcut on the laptop or real desktop**.
- Run the same rehearsal twice to detect non-idempotent tasks; aim for `failed=0` and `changed=0` on the second run. A VM pass is not proof that desktop GNOME or Proton authentication works.
