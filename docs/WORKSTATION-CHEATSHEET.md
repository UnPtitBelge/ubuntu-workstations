# Ubuntu Workstations — Command Cheatsheet

**Applies to:** `Omnissiah-desktop` (inventory host `desktop`) and `Omnissiah-pocket` (`laptop`)  
**Baseline:** Ubuntu 26.04 LTS · Fish shell · Ansible + Git · v1.2.x  
**Repository:** `~/Projects/ubuntu-workstations`  
**Rule:** Run Ansible **on the machine being configured**; `--limit` must match that machine. Commands below are Fish-compatible.

> **Legend:** 🔎 read-only · 🛠️ changes local configuration · ☁️ changes remote Git / starts a real backup. Never assume `--check` is equivalent to a real deployment.

## 1. Daily essentials

| Task | Command | Effect |
|---|---|---|
| Go to repository | `cd ~/Projects/ubuntu-workstations` | 🔎 |
| Working tree | `git status --short` | 🔎 |
| Current release | `git describe --tags --always` | 🔎 |
| See last commits | `git log -5 --oneline` | 🔎 |
| Weekly report | `cat ~/.local/state/workstation-weekly-report/latest.txt` | 🔎 |
| Full release audit | `~/.local/bin/workstation-release-audit` | 🔎 (writes a local report) |
| Active maintenance timers | `systemctl --user list-timers --all | grep workstation` | 🔎 |
| Failed user units | `systemctl --user --failed --no-pager` | 🔎 |
| Failed system units | `systemctl --failed --no-pager` | 🔎 |

## 2. Update the Ansible repository and deploy

Choose **one** target, on the relevant machine:

```fish
# On Omnissiah-desktop:
set target desktop

# On Omnissiah-pocket, use instead:
# set target laptop

cd ~/Projects/ubuntu-workstations

# Do not pull over local uncommitted changes.
git status --short
git pull --ff-only

cd ansible
ansible-playbook playbooks/workstation.yml --syntax-check
and ansible-playbook playbooks/workstation.yml --check --diff -K --limit $target
# Review the preview; only then apply:
ansible-playbook playbooks/workstation.yml -K --limit $target
and ansible-playbook playbooks/validate-workstation.yml -e audit_enforce=true --limit $target
```

**Idempotency check** (run a *second* time after successful deployment):

```fish
cd ~/Projects/ubuntu-workstations/ansible
ansible-playbook playbooks/workstation.yml -K --limit desktop
# On laptop: replace desktop with laptop.
# Aim for failed=0 and changed=0.
```

**Inventory / role discovery:**

```fish
cd ~/Projects/ubuntu-workstations/ansible
ansible-inventory -i inventory/hosts.yml --graph
ansible-playbook playbooks/workstation.yml --list-tasks --limit desktop
```

## 3. Monitoring: run now and read reports

These probes do not repair services or install updates. They may update their own local report files.

| Subsystem | Run check | Saved report |
|---|---|---|
| System health | `~/.local/bin/workstation-health-check` | `~/.local/state/workstation-health/latest.txt` |
| Selected-file drift | `~/.local/bin/workstation-drift-check` | `~/.local/state/workstation-drift/latest.txt` |
| Proton backup health | `~/.local/bin/workstation-backup-health-check` | `~/.local/state/workstation-backup-monitor/latest.txt` |
| Weekly consolidation | `~/.local/bin/workstation-weekly-report` | `~/.local/state/workstation-weekly-report/latest.txt` |
| Tool update discovery | `~/.local/bin/workstation-tool-update-check` | `~/.local/state/workstation-tool-updates/latest.txt` |
| Release readiness | `~/.local/bin/workstation-release-audit` | `~/.local/state/workstation-release-audit/latest.txt` |
| GNOME failures (preview) | `~/.local/bin/workstation-desktop-alerts --dry-run` | Prints planned alert actions |
| Tool-update alerts (preview) | `~/.local/bin/workstation-tool-update-alerts --dry-run` | Prints planned alert actions |

**Quick read without rerunning a check:**

```fish
for name in workstation-health workstation-drift workstation-backup-monitor workstation-weekly-report workstation-tool-updates workstation-release-audit
    set f ~/.local/state/$name/latest.txt
    if test -f $f
        echo "=== $name ==="
        stat -c '%y %n' $f
        tail -n 4 $f
    else
        echo "MISSING: $f"
    end
end
```

