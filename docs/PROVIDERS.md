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
| backup | `proton/drive` | `providers/proton/drive` | Proton Drive CLI + filtered scheduled upload (`workstation-proton-backup.*`) | Proton account (Drive needs a paid plan) | Proton session in keyring |
| backup | `google/drive` | `providers/google/drive` | rclone + scheduled `workstation-rclone-backup.*`; works with any rclone remote (Google Drive, SFTP/S3 to your VPS) | depends on remote (Google account for `gdrive`) | `~/.config/rclone/rclone.conf` OAuth token / service-account JSON |
| sync | `syncthing` | `providers/syncthing` | Syncthing user service; pairing manual, unique identity per machine | none | `~/.config/syncthing/` key/cert |
| vpn | `proton/vpn` | `providers/proton/vpn` | Proton VPN repo package + GNOME app | Proton account (VPN needs a paid plan) | Proton session in keyring |
| vpn | `wireguard` | `providers/wireguard` | wireguard-tools; config per machine in `~/.config/wireguard/<iface>.conf`; optional autostart (`workstation_wireguard_autostart`) | self-hosted server (VPS/home) | private key in the `.conf` (mode 0600) |
| mail | `proton/mail` | `providers/proton/mail` | Proton Mail desktop app (pinned DEB, amd64) | Proton account | Proton session in keyring |
| mail | `google/mail` | `providers/google/mail` | Thunderbird; accounts added manually (IMAP/SMTP, OAuth for Gmail; works with any IMAP server) | any IMAP provider (Gmail, self-hosted, …) | mail password/OAuth in profile/keyring |
| passwords | `proton/pass` | `providers/proton/pass` | Proton Pass desktop app (pinned DEB, amd64) | Proton account | Proton session in keyring |
| passwords | `keepassxc` | `providers/keepassxc` | KeePassXC; vault file at `workstation_keepassxc_vault` (inside backup sources by default) | none (local vault) | vault master password / key file on the machine |
| any | `custom` | `providers/custom` | guidance-only: prints the provider contract, deploys nothing | — | — |

Both backup providers share the same capability-level variables (`workstation_backup_sources`, `workstation_backup_excludes`, schedule, `workstation_backup_timer_enabled`, `workstation_backup_dataset_id`, `workstation_backup_manifest_enabled`, restore-drill schedule) and both write the normalized `~/.local/state/workstation-backup/status.json` record (plus a `history.jsonl` append and an uploaded per-file SHA-256 `manifest.json`) that `workstation-backup-health-check` monitors — the monitor follows the selected provider's units automatically and also warns when the last restore drill (`verified_restore_at`, monthly `workstation-*-backup-restore-test.timer`) is stale. Unit names stay provider-specific (`workstation-proton-backup.*` vs `workstation-rclone-backup.*`) so old and new can run side by side during a migration; do not rename them in place.

## Using your own provider (self-hosted / any vendor)

The layout is vendor-namespaced so the project can grow by contribution:

```
ansible/roles/providers/
  proton/          # one directory per vendor
    drive/         #   one directory per provider (role): tasks/main.yml, defaults/, templates/, files/
    vpn/
    pass/
    mail/
    _deb/          # names starting with '_' are private helpers, not selectable providers
  google/
    drive/
    mail/
  syncthing/       # single-product vendors may use a flat directory instead
  wireguard/
  keepassxc/
  custom/
```

1. Create `ansible/roles/providers/<vendor>/<name>/` in **your clone** with at least `tasks/main.yml` (plus `defaults/main.yml` for your variables). Use `_`-prefixed names for shared helper roles inside a vendor directory.
2. Declare the adapter contract in `defaults/main.yml` and record it in `tasks/main.yml` (required — the playbook fails the run otherwise):

   ```yaml
   workstation_provider_supported_actions: [install, configure, health, disable]
   workstation_provider_manual_actions: [export, import, verify, cutover]
   ```

   plus the "Record provider adapter contract" task writing `~/.local/state/workstation-provider/<provider>.json` (copy the task from any built-in provider role; `workstation_capability` and `workstation_provider_path` are passed in by the playbook).
3. Set `workstation_providers.<capability>: <vendor>/<name>` (or a flat `<name>`).
4. No playbook edit is needed — the playbook includes `providers/{{ workstation_providers.<capability> }}` and lists every discovered provider in its validation error. See [CONTRIBUTING.md](../CONTRIBUTING.md) "Adding a provider" for the full contract and boundaries.

**Provider contract** (full details in [MIGRATE.md](MIGRATE.md) §5):

- Always implement `install` / `configure` / `health`.
- Implement `export` / `import` / `verify` only where the backend supports them; otherwise list them in `workstation_provider_manual_actions` — never claim an unsupported operation succeeded.
- Health output: write `~/.local/state/workstation-<capability>/latest.txt` containing exactly one `OVERALL:` line, and register it in `workstation_report_sources` so the weekly report and GNOME alerts pick it up. Backup providers must additionally write `~/.local/state/workstation-backup/status.json` + `history.jsonl`, upload a `manifest.json`, and provide a restore-drill script (schema in MIGRATE.md §5).
- Preflight inventory is repository-side: extend `scripts/preflight-collect.py` with a section for your provider (never print secrets; truncate device IDs).
- Secrets stay in `~/.config`, the keyring, or mode-0600 files — never in Git, never in backup sources.
- Switching providers never deletes data, revokes sessions, or uninstalls the old provider. `disable` stops units and leaves data in place.

## Self-hosted example: one VPS

A typical single-VPS setup, workstation side:

| Capability | Server side (VPS, deployed outside this repo) | Workstation provider |
| --- | --- | --- |
| passwords | **Vaultwarden** (Bitwarden-compatible, docker) | `custom` with your own client role (`providers/<you>/vaultwarden-client`, Bitwarden desktop/CLI pointed at `https://vault.example.com`), or `keepassxc` for a purely local vault |
| vpn | **WireGuard** server (`wg-quick`/`wg-easy`) | `wireguard` + `~/.config/wireguard/wg0.conf` |
| backup | SSH/SFTP or S3 on the VPS; restic/borg server-side if you want snapshots | `google/drive` with an **sftp remote** (`workstation_rclone_remote: vps`) |
| mail | **maddy** or **docker-mailserver** (IMAP/SMTP) | `google/mail` (Thunderbird) with your server's IMAP/SMTP endpoints |
| sync | optional second Syncthing device, or none | `syncthing` |

Moving **real data** from one provider to another always follows the staged workflow in [MIGRATE.md](MIGRATE.md) §2 (preflight → independent recovery proof → parallel setup → transfer → verify → cutover → observe → separately approved decommission). Changing `workstation_providers` in inventory only changes what Ansible installs/starts — it never migrates or deletes data.

## Related

- [DEPLOY.md](DEPLOY.md) §4 — architecture and acceptance criteria
- [MIGRATE.md](MIGRATE.md) — adapter contract, migration workflow, rollback
- [TODO.md](TODO.md) — remaining provider work
