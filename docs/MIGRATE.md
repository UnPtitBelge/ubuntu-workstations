# Change a provider without losing data

Use this guide when replacing backup, sync, VPN, mail or password tooling.
Selecting a new role in inventory does not transfer data, revoke sessions or
retire the previous provider. [Providers](PROVIDERS.md) lists selectable roles;
[Deploy](DEPLOY.md) owns provisioning and explicit disabling.

The console's Lifecycle section presents this sequence as guidance. Its Setup
editor does not perform provider migrations or decommissioning. An Ansible
preview/apply from the dashboard does not establish the recovery and cutover
evidence required here.

## 1. Rules for any migration

Keep the source usable until independent recovery and destination verification
have passed. Preserve encryption, metadata, identities, retention and access.
Export credentials/vaults only through an independently protected process, never
into this repository or an ordinary shared folder.

Choose one capability and one host first. Record the original configuration,
transfer method, acceptance tests, write-freeze requirements and rollback window.
Do not delete old data or revoke access as a side effect of selecting a provider.

## 2. Staged workflow

| Stage | Work | Acceptance |
| --- | --- | --- |
| A. Preflight | Inventory data, dependencies, auth presence, capacity and export limits | Scope and risks recorded |
| B. Independent recovery | Preserve a known-good copy/export and restore a sample | Recovery does not depend only on the live source |
| C. Parallel setup | Enroll the replacement in an isolated test setup | Auth and required behavior work without retiring the source |
| D. Transfer | Initial export/import or copy, without destructive mirror flags | Counts/metadata reconciled and exceptions recorded |
| E. Verify | Compare checksums, open files and test service-specific behavior | Written acceptance tests pass |
| F. Cutover | Freeze/reconcile writes as required; switch approved schedules/clients | Correct authoritative provider and monitoring |
| G. Observe | Watch actual jobs and repeat recovery during the rollback window | No missing data or unexplained failure |
| H. Decommission | Separately approve unit retirement, revocation and any deletion | Verified recovery and explicit deletion approval |

The preflight playbook collects local evidence and writes a private report; it
does not prove account usability, remote capacity or all migration prerequisites:

```fish
cd ~/Projects/ubuntu-workstations/ansible
set target desktop
# Use laptop only when running on that machine.
ansible-playbook playbooks/provider-preflight.yml --limit $target
```

Review reports under `~/.local/state/workstation-migration/` privately. It
collects device-ID prefixes/auth presence rather than intended secret values;
outputs can still contain personal paths and other private context.

Record: capability, source/destination versions, host and dataset identities,
expected contents/metadata, encryption/export format, verified recovery,
transfer/delta method, acceptance evidence, cutover time, rollback trigger and
separately approved decommissioning.

## 3. Backup migration helper: actual scope and limits

`playbooks/migrate-backup.yml` currently knows `proton/drive` and `google/drive`.
Inspect it before a real migration. Its modes have different effects:

| Mode | Actual effects |
| --- | --- |
| `observe` (default) | Reads local latest status and displays inventory-derived provider information; does not prove remote feasibility |
| `prepare` | Runs preflight, the already-installed new backup helper's selection preview and a **real restore download** through the current helper; writes local evidence/plan |
| `cutover` | Requires `migration_confirm=true`; includes the new provider role, which can install/configure software and enable schedules, then stops the original upload timer and writes a journal entry |
| `rollback` | Requires `migration_confirm=true`; stops the new upload timer and enables the timer identified by the current inventory selection as original |

To inspect, on the correct machine:

```fish
ansible-playbook playbooks/migrate-backup.yml --limit $target
```

`prepare` requires both helpers to be installed/configured. It does not install
the replacement or upload its dataset. Some commands explicitly run even under
Ansible `--check`, including the restore download. Its saved plan is not an
enforced gate: failed preview/restore results can be recorded without aborting.
Read and validate the evidence before considering cutover.

Before any real cutover, address these current limitations in a reviewed plan:

- The helper derives the original provider from `workstation_providers.backup`.
  Changing that selection first can make cutover reject the target or rollback
  identify the wrong original. Freeze/record original intent separately; reconcile
  the new selection and monitor only at the deliberately reviewed stage.
