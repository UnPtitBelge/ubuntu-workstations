# PROVIDERS — capabilities, built-in providers, and your own

The workstation is composed of **capabilities** (backup, sync, VPN, mail, passwords), each with a selectable **provider**. Selection is pure inventory configuration:

```yaml
# ansible/inventory/group_vars/all.yml (defaults reproduce the original Proton + Syncthing setup)
workstation_capabilities:
  backup: {enabled: true}
  sync: {enabled: true}
  vpn: {enabled: true}
  mail: {enabled: true}
  passwords: {enabled: true}

workstation_providers:
  backup: proton/drive      # proton/drive | google/drive | custom | <vendor>/<name> | none
  sync: syncthing           # syncthing | custom | <vendor>/<name> | none
  vpn: proton/vpn           # proton/vpn | wireguard | custom | <vendor>/<name> | none
  mail: proton/mail         # proton/mail | google/mail | custom | <vendor>/<name> | none
  passwords: proton/pass    # proton/pass | keepassxc | custom | <vendor>/<name> | none
```

A provider value is a path relative to `ansible/roles/providers/` — either a flat name (`syncthing`) or a vendor namespace (`proton/drive`, `google/mail`). Per host, override in `host_vars/<host>.yml` (or via `setup.local.yml` for new machines). Set a provider to `none` to skip that capability. The playbook validates that every selected provider role exists and fails with the list of available providers otherwise.

**Scope: Ubuntu 26.04 LTS only for now.** Providers target this repository's supported platform; do not add distro-specific conditionals.

## Built-in providers

| Capability | Provider | Role path | What it installs/configures | Account / subscription | Secrets (never in Git) |
| --- | --- | --- | --- | --- | --- |
| backup | `proton/drive` | `providers/proton/drive` | Proton Drive CLI + filtered scheduled upload (`workstation-proton-backup.*`) | Proton account with sufficient storage/access | Proton session in keyring |
| backup | `google/drive` | `providers/google/drive` | rclone + scheduled `workstation-rclone-backup.*`; works with any rclone remote (Google Drive, SFTP/S3 to your VPS) | depends on remote (Google account for `gdrive`) | `~/.config/rclone/rclone.conf` OAuth token / service-account JSON |
| sync | `syncthing` | `providers/syncthing` | Syncthing user service; pairing manual, unique identity per machine | none | `~/.config/syncthing/` key/cert |
| vpn | `proton/vpn` | `providers/proton/vpn` | Proton VPN repo package + GNOME app | Proton account with the required service access | Proton session in keyring |
| vpn | `wireguard` | `providers/wireguard` | wireguard-tools; config per machine in `~/.config/wireguard/<iface>.conf`; optional autostart (`workstation_wireguard_autostart`) | self-hosted server (VPS/home) | private key in the `.conf` (mode 0600) |
| mail | `proton/mail` | `providers/proton/mail` | Proton Mail desktop app (pinned DEB, amd64) | Proton account | Proton session in keyring |
| mail | `google/mail` | `providers/google/mail` | Thunderbird; accounts added manually (IMAP/SMTP, OAuth for Gmail; works with any IMAP server) | any IMAP provider (Gmail, self-hosted, …) | mail password/OAuth in profile/keyring |
| passwords | `proton/pass` | `providers/proton/pass` | Proton Pass desktop app (pinned DEB, amd64) | Proton account | Proton session in keyring |
| passwords | `keepassxc` | `providers/keepassxc` | KeePassXC; vault file at `workstation_keepassxc_vault` (inside backup sources by default) | none (local vault) | vault master password / key file on the machine |
| any | `custom` | `providers/custom` | guidance-only: prints the provider contract, deploys nothing | — | — |

Both backup providers share the same capability-level variables (`workstation_backup_sources`, `workstation_backup_excludes`, schedule, `workstation_backup_timer_enabled`, `workstation_backup_dataset_id`, `workstation_backup_manifest_enabled`, restore-drill schedule) and both write the normalized `~/.local/state/workstation-backup/status.json` record (plus a `history.jsonl` append and an uploaded per-file SHA-256 `manifest.json`) that `workstation-backup-health-check` monitors — the monitor follows the selected provider's units automatically and also warns when the last restore drill (`verified_restore_at`, monthly `workstation-*-backup-restore-test.timer`) is stale. Unit names stay provider-specific (`workstation-proton-backup.*` vs `workstation-rclone-backup.*`) so old and new can run side by side during a migration; do not rename them in place.

## Adding a provider

Use [Contributing](../CONTRIBUTING.md#adding-a-provider) for role layout,
discovery and adapter implementation requirements. [Migration §5](MIGRATE.md#5-adapter-and-evidence-contracts)
owns the evidence/contract reference. A declared action is not proof that its
operation or real data migration has been verified.

Provider `none` and capability `enabled: false` skip dispatch, leaving old
services/data in place. Use the explicit [disable procedure](DEPLOY.md#provider-disabling-and-profile-changes)
before retiring a selected provider. Switching providers does not migrate or
delete data. `custom` supplies guidance, not a working replacement backend.

## Self-hosted example: one VPS

Conceptual workstation-side choices below; the server stacks are not installed, hosted or managed by this repository:

| Capability | Server side (VPS, deployed outside this repo) | Workstation provider |
| --- | --- | --- |
| passwords | **Vaultwarden** (Bitwarden-compatible, docker) | `custom` with your own client role (`providers/<you>/vaultwarden-client`, Bitwarden desktop/CLI pointed at `https://vault.example.com`), or `keepassxc` for a purely local vault |
| vpn | **WireGuard** server (`wg-quick`/`wg-easy`) | `wireguard` + `~/.config/wireguard/wg0.conf` |
| backup | SSH/SFTP or S3 on the VPS; restic/borg server-side if you want snapshots | `google/drive` with an **sftp remote** (`workstation_rclone_remote: vps`) |
| mail | **maddy** or **docker-mailserver** (IMAP/SMTP) | `google/mail` (Thunderbird) with your server's IMAP/SMTP endpoints |
| sync | optional second Syncthing device, or none | `syncthing` |

Moving **real data** from one provider to another always follows the staged workflow in [MIGRATE.md](MIGRATE.md) §2 (preflight → independent recovery proof → parallel setup → transfer → verify → cutover → observe → separately approved decommission). Changing `workstation_providers` in inventory only changes what Ansible installs/starts — it never migrates or deletes data.

## Related

- [DEPLOY.md](DEPLOY.md) §4 — selecting capabilities and providers
- [MIGRATE.md](MIGRATE.md) — adapter contract, migration workflow, rollback
- [TODO.md](TODO.md) — remaining provider work
