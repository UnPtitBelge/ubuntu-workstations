# Public Release Audit — Ubuntu Workstations

**Date:** 2026-11-04 · **Baseline:** `v1.2.0` + post-release working tree (`main` @ `2b2b0f2`) · **Auditor:** Mistral Vibe (read-only audit + minimal documentation remediation)
**Scope:** all 144 tracked files, the complete local Git history (56 commits, 4 annotated tags, 1 branch), and portability/provider review. No provisioning, no network changes, no history rewrite, no push.

> Secret values are never reproduced in this report. Anything sensitive was redacted before recording.

## Executive summary

- **Publication readiness: READY WITH WARNINGS.** No credentials, private keys, tokens, Syncthing identities, Proton sessions, personal emails in file contents, or private IPs were found in the working tree **or** in the full Git history.
- **Decision item resolved (was Medium):** every commit's author/committer metadata contains `unptitbelge@pm.me` (GitHub handle `UnPtitBelge`). The owner confirmed on 2026-11-04 that this is their main GitHub email and approves publishing it — no history rewrite is needed or performed.
- At audit time the real hostnames appeared in docs and inventory and the owner approved publishing them; post-release the hostnames were removed from the working tree (placeholders `my-desktop` / `my-laptop` now — see the addendum). Username `matteo` appears in docs; the owner approved publishing it.
- Remediation performed in this audit (owner-approved): stale `ansible/roles/health/files/` copies deleted; `LICENSE` (MIT), `SECURITY.md`, `CONTRIBUTING.md`, `.gitattributes`, and a gitleaks + static-checks CI workflow added; gitleaks 8.30.1 installed locally (checksum-verified) and run over the full history — **no leaks found**; two inert generic example inventory files, README accuracy fixes, an "external services" note, and a DEPLOY.md pointer. Third-party dev CLIs (the `npm:` AI assistants in `dotfiles/mise/config.toml` and `crewai`/`jupyterlab`/`mistral-vibe` in `workstation_python_tools`) were removed from the shared defaults on owner request — users add their own tools per host. Both workstations remain provisionable; no operational role, script, inventory or host_vars file was changed.

## Security findings

| # | Severity | Location | Finding | Impact | Remediation | Where |
|---|----------|----------|---------|--------|-------------|-------|
| S1 | Informational | entire tree + history | No passwords, tokens, API keys, private keys (no PEM blocks), Proton session data, Syncthing device IDs/certs, or hardcoded credentials found. Verified by pattern-scanning **every unique blob in history** (redacted output) plus targeted `git grep`. | None | Keep the existing `.gitignore` secrets section; add CI secret scanning (S5). | Current + history |
| S2 | Low — **resolved** | `ansible/roles/health/files/` (3 files) | Stale, unreferenced duplicates of the health checker; the `.py` copy failed `py_compile` (unterminated string literal). The role deploys `templates/*.j2` (`health/tasks/main.yml:16,23,30`); the deployed `~/.local/bin/workstation-health-check` was verified to compile. Nothing referenced `files/`. | Zero runtime impact; would have failed a CI `py_compile` gate. | **Deleted** with owner approval on 2026-11-04 (`workstation-health-check.py`, `.service`, `.timer`); `py_compile` now passes on all tracked `.py`. | Current |
| S3 | Low | `ansible/roles/bootstrap/tasks/main.yml:24-31, 50-55, 76-85` | mise/uv/rustup installer scripts are downloaded over HTTPS and piped to `sh` without checksum pinning. `MISE_VERSION` pins mise; uv and rustup installers are unpinned (standard upstream practice). | Supply-chain risk if an upstream installer URL is compromised; HTTPS mitigates. | Pin checksums or vendor the installers (P2). | Current |
| S4 | Informational | `ansible/roles/proton/defaults/main.yml:17-23`, `proton/tasks/vpn.yml:30-31`, `proton/tasks/desktop-apps.yml:34,47`, `containers/tasks/main.yml:9-14` | All Proton/Docker artifacts are checksum- or GPG-pinned. The 128-hex strings are vendor SHA-512 integrity pins, **not** secrets. | Positive finding — keep. | None. | Current |
| S5 | Informational — **mitigated** | `.github/workflows/ci.yml` | No CI/CD workflows existed at audit time. **Added:** `ci.yml` runs gitleaks (full history, `fetch-depth: 0`) plus YAML/Python/Ansible static checks on every push to `main` and every PR. | Secrets introduced later are now blocked by CI. | Also enable GitHub secret scanning / push protection in the repository settings (a UI setting, not a file — see checklist). | Current |
| S6 | Informational | `assets/wallpapers/desktop.png` | 5 MB binary; chunk scan shows only IHDR/IDAT/IEND — no tEXt/eXIf metadata, no embedded personal data. | Repo size only. | Optional: keep, compress, or drop; add `*.png binary` to `.gitattributes` if kept. | Current + history |
| S7 | Informational | `scripts/patch-backup-disable.py` | One-off migration patch, already applied (marker present at `backup/tasks/main.yml:2`). Harmless. | Cosmetic. | Removed during post-v1.3.0 cleanup; fix remains in `providers/proton/drive`. | Resolved |
| S8 | Informational — **resolved** | audit environment | gitleaks was initially unavailable, so git-native inspection was used as the fallback (every blob pattern-scanned, redacted). **Afterwards** gitleaks 8.30.1 was installed locally (official GitHub release, SHA-256 verified against the published checksums) and run with `--redact` over the full history: 56 commits scanned, **no leaks found** (exit 0). | Both a dedicated scanner and manual inspection now agree. | gitleaks also runs in CI (`.github/workflows/ci.yml`) and is re-run on the published repo per the checklist. | History |

