# MIGRATE — Switching workstation providers without losing data

**Status:** Manual runbooks for the public `v1.3.0` repository. The capability/provider **selection** is implemented (`workstation_capabilities` / `workstation_providers` dispatching to vendor-namespaced roles under `ansible/roles/providers/`, with normalized backup monitoring), but there is **no one-command migration tool**: every cutover below remains a staged, human-driven procedure. Export/import orchestration per adapter is still planned work.

Related: [DEPLOY.md](DEPLOY.md) · [PROVIDERS.md](PROVIDERS.md) · [TODO.md](TODO.md) · [WORKSTATION-ROUTINE-CHECKLIST.md](WORKSTATION-ROUTINE-CHECKLIST.md) · [WORKSTATION-RECOVERY.md](WORKSTATION-RECOVERY.md).

## Design principle: switch capabilities, not the entire stack

A workstation is composed of distinct *capabilities* and their *providers*. Changing a provider must not automatically remove the underlying data or unrelated applications.

| Capability | Current / typical provider | Possible destination classes | Migration challenge |
| --- | --- | --- | --- |
| File backup | Proton Drive CLI with filtered scheduled uploads | Encrypted object storage, SFTP, NAS, another cloud drive | Revisions, restore validation, retention, encryption, deletions |
| File sync | Syncthing | Another sync service or a shared-drive client | Device IDs, conflicts, sharing semantics, version history |
| VPN | Proton VPN | Another VPN client or WireGuard/OpenVPN config | Auth, routing, kill switch, DNS and leak protection |
| Password manager | Proton Pass | Another password manager | Export encryption, TOTP/passkeys, attachments, shared vaults, metadata |
| Mail | Proton Mail | Another mail provider/client | Mailboxes, labels, filters, contacts, domains, aliases and encryption |
| Terminal/shell | Fish + Ghostty + Starship | Another terminal/shell | Startup syntax, keybindings, prompt, environment activation |
| Development tools | mise, rustup, uv | Other version managers | Version pin semantics, global tools, shims/PATH, reproducibility |
| Containers | Docker + Compose | Another container runtime | Networks, images, volume/data portability, CLI behavior |

**No provider should be assumed equivalent.** Some proprietary features (e.g., shared vault permissions, passkeys, email aliases or provider-specific version history) may not export faithfully. Keep the source available until those gaps are explicitly accepted.

## 1. Migration invariants (apply to every capability)

1. **Back up and prove recovery first.** Restore a meaningful sample to a separate location. For critical data, maintain an independent recovery copy—not just the provider being replaced.
2. **Inventory before making changes.** Record datasets, sizes, metadata, source of truth, credentials, scheduled tasks, dependent services and remaining subscription constraints.
3. **Keep old and new implementations side by side where safe.** The old service remains the rollback path until verification and cutover are complete.
4. **Avoid uncontrolled dual writes.** Identify one authoritative source, or explicitly define conflict handling. For sync/mail/passwords, careless simultaneous writes can create duplicates or data loss.
5. **Keep exports and secrets local/encrypted.** Never commit exported vaults, email archives, private keys, provider tokens or backup manifests containing sensitive paths/contents to Git.
6. **Compare what matters.** File count, byte size, checksums and sample restores; also verify timestamps, folder structure, permissions, metadata, sharing and policies where supported.
7. **Cut over deliberately.** Stop old schedules, switch consumers and monitoring, then enable new schedules. Preserve old data for a defined rollback window.
8. **Decommission only after acceptance.** Revocation/deletion is a separate, reviewed action—not an implicit effect of an Ansible provider selection change.

## 2. Universal migration workflow

| Stage | Procedure | Exit condition |
| --- | --- | --- |
| **A. Preflight** | List capabilities and current providers; verify export rights, destination capacity, auth, network access, compliance and recovery options. | Data inventory and risks documented. |
| **B. Independent recovery** | Take a known-good backup and restore a sample; save an encrypted export if needed. | Recovery does not depend only on the old live service. |
| **C. Parallel setup** | Install/configure destination without removing source; enroll credentials locally; deploy in a test profile/host if possible. | New provider can authenticate and pass health checks. |
| **D. Initial transfer** | Export/import or copy data. Avoid destructive mirror flags and unattended deletions. | Inventory reconciled; mismatches recorded. |
| **E. Validation** | Check counts, checksums, sample opens/restores and provider-specific metadata/behaviors. | Signed-off acceptance criteria met. |
| **F. Cutover** | Freeze writes if necessary, transfer delta, switch schedules/clients/defaults, verify routing and service behavior. | New provider is authoritative; no silent dual writes. |
| **G. Observation** | Watch logs, user reports, restore tests and notifications during a rollback window. | Stable service and no missing data. |
| **H. Decommission** | Disable old units and revoke sessions/tokens; delete old remote copies only with explicit approval and proven recovery. | Old provider retired safely. |

