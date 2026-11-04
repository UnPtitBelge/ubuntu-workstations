# Maintenance release v1.0.1 — proposed

> Historical record; these instructions are not the current deployment procedure. Use [DEPLOY](../DEPLOY.md) and the [routine checklist](../WORKSTATION-ROUTINE-CHECKLIST.md).

The one-off `scripts/patch-backup-disable.py` has been removed: its fix is already part of `ansible/roles/providers/proton/drive/tasks/main.yml`. The commands below describe the original proposal and must not be followed on the current tree.

This is a focused maintenance patch for the Phase 23 Proton Drive backup role. It is based on the previously supplied role, **not an inspection of the latest checkout**.

## Bug fixed

Previously, `workstation_backup_enabled: false` skipped the timer-management task. A timer enabled on an earlier run could therefore continue scheduling backups. The patch checks for the existing user timer unit and stops/disables it when backups are disabled. Normal `workstation_backup_enabled: true` behavior is unchanged. The patch does not delete Proton Drive content or credentials.

## Apply carefully

1. Inspect the existing role and confirm its first task is `Ensure Proton Drive backup is not configured for an invalid location`.
2. Run `python3 scripts/patch-backup-disable.py` from the Git repository root.
3. Inspect `git diff -- ansible/roles/backup/tasks/main.yml`.
4. Run `python3 scripts/maintenance-check.py`.
5. Run `cd ansible; ansible-playbook playbooks/workstation.yml --check --diff -K --limit laptop`.
6. Run a real provision only after reviewing diff, then repeat it for idempotency.
7. Run the strict health validation playbook separately.

## Test the fix without affecting normal backups

The normal enabled configuration should stay enabled and show no changes after two runs. For a **maintenance window only**, temporarily set `workstation_backup_enabled: false` in inventory, run the playbook, and check that `systemctl --user is-enabled workstation-proton-backup.timer` no longer says `enabled`. Restore the variable and rerun Ansible to re-enable the timer. **Do not attempt this while a backup is running.**

An alternative, safer in normal production, is to test disable/re-enable in the disposable VM with a simulated user timer; a headless VM may not have the required user D-Bus session.

## Release checklist

- [ ] Git worktree clean at baseline
- [ ] Patch reviewed and only intended task changed
- [ ] Existing backup and restore remain working
- [ ] No unintended timer disablement in enabled configuration
- [ ] Provisioning second run has `changed=0`
- [ ] Strict workstation health audit passes
- [ ] `git diff --check` passes
- [ ] Changes committed before tagging
- [ ] Annotated tag `v1.0.1` created after validation

Do not commit secrets, systemd unit credentials, or Proton session data.