## Privacy findings

| # | Severity | Location | Personal data | Where |
|---|----------|----------|---------------|-------|
| P1 | Medium | commit metadata of all 56 commits (`git log --format='%an <%ae> %cn <%ce>'` → `UnPtitBelge <unptitbelge@pm.me>`); also local `git config user.email` and the `origin` remote URL | Personal Proton Mail address (`pm.me`) + GitHub handle in author/committer fields of every commit. GitHub exposes commit metadata publicly. The remote URL itself is not published. | History (all commits) |
| P2 | Informational | `docs/WORKSTATION-INSTALL.md:10,121`; 9 historical README blob lines | Linux username `matteo` and `/home/matteo` paths in old README versions. **Explicitly approved for publication by the owner.** | Current (docs) + history |
| P3 | Informational | `ansible/inventory/host_vars/{desktop,laptop}.yml`, README, `docs/DEPLOY.md`, `docs/MIGRATE.md`, `docs/TODO.md`, cheatsheet, backup examples | At audit time: real hostnames and per-host backup paths in the working tree (**owner-approved at the time**). Post-release: hostnames removed from the tree, placeholders used; they remain in Git history only (owner-accepted). | History (superseded in tree) |
| P4 | Informational | `ansible/roles/gnome/defaults/main.yml:29-35` | Strings like `ubuntu-dock@ubuntu.com` are GNOME Shell extension UUIDs, not email addresses. | Current |
| P5 | Informational | — | No personal email addresses, public/private IP addresses (only `127.0.0.1`), MAC addresses, cloud account IDs, or machine-specific filesystem paths in any tracked file or historical blob. | Current + history |

**P1 decision (owner, 2026-11-04):** the `pm.me` address is the owner's main GitHub email and is approved for publication — option (a), accept. No history rewrite is performed or needed. No credential exposure was found anywhere, so nothing requires rotation; the address is an identifier, not an authentication secret.

## Portability findings

A third party **can** deploy this on a fresh Ubuntu 26.04 GNOME workstation, with manual steps documented in `docs/WORKSTATION-INSTALL.md` and `docs/DEPLOY.md` §3. Assumptions identified:

| # | Severity | Location | Assumption | Impact on a fresh machine |
|---|----------|----------|------------|---------------------------|
| T1 | Info | `ansible/inventory/hosts.yml` | Two named local hosts (`desktop`, `laptop`), `ansible_connection: local`. Adding a machine = new inventory entry + `host_vars/<name>.yml`. Generic inert examples now provided: `ansible/inventory/hosts.yml.example`, `ansible/inventory/host_vars/workstation.yml.example` (added in this audit; verified not loaded by Ansible). | Low — documented procedure. |
| T2 | Info | roles generally | HOME, UID, hostname and architecture are derived from `ansible_facts` (e.g. `backup/defaults/main.yml:9` builds the backup destination from `ansible_facts['hostname']`). No hardcoded `/home/<user>` in the current tree. | Portable by design. |
| T3 | Low | `ansible/roles/languages/tasks/main.yml:59` | PATH prepend hardcodes `mise/installs/node/22/bin`; the node major must match `dotfiles/mise/config.toml`. | Works today; breaks silently if the pin changes to another major. |
| T4 | Low | `ansible/roles/proton/tasks/desktop-apps.yml:3-8` | Proton Pass/Mail DEBs are pinned amd64-only (hard assert). Drive CLI and containerlab support aarch64. | Proton Pass/Mail fail on arm64 — assertion message is clear. |
| T5 | Low | `ansible/roles/backup/` | Backup sources assume `~/Documents` and `~/Sync` exist (script exits with a clear error otherwise); the remote parent `/my-files/Workstation-Backups/<hostname>` must be pre-created manually in Proton Drive. | Documented in `WORKSTATION-INSTALL.md` §5. |
| T6 | Info | `ansible/inventory/hosts.yml:11-12` | The `desktop` entry omits `ansible_host`/`ansible_python_interpreter` that `laptop` sets. Works with `ansible_connection: local`. | Cosmetic inconsistency only. |
| T7 | Info | `ansible/playbooks/workstation.yml:15-16` | GNOME role only runs when a GNOME session is detected (`workstation_hardware_has_gnome_session`); headless rehearsal (`rehearsal-headless.yml`) covers base/shell/bootstrap/languages only. | Expected; documented. |
| T8 | Info | `playbooks/validate-workstation.yml`, `rehearsal-headless.yml` | Ubuntu 26.04-only assertions; `sudo-rs` incompatibility with Ansible documented in `docs/ubuntu-26.04-compatibility.md`. | Scope is explicit in README/DEPLOY. |
| T9 | Info | docs | Fish shell assumed for interactive commands; `scripts/bootstrap.sh` is POSIX `sh`. | Fine. |
| T10 | Info | `ansible/playbooks/rehearsal-headless.yml` | The rehearsal playbook targets `hosts: all`; in a single VM both inventory entries share one `$HOME`, so default parallelism makes concurrent `rustup`/`mise` installs race (observed: `rustup` partial-download rename failure). Real per-machine provisioning is unaffected (one host per machine); the rehearsal must be run with `--limit <host>` or `-f 1`. Now documented in `WORKSTATION-INSTALL.md` §7. | Rehearsal-only; verified working around it. |

## Provider coupling (implemented vs proposed)

**Implemented today (v1.2.0):**

- One `proton` role bundles VPN + Drive + Pass + Mail (`ansible/roles/proton/tasks/main.yml`), with per-component flags (`workstation_proton_manage_vpn`, `workstation_proton_drive_enabled`, `workstation_proton_pass_enabled`, `workstation_proton_mail_enabled`) — partial decoupling already exists.
- The **backup capability is fully Proton-coupled**: `backup` role and `backup_monitor` hardcode the `proton-drive` CLI (`backup/defaults/main.yml:25`) and the `workstation-proton-backup.*` unit names; the success stamp (`backup_monitor/files/10-success-stamp.conf`) is Proton-specific.
- Update tooling names Docker/Proton packages explicitly (`tool_updates/defaults/main.yml`, `tool_update_policy`, `apt_update_review`).
- Already provider-neutral: health, drift, weekly report, desktop alerts, release audit, shell, containers, virtualization, Syncthing (identity deliberately left manual per host).