### Migration worksheet (copy per capability)

```text
Capability:
Source provider / version:
Destination provider / version:
Host(s) / unique identities:
Authoritative data and dataset locations:
Expected item count / size / metadata:
Encryption, credential and export format:
Last verified independent restore:
Target data residency / retention / cost constraints:
Dependencies (apps, timers, DNS, mail aliases, links):
Transfer method / delta method:
Validation evidence and known exceptions:
Scheduled cutover time and write-freeze plan:
Rollback trigger / rollback deadline / responsible person:
Old data deletion approval date (separate):
```

## 3. Example: migrating **from Proton Drive backups** to another backup backend

Since `v1.3.0`, the backup capability is selected by `workstation_providers.backup` (`proton/drive`, `google/drive`, …) and the monitor follows the selected provider's units via the normalized `~/.local/state/workstation-backup/status.json` record. Changing that variable provisions the new provider's roles, but it **does not migrate data and does not touch the old provider's remote copies** — follow the runbook below.

### Preflight

- Confirm both unique source destinations: `/my-files/Workstation-Backups/Omnissiah-desktop/` and `/my-files/Workstation-Backups/Omnissiah-pocket/` (or their actual configured hostnames).
- Read the backup include/exclude rules. Determine whether the copy is a revisioned file upload, not a point-in-time snapshot; identify what has never been backed up (e.g., Docker volumes or encrypted session stores).
- Choose the destination architecture: local/remote storage, encryption at rest **and before upload if required**, retention, pruning policy, restore process and cost. Do not assume the new backend implements Proton revisions.
- Restore a source sample to a **separate** directory and compare it. For an independent historical archive, decide whether and how old Proton revisions can be exported; they may require provider-specific manual steps.

### Parallel setup and test

1. Configure the destination's client and authentication on **one host**, without disabling the Proton backup job.
2. Create an explicit dataset manifest and a deterministic initial transfer; keep a separate backup job name and output path so monitors cannot confuse old and new success states.
3. Run one real destination backup. Restore several representative files—including a modified file and a nested directory—and compare content and meaningful metadata.
4. Repeat on the other host with a **distinct** destination; verify backup monitors and GNOME alerts can distinguish both sources.

### Cutover and rollback

1. Record a final successful Proton backup and its log timestamp.
2. Temporarily stop the old **timer**, not the data: `systemctl --user stop workstation-proton-backup.timer` (manual cutover only). **Do not disable or delete old data merely by switching a variable.**
3. Run the new provider's verified final/delta backup. Enable the new timer. Confirm success metadata points to the new provider and a restore succeeds.
4. Update Ansible capability selection and monitors; deploy, run strict validation and check idempotency. Inspect reports for false success caused by stale Proton success stamps.
5. Keep the old account/backup readable through the agreed rollback window. If the new destination fails, stop the new timer and restore the previously reviewed Proton schedule **only after checking for writes made since cutover**.
6. Separately approve account closure, token revocation and deletion when no longer needed.

> **Failure mode to avoid:** Running both backup providers may be acceptable during migration, but both must have independent destinations and success records; one must not overwrite the other's state. An active timer or a green `last-success` stamp does not by itself demonstrate restorable data.

## 4. Capability-specific migration precautions

### Password managers (Proton Pass → another manager)

- Export from the source using its supported tool and an appropriately secured format; an unencrypted CSV is particularly sensitive. Keep exports temporary, protected and **outside the repository and synced folders**.
- Check entries, custom fields, notes, attachments, TOTP, passkeys, shared items, vault organization and recovery methods. Some items may need manual recreation.
- Import into a separate destination vault/profile. Test representative logins **and 2FA** before changing autofill or browser integration.
- Freeze edits around the final sync/import or explicitly reconcile changes; revoke old sessions and securely delete export artifacts only after verified cutover.

### Mail (Proton Mail → another provider)

- Inventory folders/labels, contacts, calendars, filters, signatures, aliases, domains, encrypted-message constraints and mailbox size.
- Select a supported migration method; test with a subset first. Do not assume a standard IMAP export preserves all Proton-specific metadata.
- If using a custom domain, plan MX/SPF/DKIM/DMARC changes and DNS TTL windows separately; verify inbound and outbound mail, forwarding, aliases, spam handling and recovery before cancellation.
- Maintain access to the old inbox during propagation and the observation window.

### VPN (Proton VPN → another provider)

- Record current routing, DNS, kill-switch, split-tunnel and auto-connect requirements. Authentication formats and privacy characteristics differ.
- Install the new client **without activating a conflicting kill switch**. Test public IP, DNS behavior, local-LAN access, application connectivity and reconnection after sleep/reboot.
- Switch the default connection intentionally; avoid remote cutover over a VPN-only management path without an out-of-band connection.
- Decommission old VPN unit and credentials only after traffic and recovery checks succeed.