> Drift detection covers **selected managed files**, not the entire machine. Rerunning Ansible can regenerate its baseline. A healthy backup-monitor report is **not** a substitute for restoring a file.

## 4. systemd and logs

```fish
# User timers (backup, monitors, reports, notifications)
systemctl --user list-timers --all

# Security update timers (system units)
systemctl list-timers apt-daily.timer apt-daily-upgrade.timer

# Verify linger survives logout/reboot
loginctl show-user (whoami) -p Linger

# Check any unit: replace the name
systemctl --user status workstation-proton-backup.timer --no-pager
journalctl --user -u workstation-proton-backup.service -n 80 --no-pager
journalctl --user -u workstation-desktop-alerts.service -n 80 --no-pager

# Check unexpected failures
systemctl --user --failed --no-pager
systemctl --failed --no-pager
```

**Known user unit names:** `workstation-proton-backup.timer` (+ `workstation-proton-backup-restore-test.timer`; `workstation-rclone-backup.*` for the `google/drive` provider), `workstation-health.timer`, `workstation-drift.timer`, `workstation-backup-health.timer`, `workstation-weekly-report.timer`, `workstation-desktop-alerts.timer`, `workstation-tool-update-check.timer`, `workstation-tool-update-alerts.timer`, `workstation-post-update-validation.timer`, and `workstation-post-update-validation.path` (the last is a path unit, not a timer).

**Safe notification tests:**

```fish
~/.local/bin/workstation-desktop-alerts --test-notification
~/.local/bin/workstation-desktop-alerts --dry-run --test-post-update-failure
~/.local/bin/workstation-tool-update-alerts --test-notification
```

GNOME notifications require an active graphical session, even with lingering enabled.

## 5. Backups and synchronization

```fish
# Scheduled backup and its last service result
systemctl --user is-enabled workstation-proton-backup.timer
systemctl --user is-active workstation-proton-backup.timer
systemctl --user show workstation-proton-backup.service -p Result -p ExecMainStatus

# Last recorded successful service run
stat ~/.local/state/workstation-backup-monitor/last-success

# Backup health without uploading again (shows last run, restore verification, manifest stats)
~/.local/bin/workstation-backup-health-check
journalctl --user -u workstation-proton-backup.service -n 80 --no-pager

# Restore drill (read-only on the remote: downloads ONE small file to a temp dir and compares SHA-256)
~/.local/bin/workstation-proton-backup-restore-test        # proton/drive; workstation-rclone-backup-restore-test for google/drive
systemctl --user status workstation-proton-backup-restore-test.timer --no-pager
cat ~/.local/state/workstation-backup/restore-tests.jsonl  # dated drill results
jq . ~/.local/state/workstation-backup/status.json          # verified_restore_at, files, bytes
jq . ~/.local/state/workstation-backup/manifest-latest.json  # per-file SHA-256 of the last backup
tail -3 ~/.local/state/workstation-backup/history.jsonl     # append-only run history (side-by-side safe)

# Drift: see what changed, acknowledge a deliberate out-of-band edit
~/.local/bin/workstation-drift-check
~/.local/bin/workstation-drift-ack --list
~/.local/bin/workstation-drift-ack "Health check systemd timer"   # mark accepted (still visible as [ACCEPTED])
cat ~/.local/state/workstation-drift/baseline-updates.jsonl        # provisioning re-baselines (never silent)

# Alert/validation self-tests (no real notification sent, nothing real is modified)
~/.local/bin/workstation-desktop-alerts --self-test
~/.local/bin/workstation-post-update-validate --self-test

# Read-only provider preflight inventory (migration stage A; report in ~/.local/state/workstation-migration/)
cd ~/Projects/ubuntu-workstations/ansible
ansible-playbook playbooks/provider-preflight.yml --limit desktop

# Proton Drive login/access (requires an authenticated session)
proton-drive filesystem list /my-files

# Syncthing user service
systemctl --user is-active syncthing.service
systemctl --user status syncthing.service --no-pager
```