**Proposed, NOT implemented (do not mistake for shipped):** the `workstation_capabilities` / `workstation_providers` schema and adapter contracts appear only as labeled design sketches in `docs/DEPLOY.md` §3–4, `docs/MIGRATE.md` §5 and `docs/TODO.md` P1. This audit did **not** implement any abstraction and migrated no data.

## Recommended improvements (prioritized)

1. **P0 — Commit-email decision (P1).** ~~Accept / noreply / rewrite~~ **Done:** owner approved publishing `unptitbelge@pm.me` (main GitHub email); no rewrite.
2. **P0 — `SECURITY.md` + secret scanning in CI.** **Done:** `SECURITY.md` added; `.github/workflows/ci.yml` runs gitleaks over full history plus static checks; gitleaks 8.30.1 also run locally (no leaks). Remaining: enable GitHub secret scanning / push protection in repo settings (UI-only).
3. **P0 — LICENSE + CONTRIBUTING.** **Done:** `LICENSE` added as **MIT** (owner approved adding a license on 2026-11-04; MIT chosen as the conventional default for a personal config repo — trivially replaceable if another license is preferred). `CONTRIBUTING.md` added.
4. **P1 — Remove stale `ansible/roles/health/files/` copies (S2).** **Done:** deleted with approval; `py_compile` now passes on all tracked `.py`.
5. **P1 — Generic deployment examples.** **Done:** `hosts.yml.example`, `host_vars/workstation.yml.example`, DEPLOY.md pointer. Acceptance: a third host needs inventory data only (rest is already in DEPLOY.md §3).
6. **P1 — Capability/provider split** per `DEPLOY.md`/`MIGRATE.md`/`TODO.md` (first step: normalized backup status record so `backup_monitor` stops naming Proton units). Acceptance criteria are already defined in TODO.md P0/P1.
7. **P2 — Pin or vendor uv/rustup installers (S3).**
8. **P2 — Repo hygiene.** `.gitattributes` **done** (LF normalization + `*.png binary`; verified all tracked text files were already LF, so no renormalization). Remaining: decide on the 5 MB wallpaper, fix `hosts.yml` desktop-entry consistency (T6), derive the node major in `languages` (T3).

## Validation results

All read-only. Run on the desktop (`my-desktop`), repo `~/Projects/ubuntu-workstations`.