### File sync (Syncthing → another sync engine)

- Inventory folders, sizes, ownership, ignored paths, peer/share permissions, versioning and conflicts.
- Stop or freeze writes for the final reconciliation, especially when both engines would watch the same directories. **Do not point two bidirectional sync engines at the same live tree** without an explicit collision plan.
- Verify transfer and conflict resolution between two devices; retain a separate backup before altering share topology.

### Shell / development tools / containers

- Treat shell changes as a migration of init files, PATH shims, terminal shortcuts and environment activation—not just package replacement. Keep the old shell available until a new login works.
- For mise/rustup/uv migrations, move version declarations into reviewed inventory/config before changing installed versions; test `node`, `java`, `rustc`, Python and installed CLI tools.
- Container runtime swaps require an inventory of Compose projects, networks and **persistent volumes**; image export alone does not preserve volume data. Plan application downtime and service-level validation.

## 5. Plug-and-play contracts (schema implemented; more adapters planned)

The main playbook now selects capabilities and providers (`workstation_capabilities`, `workstation_providers` in `group_vars/all.yml`) and dispatches to vendor-namespaced roles under `ansible/roles/providers/<vendor>/<name>/` (see [PROVIDERS.md](PROVIDERS.md) and [CONTRIBUTING.md](../CONTRIBUTING.md)); the built-in adapters today are the Proton, Google, Syncthing, WireGuard and KeePassXC ones plus the guidance-only `custom`. Adding another provider = a new role directory, no playbook edit. Monitoring consumes normalized records (`status.json` for backup, `latest.txt` with an `OVERALL` line for the rest), so it does not bind to Proton-specific units.

```yaml
# Active schema (defaults reproduce the original Proton + Syncthing setup)
workstation_capabilities:
  backup: {enabled: true}
  sync: {enabled: true}
  vpn: {enabled: true}
  mail: {enabled: false}
  passwords: {enabled: true}

workstation_providers:
  backup: proton/drive    # or google/drive, custom, <vendor>/<name>, none
  sync: syncthing
  vpn: proton/vpn         # or wireguard
  passwords: proton/pass  # or keepassxc

workstation_migration:
  mode: observe           # example states: observe, prepare, cutover
  retain_source: true
```

**Proposed adapter contract** (implement per capability, not as one universal data serializer):

| Action | Promise |
| --- | --- |
| `preflight` | Verify prerequisites, credentials presence, destination capacity and export limits without changing the source. |
| `install/configure` | Idempotent, scoped provisioning for the selected provider. |
| `health` | Emit a consistent machine-readable status with timestamp, provider, capability and failure reason. |
| `export` | Produce a manifest and migration artifact where the provider allows it; never imply unsupported metadata was migrated. |
| `import` | Support resumable or rerunnable transfer when safe; make conflict behavior explicit. |
| `verify` | Compare source/destination evidence and run real restore/login/connectivity tests. |
| `cutover` | Switch authoritative services and monitors only after validation; record rollback state. |
| `disable` | Stop provider services **without deleting data or credentials** by default. |

Sample proposed backup status record:

```json
{
  "schema_version": 1,
  "capability": "backup",
  "provider": "proton/drive",
  "host": "Omnissiah-desktop",
  "dataset_id": "home-selected",
  "checked_at": "<ISO-8601 timestamp>",
  "result": "success",
  "verified_restore_at": null
}
```

The `result` is only a job status, **not** proof of remote integrity. A separate restore-verification field must never be forged from a successful upload exit code.

## 6. Tests required before calling the system provider-independent

- [x] Two different backup providers can be selected by inventory/profile without editing the playbook. _Done in v1.3.0:_ `proton/drive` and `google/drive` share the `workstation_backup_*` variables and the normalized status record.
- [x] Disabling Proton Drive backup does not cause an unrelated Proton VPN, mail or password-manager role to fail. _Done in v1.3.0:_ providers are independent roles (`proton/{drive,vpn,pass,mail}`); capabilities toggle independently.
- [x] Backup monitor, reports and GNOME alerts consume normalized status and do not assume `workstation-proton-backup.service`. _Done in v1.3.0:_ the checker reads `status.json` (legacy `last-success` fallback) and follows `workstation_backup_monitor_service/_timer` set by the selected provider.
- [ ] Export/import preserves the documented dataset and identifies unsupported metadata; a real restore test passes.
- [ ] A reversible cutover can switch providers and roll back without silently losing intervening writes.
- [ ] Both existing machines still pass strict validation and idempotency tests after provider separation.
- [ ] Provider decommissioning never deletes cloud data or local exports without an explicit reviewed operation.

**First recommended experiment:** implement a second backup target for a small, non-sensitive test dataset, with a separate schedule, status record, test restore and rollback. Only then migrate real workstation backup data.
