# Phase 31.5 — Post-update validation

- Install this role after `apt_update_review` in workstation.yml.
- Initial setup: run `~/.local/bin/workstation-post-update-validate --baseline` once to record installed package versions.
- The user systemd `.path` unit watches `/var/lib/dpkg/status`. Upon subsequent APT/dpkg changes it triggers the checker; checks execute only if monitored Docker/Proton package versions changed.
- A 30-minute fallback timer rechecks installed versions and retries failed validation even if a filesystem event was missed.
- Explicit on-demand checks: `workstation-post-update-validate --check docker`, `--check proton`, or `--check all`.
- Reports: `~/.local/state/workstation-post-update/latest.txt` and user journal.
- This is read-only and does not install/roll back packages, start containers, or connect/disconnect the VPN.
- Checks Docker service, Docker API, Compose, Buildx; checks Proton VPN package installation only. It **does not** verify VPN authentication or connectivity.
- This is event-driven, best effort. An unattended update while the user manager is not running may be missed; use lingering for continuous operation. `systemd.path` is based on inotify and is not a replacement for package-manager transactional hooks.
- The baseline only advances after successful validation. If validation fails, the prior versions remain for retry on a later change or manual `--check`.
- A manual `--check` records current installed versions after success; do not run it to mask a failed automatic validation before inspecting the report.