| Command | Result |
|---|---|
| `git status --short` / `git diff --check` | 2 modified docs + 2 new example files; whitespace check OK |
| `git ls-files` | 144 tracked files; no `.pyc`/`.env`/key files tracked |
| Full-history blob scan (patterns: PEM, credential assignments, high-entropy, emails, IPs, Syncthing device IDs, `/home/*`; values redacted) | 56 commits, all unique blobs scanned; no private keys, no credential values, no device IDs, no public IPs; only vendor extension-UUID "emails" and historical `/home/matteo` lines (owner-approved username) |
| `git log --all --diff-filter=D --name-only` | empty — no files were ever committed then deleted |
| `git fsck --full --unreachable`, `git stash list` | no unreachable/dangling objects; no stashes |
| Tag objects `v1.0.0`–`v1.2.0` | annotated, clean messages, no personal data |
| Commit metadata `git log --all --format='%an <%ae> %cn <%ce>'` | single identity `UnPtitBelge <unptitbelge@pm.me>` (finding P1) |
| PNG chunk scan of `assets/wallpapers/desktop.png` | IHDR/IDAT/IEND only; no text/EXIF metadata |
| Markdown relative-link check (16 tracked `.md` files) | 0 broken links |
| `python3 scripts/audit-workstation.py .` | 0 errors, 4 warnings (intentional historical "Restic" references), 10 info notes; 58 YAML files parsed; exit 0 |
| `python3 -m py_compile` on all tracked `*.py` | initially all pass **except** `ansible/roles/health/files/workstation-health-check.py` (S2); after deleting the stale `files/` copies, **all pass** |
| `gitleaks detect --source . --redact` (gitleaks 8.30.1, installed from the official GitHub release with SHA-256 verified against published checksums) | 56 commits scanned, **no leaks found**, exit 0 |
| Multipass rehearsal on a clean Ubuntu 26.04 LTS VM (`ws-rehearsal`, 4 CPU / 4 GiB / 30 GiB): working tree transferred via `$HOME` (Snap-private `/tmp` cannot be read by the multipass Snap), extracted to `~/Projects/ubuntu-workstations`, `git` + `ansible-core` 2.20.1 installed, then `WORKSTATION_REHEARSAL_VM=yes ansible-playbook playbooks/rehearsal-headless.yml --limit desktop -f 1` run 3 times | Run 1 (no `--limit`, default forks): `failed=1` on the parallel `rustup` install race (T10); runs 2 and 3 with `--limit desktop -f 1`: `ok=28 changed=0 failed=0` — **idempotent** |
| Tool verification inside the rehearsal VM | `node v22.23.4`, `openjdk 25.0.5 LTS`, `rustc 1.99.1`, `uv 0.13.7`, mise pins (copilot/gemini-cli/codex/typescript) and uv tools (crewai, jupyterlab, mistral-vibe) all installed and runnable |
| `python3 scripts/audit-workstation.py .` inside the fresh VM | 0 errors, 5 warnings (intentional Restic mentions), 10 notes — same as on the desktop |
| YAML parse of new files: `*.example` inventory, `.github/workflows/ci.yml` | OK |
| `git ls-files --eol` before/after `.gitattributes` | all text files already `w/lf`, PNG `w/-text` — `.gitattributes` causes zero renormalization |
| `ansible-playbook --syntax-check` on `workstation.yml`, `validate-workstation.yml`, `rehearsal-headless.yml` (ansible-core 2.20.1) | all pass |
| `ansible-inventory -i inventory/hosts.yml --graph` | `@workstations: laptop, desktop` |
| `ansible-playbook playbooks/workstation.yml --list-tasks --limit desktop` / `--limit laptop` | 214 tasks each, no errors |
| `ansible-inventory --host desktop` | `.example` files are **not** loaded as host vars |
| `gitleaks` / `trufflehog` | gitleaks 8.30.1 installed and run (no leaks); trufflehog not used |

**Not run** (require approval/privileges): real provisioning (`-K`), `--check --diff` previews, strict validation on the machines, any network/backup operation.

## Publication checklist

- [x] LICENSE added — MIT, chosen by the auditor after owner approval to add one (replace if another license is preferred)
- [x] `SECURITY.md` added with a private disclosure contact (GitHub private reporting + `unptitbelge@pm.me`)
- [x] Commit-email decision made (P1): owner approved publishing `unptitbelge@pm.me`; no history rewrite
- [x] CI added: `.github/workflows/ci.yml` — gitleaks full-history secret scan + YAML/Python/Ansible static checks + inventory parse
- [ ] Enable **GitHub secret scanning / push protection** in the repository settings (UI-only setting, not a file) and re-run gitleaks against the published repo; expect zero findings
- [x] Stale `ansible/roles/health/files/` copies removed (S2); `py_compile` passes on all tracked `.py`
- [x] `.gitattributes` added (LF normalization, binaries untouched; no renormalization of existing files)
- [x] Example inventory files present and inert (`hosts.yml.example`, `host_vars/workstation.yml.example`)
- [x] Docs link check passes (0 broken links across all tracked md files at audit time)
- [x] Ansible syntax checks pass (3 playbooks, ansible-core 2.20.1); `--list-tasks` clean for both hosts
- [x] Local gitleaks run over full history: no leaks (re-run before commit `b1b47f3`: still no leaks)
- [x] Owner confirms hostnames + username + main email may stay public
- [x] Work committed (`b1b47f3`) and pushed; `origin/main` in sync; desktop provisioned, validated and idempotent with the new roles; monitoring re-verified healthy
- [ ] Confirm the CI workflow runs green on `main` in the GitHub Actions tab after the push
- [x] Fresh-machine rehearsal on a clean Ubuntu 26.04 Multipass VM (2026-11-04): foundation roles provisioned, second/third runs `changed=0 failed=0`, all toolchains verified working, repo audit clean; VM deleted and purged afterwards. Run with `--limit <host>`/`-f 1` (see T10). Remaining optional: a full GNOME desktop rehearsal, which needs a graphical session.
- [ ] Branch protection enabled on `main`; tags `v1.0.0`–`v1.2.0` remain annotated and untouched
- [ ] Flip repository visibility **last**, after all of the above

