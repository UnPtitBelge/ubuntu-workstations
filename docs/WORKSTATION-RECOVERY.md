# Ubuntu workstation recovery runbook

**Goal:** restore access to files and rebuild working software after disk failure, accidental deletion, or a failed upgrade. The recovery path intentionally separates **Git + Ansible** (machine configuration), **Syncthing** (replication) and **Proton Drive** (off-site file copies).

## 0. Protect existing evidence and data

1. Stop unnecessary writes to a disk that may be failing. If the problem looks physical, prioritize recovery of data; do not repeatedly reinstall packages on that disk.
2. Decide whether you're restoring an individual file or rebuilding the workstation. Prefer a **targeted file restore** to a full reinstall when possible.
3. Use a **separate restore directory**. Never restore on top of a still-working project until you've verified content and versions.
4. Check you can access the Git repository and Proton account on a trusted system. This runbook does not store recovery credentials.

## A. Recover accidentally deleted / overwritten files

### A1. If the file was in Syncthing

- Stop edits on other devices until you know which version is correct.
- Inspect Syncthing conflicts and the folder's `.stversions` directory when staggered versioning was enabled. The presence and retention of a prior version are **not guaranteed**.
- Restore to a separate temporary directory first, compare contents, then copy it back.
- Remember that Syncthing can propagate deletions across devices; it is not itself a complete backup.

### A2. If the file was in Proton Drive

Check your active CLI session:

```fish
proton-drive filesystem list /my-files
```

Identify the computer-specific destination (the remote name follows the actual hostname used for the backup):

```fish
hostname
proton-drive filesystem list /my-files/Workstation-Backups
```

Create a local recovery location:

```fish
set restore_dir (mktemp -d "$HOME/proton-restore.XXXXXXXX")
echo $restore_dir
```

Then download the affected folder to the separate location, e.g. replacing `<backup-hostname>` as needed:

```fish
proton-drive filesystem download \
  /my-files/Workstation-Backups/<backup-hostname>/Documents \
  $restore_dir
```

Inspect the recovered files and compare selected originals:

```fish
find $restore_dir -maxdepth 3 -type f | head -50
```

If the source file still exists, compare it to the recovered version using `cmp` or `sha256sum`. If you need an older revision, inspect Proton Drive's file version history in the web interface; do not assume the CLI always downloads a historical version.

**Filtered-backup caveats:** The backup excluded Python virtual environments, generated build outputs, caches and other ignored patterns. It cannot restore files never uploaded. The backup is folder-based with file revisions—not an immutable point-in-time snapshot. Before rebuilding a complex project, confirm that its actual source and lockfiles were included.

## B. Rebuild a workstation after reinstall or disk replacement

1. Install a clean, supported Ubuntu Desktop release (this project currently targets **26.04 LTS**).
2. Create and sign into your own desktop user account; verify network access and APT.
3. Follow `docs/WORKSTATION-INSTALL.md` to install Git/Ansible, retrieve the repository, inspect inventory and provision locally.
4. Sign into Proton services **manually** and pair Syncthing as a new device. A reinstalled machine gets a **new Syncthing device identity** unless you deliberately restored that identity from a secure backup—which this project does not assume or automate.
5. Restore only desired documents, notes and other protected data from Proton Drive to separate locations. Inspect before replacing local files. Re-clone or fetch development repositories from their Git remotes; use Proton backups to recover any unpushed work if it was included.
6. Re-run the strict validation audit. Then run provisioning a second time to check idempotency.
7. Verify the Proton backup script and its exclusions before enabling automatic backups on the rebuilt machine.

**What Ansible does not restore:** Authenticated Proton sessions, Syncthing private identities, SSH keys, passwords, live Docker volumes, VM disks and any paths not included in Proton backups. Recreate those explicitly or recover them through separate protected processes.

## C. Verify scheduled Proton backups are genuinely usable

A timer being active is **not** proof that Proton Drive authentication or backup uploading works.

```fish
systemctl --user list-timers workstation-proton-backup.timer
journalctl --user -u workstation-proton-backup.service -n 100 --no-pager
```

Test manual and service-context runs independently:

```fish
~/.local/bin/workstation-proton-backup --dry-run
systemctl --user start workstation-proton-backup.service
journalctl --user -u workstation-proton-backup.service -n 100 --no-pager
```

Check whether the service actually succeeded and verify remote files. An unattended user service can fail to unlock the same GNOME Keyring session that an interactive shell uses. Fix that authentication context explicitly; do not embed Proton credentials in systemd units or Git.

To enable the timer **after a successful backup and restore**, set `workstation_backup_timer_enabled: true` in the appropriate inventory variables and rerun provisioning. Verify the resulting timer and a real scheduled run.

**Automated restore drills:** every backup provider deploys a monthly `workstation-*-backup-restore-test.timer` that downloads one random small backed-up file to a separate temp directory and compares its SHA-256 with the local source (read-only on the remote — it never overwrites or deletes anything). Results are dated in `~/.local/state/workstation-backup/restore-tests.jsonl` and summarized in `status.json` (`verified_restore_at`) and the backup monitor report (`Last verified restore`). Manual drill: `~/.local/bin/workstation-proton-backup-restore-test` (or `workstation-rclone-backup-restore-test`). Every backup run also uploads a per-file SHA-256 `manifest.json` next to the dataset (local copy: `manifest-latest.json`) — compare counts/checksums with it instead of trusting remote UI totals.

## D. Ongoing recovery exercises

- Monthly: the automated restore drill covers one random file; the backup monitor alerts if `verified_restore_at` is older than `workstation_backup_monitor_restore_max_age_hours`. Quarterly, additionally restore a chosen file manually to a temporary directory, verify it opens, and inspect the backup logs.
- After significant role changes: rerun `validate-workstation.yml` and test second-run idempotency.
- After major OS upgrades: test a new disposable VM rehearsal before changing the laptop.
- Before deleting obsolete cloud backups: ensure you have verified replacement copies. Exclusion rules prevent *future* uploads; they do not reclaim old Proton Drive storage automatically.
- Keep recovery credentials in a trusted password manager and confirm you can access them after losing the laptop. Avoid treating a password manager session on the failed laptop as your only recovery path.

## E. Important limitations

- One Proton account is a single failure domain: account lockout, cloud-side deletion and retention policy can affect all its backups.
- Syncthing versioning and Proton Drive revisions complement backups but don't replace independently retained snapshots.
- Dev environment caches can be recreated. Source code, lockfiles, documents, and unpushed Git commits cannot always be recreated; audit backup coverage accordingly.
- If the old Restic role was briefly extracted or deployed, its old password or repository files may still exist locally. They are **not** used by the Proton backup role. Review manually before deleting anything.