- The helper manages upload timers, not every old restore-drill timer or monitor.
  Provisioning the new role can start its timers according to enable flags.
  Review the full role effects, running jobs and monitoring reconciliation.
- Distinct unit names permit parallel installation, but `status.json`, manifest
  and restore timestamp state are shared. Concurrent providers are not isolated
  monitoring streams; use provider journals/history and independent evidence.
- A real end-to-end transfer, service-context restore and reversible cutover have
  not been established by the helper's existence or static checks. See [TODO](TODO.md#correctness-before-more-automation).

For a first experiment, use one small non-sensitive dataset and independent
host-specific destinations. Prove the source restore, new real upload and new
chosen-file restore before scheduling cutover. Manifests help compare content;
they do not export old revisions or preserve provider-specific metadata by magic.
Keep old data accessible throughout the rollback window and reconcile writes
made since cutover before rolling back. Promotion to the other workstation is
a separate operation.

## 4. Capability-specific acceptance

| Capability | Preserve and verify |
| --- | --- |
| Backup | Coverage/exclusions, host destination, checksums, retention, old revisions where needed, service-context auth and independent chosen-file recovery |
| Sync | Folder IDs, distinct device identities, sharing/versioning and conflict behavior; do not point two bidirectional engines at one live tree without a collision plan |
| VPN | Endpoint/keys, routing/DNS, split-tunnel/kill-switch behavior and rollback connectivity; changing a client is not proof of a usable tunnel |
| Passwords | Notes, custom fields, attachments, TOTP, passkeys, shared vaults and recovery methods; test logins/2FA before changing autofill; protect exports and reconcile edits |
| Mail | Folders/labels, messages, contacts, calendars, filters, aliases/domains and encryption limitations; test send/receive before any DNS/MX cutover |

For toolchain/container changes, include project compatibility, CLI behavior,
networks and persistent volumes. Image export alone does not preserve application
data. Unsupported metadata must be listed explicitly, with manual recreation
steps rather than a successful import claim.

## 5. Adapter and evidence contracts

Provider defaults declare `workstation_provider_supported_actions` and
`workstation_provider_manual_actions`. Roles write declarative contract records
under `~/.local/state/workstation-provider/`, replacing `/` in provider names
with `__` (for example `proton__drive.json`). Records contain `schema_version`,
`capability`, `provider`, `supported_actions`, `manual_actions`; they contain no
per-run timestamp. An unchanged record should remain unchanged on a second pass.

The main playbook asserts that selected contract files exist. The declaration
is not an action-dispatch API, proof that data moved or validation of every
promised operation. VPN/desktop runtime shutdown and most export/import/cutover
operations are manual. `custom` is guidance only. See
[Contributing](../CONTRIBUTING.md#adding-a-provider) for adapter implementation rules.

Backup helpers intend to write the following **shared latest** status, plus
append-only `history.jsonl` under `~/.local/state/workstation-backup/`:

```json
{
  "schema_version": 1,
  "capability": "backup",
  "provider": "proton/drive",
  "host": "example-host",
  "dataset_id": "home-selected",
  "checked_at": "<ISO-8601 timestamp>",
  "result": "success",
  "verified_restore_at": null,
  "files": 123,
  "bytes": 456789
}
```

`verified_restore_at` is intended to be a successful restore timestamp or null,
never an upload timestamp. Inspect the journal/direct recovery result as well;
current serialization and provider attribution gaps are tracked in TODO. The
monitor has a legacy success-stamp fallback and does not validate all identity
fields, so a healthy result alone is not provider-specific recovery proof.

With manifests enabled, the local `manifest-latest.json` and remote
`manifest.json` contain `schema_version`, `dataset_id`, `host`, `generated_at`,
`file_count`, `total_bytes` and file entries with `path`, `size`, `sha256`.
This describes selected files, not an atomic snapshot or universal export format.

## 6. Evidence needed before accepting a migration

Record a real source recovery, destination transfer and independent destination
restore; unsupported metadata and retention differences; actual scheduled runs;
correct provider/host/dataset monitoring; and a rollback exercise that preserves
intervening writes. Revalidate each affected machine separately. Static syntax,
isolated unit simulations and an active timer are insufficient.