## Post-audit implementation update (2026-11-04, owner-approved)

The maintenance and backup system was completed so that registering a new tool is configuration-only (see `docs/DEPLOY.md` §7):

- `health`: service/timer checks are now variable-driven (`workstation_health_system_services`, `workstation_health_user_services`, `workstation_health_system_timers`).
- `weekly_report` and `desktop_alerts`: report sources render from the shared `workstation_report_sources` variable (with optional per-source `max_age_hours`); the tool-update report was added to the consolidated set.
- `tool_updates`: `workstation-tool-update-check` now also discovers outdated **uv** tools (`uv tool list --outdated`) and emits an `OVERALL` status line.
- `post_update_validation` and `apt_update_review`: package groups are variable-driven (`workstation_post_update_groups`, `workstation_apt_update_review_groups`); new post-update groups get a generic still-installed check.
- `backup`: the backup script now writes a normalized `~/.local/state/workstation-backup/status.json` record (MIGRATE.md §5 schema, `provider: proton_drive`, `dataset_id` from the new `workstation_backup_dataset_id` variable); `workstation-backup-health-check` consumes it with the legacy `last-success` stamp as fallback. Unit names remain Proton-specific (renaming is a separate reviewed migration).
- Third-party onboarding: `setup.yml.example` + `scripts/setup-workstation.py` generate a new host's inventory entry and `host_vars` from one fill-in file (`setup.local.yml`, gitignored); `--verify` runs the read-only Ansible checks. The existing `desktop`/`laptop` entries are never modified. At audit time the owner accepted publishing the machine names; **post-release they were removed from the working tree** (see the addendum below) — they remain only in Git history.
- Provider independence (owner-approved plan): `workstation_capabilities` / `workstation_providers` schema in `group_vars/all.yml`; roles live vendor-namespaced under `ansible/roles/providers/<vendor>/<name>/` (`proton/{drive,vpn,pass,mail,_deb}`, `google/{drive,mail}`, `syncthing`, `wireguard`, `keepassxc`, guidance-only `custom`), so contributors grow the project by adding a vendor directory — no playbook edits (dispatch + auto-discovery + validation in `workstation.yml`). Defaults reproduce the original Proton + Syncthing behavior exactly, so `desktop`/`laptop` are unaffected. Scope is Ubuntu 26.04 LTS only (CONTRIBUTING.md boundaries).
- Multi-setup profiles (owner-confirmed Option A): `profiles/<name>.yml` selected by `workstation_profile`, loaded at inventory level in `group_vars/all.yml` (so `host_vars` can still override per machine); the playbook validates the profile and gates foundation roles on `workstation_role_*` toggles. Starter profiles: `developer_gnome` (default = previous behavior), `minimal`, `headless`. `scripts/setup-workstation.py` accepts a `profile:` field and validates it. Adding a template = one YAML file (DEPLOY.md §8, CONTRIBUTING.md "Adding a profile"). Phases 2–4 of the owner-confirmed plan are also implemented: backup monitoring is now provider-following (`workstation_backup_monitor_service/_timer`, set by each backup provider role; the checker is a rendered template), and new built-in adapters exist — `rclone_gdrive` (backup via any rclone remote, Google Drive or SFTP/S3 to a VPS), `thunderbird` (mail, any IMAP incl. Gmail and self-hosted servers), `wireguard` (VPN), `keepassxc` (passwords) — documented with account/secret requirements and a self-hosted single-VPS example (Vaultwarden, WireGuard, rclone-over-SFTP, maddy/docker-mailserver) in `docs/PROVIDERS.md`.