Syncthing GUI: <http://127.0.0.1:8384>. Check both devices show **Up to Date**. Each machine must have its **own** backup destination (derived from its declared `workstation_device_name`). The monthly restore drill (`workstation-*-backup-restore-test.timer`) already downloads one random backed-up file to a separate temp dir and compares SHA-256; for a manual test you can run `~/.local/bin/workstation-proton-backup-restore-test` or download a known file with your CLI workflow and `cmp original restored`. **Do not overwrite the source file to test a restore.**

> 🛠️ `systemctl --user start workstation-proton-backup.service` starts a **real backup upload**. Use it intentionally, not as a routine health probe.

## 6. Development tools and package updates

```fish
# Versions and configuration
mise ls
mise config ls
node --version
rustc --version
rustup check
uv --version
java -version

# Read-only update review
~/.local/bin/workstation-tool-update-check
~/.local/bin/workstation-tool-update-policy
~/.local/bin/workstation-apt-update-review --group docker --plan
~/.local/bin/workstation-apt-update-review --group proton --plan

# Post-update probes; --watch checks only if monitored versions changed
~/.local/bin/workstation-post-update-validate --watch
~/.local/bin/workstation-post-update-validate --check docker
~/.local/bin/workstation-post-update-validate --check proton

# Docker essentials
docker info
docker ps
docker compose ls
docker compose version
docker buildx version
```

APT simulations and version checks **do not authorize an upgrade**. Review the exact package set and service impacts before updating Docker or Proton. Keep approved mise version pins in Ansible/Git. Avoid unattended `mise upgrade`, `rustup update`, or unreviewed `apt upgrade`.

## 7. Ubuntu security updates

```fish
apt-config dump | grep -E 'APT::Periodic::|Unattended-Upgrade::(Allowed-Origins|Automatic-Reboot)'
systemctl list-timers apt-daily.timer apt-daily-upgrade.timer
sudo unattended-upgrade --dry-run --debug
sudo tail -n 50 /var/log/unattended-upgrades/unattended-upgrades.log

test -e /var/run/reboot-required; and echo 'Reboot required'; or echo 'No reboot pending'
```

Unattended security upgrades are enabled, but **automatic reboot is disabled**. Docker/Proton third-party packages are not automatically upgraded by the security-update policy.

## 8. Git: review, push, release

```fish
cd ~/Projects/ubuntu-workstations

git status --short
git diff --check
git diff --stat

# Stage only reviewed changes (example: docs)
git add docs/WORKSTATION-CHEATSHEET.md docs/WORKSTATION-ROUTINE-CHECKLIST.md
git diff --cached --check
git diff --cached --stat

# Commit only after inspecting the staged changes
git commit -m 'docs: add workstation command and routine guides'
and git push origin main
```

**Tagging is a separate release decision**, not a routine maintenance operation. Confirm a clean tree, validated workstation, current branch `main` and synchronized `origin/main` before creating/pushing an annotated version tag.

## 9. First response when something breaks

| Symptom | First useful checks |
|---|---|
| Docker permission denied | `id -nG`; `getent group docker`; `ls -l /var/run/docker.sock` (group membership may require a fresh login) |
| Docker daemon unavailable | `systemctl is-active docker`; `journalctl -u docker -n 80 --no-pager` |
| Backup stale/failed | `workstation-backup-health-check`; `journalctl --user -u workstation-proton-backup.service -n 80 --no-pager` |
| User timer inactive | `systemctl --user status <unit> --no-pager`; `loginctl show-user (whoami) -p Linger` |
| Drift alert | `workstation-drift-check`; compare the named file with its Ansible-managed source before redeployment |
| Tool reverted/reinstalled | `mise ls`; `mise config ls`; `rg -n '<tool-name>' ansible ~/.config/mise` |
| Ansible failed | Capture the **first** failed task and source file; check `--syntax-check`, inventory target, and host variable overrides |
| GNOME alert absent | Test while logged into GNOME; check `notify-send`, alert service journal and timer |

**Avoid:** `chmod 666 /var/run/docker.sock`, resetting your Proton session, indiscriminate Docker pruning, automatically clearing drift baselines, or broad Ansible rewrites to repair a single failed task.

---

**See also:** [Routine Checklist](WORKSTATION-ROUTINE-CHECKLIST.md) · `docs/v1.2.0-release-checklist.md` · repository installation/recovery docs.
