# Ubuntu Workstations — Routine Maintenance Checklist

**For:** `my-desktop` and `my-laptop` · **Starting point:** v1.2.x
**Operating principle:** Let timers do the ordinary work. Investigate alerts; do not manually run every checker every day.

## ✅ Always-on automation (no manual action when healthy)

| System | Expected automatic behavior | If it alerts |
|---|---|---|
| Ubuntu security updates | Daily APT checks and eligible security upgrades; no auto reboot | Review unattended-upgrades logs and pending reboot |
| Proton Drive backup | Scheduled user-service upload (per-host destination) | Inspect backup service journal and authentication |
| System health | Daily checks for services, disk capacity, APT timers, reboot requirement | Inspect `workstation-health/latest.txt` |
| Drift detection | Daily checks of selected Ansible-managed files | Inspect named paths before regenerating the baseline |
| Backup health | Daily service success / backup-age check | Verify the latest genuine backup completed |
| Weekly consolidated report | Report generated each Sunday | Resolve unhealthy/missing/stale underlying reports |
| GNOME failure alerts | Periodic notifications only when attention is required | Check the relevant report and systemd journal |
| Tool update discovery | Weekly version/candidate check | Review update candidates, do not blindly install |
| Tool update alerts | Notify when relevant updates are reported | Plan a controlled update window |
| Post-update validation | Watches package changes with a periodic fallback | Inspect validator report and affected service |

> Timers can be active while **a service's last execution failed**. Check journals and report outcomes, not only `is-active`. GNOME notification delivery requires a signed-in graphical session. Keep `Linger=yes` so systemd user jobs can operate when logged out; validate Proton authentication separately.

## Daily — only if you received an alert (2–5 minutes)

- [ ] Open the notification or report; identify which subsystem failed.
- [ ] Read that subsystem's `latest.txt` and check its timestamp.
- [ ] Inspect recent logs for the named service rather than restarting everything.
- [ ] Distinguish a failed backup from a stale monitoring report; do not reset success timestamps.
- [ ] If repairs are needed, prefer targeted changes to Ansible configuration and rerun validation.

```fish
cat ~/.local/state/workstation-weekly-report/latest.txt
systemctl --user --failed --no-pager
journalctl --user -u workstation-proton-backup.service -n 60 --no-pager
```

## Weekly — 5 minutes, preferably after the Sunday report

- [ ] Review the weekly consolidated report on **both** machines (or only the machine you are using that week; confirm the other later).
- [ ] Confirm that the latest Proton backup really succeeded and is recent; check the last-success timestamp.
- [ ] Review any available Node/mise, Docker or Proton updates; defer unapproved upgrades.
- [ ] Look for failed user/system units and any pending reboot.
- [ ] Check Git for uncommitted workstation changes.

```fish
cat ~/.local/state/workstation-weekly-report/latest.txt
stat -c '%y %n' ~/.local/state/workstation-backup-monitor/last-success
~/.local/bin/workstation-apt-update-review --group docker --plan
~/.local/bin/workstation-apt-update-review --group proton --plan
systemctl --user --failed --no-pager
systemctl --failed --no-pager
cd ~/Projects/ubuntu-workstations; git status --short
```

**Expected result:** no unexplained failures, backup within its configured freshness window (currently 48h), and reviewed rather than surprise updates.

## Monthly — 10–20 minutes

- [ ] Compare Git revision on desktop and laptop; deploy approved config changes to the secondary machine.
- [ ] Run strict Ansible validation on both machines.
- [ ] Verify monitoring units remain enabled and timers have future runs.
- [ ] Review filesystem capacity and Docker disk usage **without pruning**.
- [ ] Confirm Syncthing connects and syncs in both directions.
- [ ] Review pending reboot status and restart at a convenient time if required.
- [ ] Confirm backup destinations remain machine-specific (`my-desktop` vs `my-laptop`).

```fish
# On the machine you are checking, set the matching host first:
set target desktop  # On my-laptop: set target laptop
cd ~/Projects/ubuntu-workstations

git describe --tags --always
git status --short
cd ansible
ansible-playbook playbooks/validate-workstation.yml -e audit_enforce=true --limit $target

systemctl --user list-timers --all | grep workstation
loginctl show-user (whoami) -p Linger
df -h / /home
docker system df
```

**Do not** interpret `docker system df` as a request to delete images or volumes. Investigate before any cleanup.

## Monthly — restore verification (2 minutes; the drill is automated, you verify it ran)