All changes are read-only monitors plus additive, backward-compatible behavior; both `desktop` and `laptop` keep working, and the changes were validated with `py_compile`, template render tests, `--syntax-check`, `--list-tasks` and the repository audit script (see validation table).

**Deployment result (2026-11-04, owner-executed on `my-desktop`):** real provisioning + strict validation + idempotency run all clean (`failed=0`, second run `changed=0`), reported by the owner; commit `b1b47f3` pushed and `origin/main` synchronized (`0 0` divergence). Post-deployment monitoring verified on the desktop: all workstation timers enabled/active, 0 failed user/system units, `Linger=yes`, health/drift/backup reports `HEALTHY`/`NO DRIFT DETECTED`, and the new scripts confirmed deployed (`status.json` writer in the backup script, 4 rendered report sources, uv section, rendered package groups). `~/.local/state/workstation-backup/status.json` appears after the next scheduled backup (20:20); until then the monitor uses the legacy stamp — no alert gap.

## Conclusion

**READY WITH WARNINGS.** No sensitive data (secrets, keys, sessions, device IDs, private network identifiers) exists in the current tree or in the complete Git history — confirmed by both a manual full-blob scan and gitleaks 8.30.1 (56 commits, no leaks). The owner has approved publishing the commit email, hostnames and username. This audit added `LICENSE` (MIT), `SECURITY.md`, `CONTRIBUTING.md`, `.gitattributes`, a gitleaks CI workflow, generic example inventory files, and documentation fixes, and deleted the stale broken `health/files/` duplicates. The only remaining items before flipping visibility are confirming the CI run is green on `main` and the repository **settings** (branch protection; then visibility; then GitHub secret scanning/push protection, which appear once the repo is public). A clean-machine Multipass rehearsal was executed and passed (idempotent, toolchains verified); the desktop was then provisioned, validated and re-verified healthy with the new roles. Both `desktop` and `laptop` remain provisionable with their existing configuration.

## v1.3.0 publication addendum (2026-11-04)

The open checklist items above are now complete; the repository is **public** and released as annotated tag **`v1.3.0`**:

- GitHub secret scanning, push protection and private vulnerability reporting enabled; branch protection on `main`; Dependabot activated (`.github/dependabot.yml`: Actions + pip).
- CI (`.github/workflows/ci.yml`) runs green on the released `main`.
- Post-audit features shipped in v1.3.0: multi-setup profiles (`profiles/`), vendor-namespaced providers (`ansible/roles/providers/<vendor>/<name>/` — the paths in the findings tables above moved accordingly: `ansible/roles/proton/` → `ansible/roles/providers/proton/<component>/`, `ansible/roles/backup/` → `ansible/roles/providers/proton/drive/`), onboarding script (`setup.yml.example` + `scripts/setup-workstation.py`), and provider-following backup monitoring. Details in [PROVIDERS.md](PROVIDERS.md) and [DEPLOY.md](DEPLOY.md).
- No new sensitive data was introduced by these changes; gitleaks re-run over the full history at release time: no leaks.
- **Privacy follow-up (post-v1.3.0, owner-requested):** the two machine names were removed from the working tree and replaced with the placeholders `my-desktop` / `my-laptop` in all docs; they remain in Git history only, which the owner explicitly accepts. `workstation_device_name` is no longer stored in tracked `host_vars/*.yml`: the runtime hostname is the default machine identity (never committed), and an optional explicit pin lives in the gitignored `ansible/inventory/host_vars/<host>/local.yml` (covered by `.gitignore`; `scripts/setup-workstation.py` writes it there). The playbook's identity assertions skip placeholder (`<...>`) values.