- [ ] Confirm the monthly restore drill succeeded: `~/.local/bin/workstation-backup-health-check` shows a fresh `Last verified restore`, or `tail -1 ~/.local/state/workstation-backup/restore-tests.jsonl` shows `"result":"success"` this month.
- [ ] Run the self-tests once after any monitoring change: `~/.local/bin/workstation-desktop-alerts --self-test` and `~/.local/bin/workstation-post-update-validate --self-test` (both must print `SELF-TEST PASSED`).
- [ ] Run a read-only provider preflight if you plan any provider change: `cd ~/Projects/ubuntu-workstations/ansible; ansible-playbook playbooks/provider-preflight.yml --limit <host>`.

## Quarterly — recovery drill (20–45 minutes)

- [ ] **Restore test:** the monthly drill covers one random file automatically; additionally restore at least one real file into a separate temporary directory and compare its contents to the original (`cmp`), e.g. `~/.local/bin/workstation-proton-backup-restore-test` (read-only on the remote).
- [ ] Verify the restored file belongs to the **correct machine's** backup destination.
- [ ] Compare the local manifest against the dataset: `jq '{file_count, total_bytes}' ~/.local/state/workstation-backup/manifest-latest.json`.
- [ ] **Sync test:** create a harmless file in the shared Syncthing folder on one device; confirm arrival on the other, then remove it after both show Up to Date.
- [ ] Confirm the cloud sign-in still works for scheduled backups without opening a terminal or entering credentials interactively.
- [ ] Validate a login/reboot cycle: user timers return, and the GNOME alert works **both in a logged-in session and after logout/login** (manual check — lingering alone does not prove delivery): `~/.local/bin/workstation-desktop-alerts --test-notification` after each login.
- [ ] Read repository recovery instructions; verify access to Git and provider credentials/recovery material **without storing secrets in the repository**.

```fish
# On the machine where both restored and source files are present:
cmp /path/to/original /path/to/restored-copy

# Inspect backup history without starting an upload:
journalctl --user -u workstation-proton-backup.service --since '90 days ago' --no-pager
tail -5 ~/.local/state/workstation-backup/history.jsonl

# Test graphical notification (while logged into GNOME):
~/.local/bin/workstation-desktop-alerts --test-notification
```

**Success means an actual restored file is usable.** A timer marked `active` and a `last-success` timestamp alone do not prove recoverability.

## Whenever you change Ansible, packages, or versions

- [ ] Confirm the correct target (`desktop` or `laptop`) and check Git status.
- [ ] Review the patch for credentials and unexpected modifications.
- [ ] Run syntax check, then `--check --diff` if useful.
- [ ] Run provisioning on the **target machine**; inspect the recap and first failure.
- [ ] Run strict validation and inspect monitoring reports if a monitored file changed.
- [ ] Rerun provisioning to verify idempotency (`changed=0` is the goal).
- [ ] Commit a focused change and push; pull/validate on the other workstation when appropriate.

```fish
set target desktop  # On laptop, change to laptop
cd ~/Projects/ubuntu-workstations/ansible
ansible-playbook playbooks/workstation.yml --syntax-check
and ansible-playbook playbooks/workstation.yml --check --diff -K --limit $target
# After reviewing the preview:
ansible-playbook playbooks/workstation.yml -K --limit $target
and ansible-playbook playbooks/validate-workstation.yml -e audit_enforce=true --limit $target
and ansible-playbook playbooks/workstation.yml -K --limit $target
```

## Release checklist — before each Git tag

- [ ] Desktop strict validation passes.
- [ ] Laptop strict validation passes after approved deployment (if possible).
- [ ] Monitoring and backup reports are healthy or documented with known exceptions.
- [ ] Restore drill has passed recently.
- [ ] No unexplained errors in `systemctl --user --failed` / `systemctl --failed`.
- [ ] Git tree is clean; all expected changes are committed and pushed.
- [ ] `HEAD` and `origin/main` agree; the desired tag does not already exist.
- [ ] Create an annotated tag **only then**, and verify the remote tag.

```fish
cd ~/Projects/ubuntu-workstations
git fetch origin
git status --short
git rev-list --left-right --count origin/main...HEAD
git tag --list 'v*'
```

## Escalation rules

**Act promptly:** backup failures/old backups, Docker unavailable when needed, Syncthing disconnected for an extended period, disk near full, security-update failures, or detected drift in security-sensitive config.

**Can be planned:** newer Docker/Proton package candidate, minor tool version proposal, optional restart when no critical security urgency.

**Never automate without review:** deleting Docker volumes, changing Proton backup destinations, overwriting restored data, `mise` major upgrades, or accepting a new drift baseline as proof the original change was authorized.

---

**Fast reference:** [Command Cheatsheet](WORKSTATION-CHEATSHEET.md). All schedule and retention thresholds should ultimately be read from the active Ansible roles/host variables rather than treated as universal defaults.
