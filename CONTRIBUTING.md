# Contributing

Thanks for considering a contribution to this Ubuntu workstation repository.
It is primarily a personal, opinionated configuration, but fixes, documentation
improvements, portability patches and **new providers** are welcome.

## Scope and boundaries

- **Ubuntu 26.04 LTS only for now.** Do not add distro- or release-specific
  conditionals; the repository supports exactly this platform.
- **Never commit secrets.** No credentials, tokens, private keys, Syncthing
  identities, Proton/rclone/VPN sessions, password-store exports or personal
  data. CI runs gitleaks on every push and pull request; a leak blocks the build.
- Keep changes small and reviewable: one coherent change per commit.
- The two provisioned machines (`desktop`, `laptop`) must stay provisionable
  with their existing inventory. Do not replace the working inventory with
  placeholders; add separate `.example` files for generic setups.
- Documentation lives in `docs/` and must stay accurate: proposed features must
  be labeled as not implemented (see `docs/TODO.md`, `docs/DEPLOY.md`).
- Provider changes never migrate or delete user data (see
  [MIGRATE.md](docs/MIGRATE.md)); switching a provider variable only changes
  what Ansible installs/starts.

## Workflow

1. Fork and create a branch from `main`.
2. Make your change. For Ansible changes, validate locally on the machine you
   are configuring (commands are Fish-compatible):

   ```fish
   cd ansible
   ansible-playbook playbooks/workstation.yml --syntax-check
   ansible-playbook playbooks/workstation.yml --check --diff -K --limit desktop
   # Review, then apply for real and check idempotency (second run: changed=0):
   ansible-playbook playbooks/workstation.yml -K --limit desktop
   ansible-playbook playbooks/validate-workstation.yml -e audit_enforce=true --limit desktop
   ```

   On the laptop, run the same commands on the laptop with `--limit laptop`.
3. Run the repository validation gate shared with CI (no provisioning; tests use temporary homes and simulated systemd):

   ```fish
   cd ~/Projects/ubuntu-workstations
   python3 scripts/maintenance-check.py
   gitleaks detect --source . --redact   # if gitleaks is installed locally
   ```

4. Update documentation (`README.md`, `docs/`) when behavior changes.
5. Open a pull request describing the change, the machines it was validated
   on, and the test results. Do not force-push to `main`; releases use
   annotated tags created by the maintainer after validation.

**Dependabot PRs** (Actions versions in `.github/workflows/`, Python deps in
`requirements.txt`, via `.github/dependabot.yml`) are welcome but review them
like any change: check the changelog, confirm CI stays green, and merge. They
are proposals, not automatic upgrades — nothing is installed on the
workstations without an approved commit.

## Adding a provider

Providers live in `ansible/roles/providers/`, vendor-namespaced, so the
project grows by people adding their own vendor directory:

```
ansible/roles/providers/
  <vendor>/            # one directory per vendor (or a flat dir for single-product tools)
    <name>/            # one role per provider: tasks/main.yml, defaults/main.yml, templates/, files/
    _helper/           # '_'-prefixed dirs are private helpers, never selectable
```

Rules for a new provider:

1. **No playbook edits.** The playbook auto-discovers every
   `providers/**/tasks/main.yml` and includes `providers/{{ workstation_providers.<capability> }}`.
   Set your provider in `workstation_providers.<capability>: <vendor>/<name>`
   (tests can use `-e`). Directories starting with `_` are helpers
   (e.g. `proton/_deb`) and are excluded from the provider list.
2. **Contract** (details in [MIGRATE.md](docs/MIGRATE.md) §5): declare in
   `defaults/main.yml` and record in `tasks/main.yml` (the playbook fails the
   run if a selected provider does not record it):
   `workstation_provider_supported_actions` / `workstation_provider_manual_actions`,
   written to `~/.local/state/workstation-provider/<provider>.json` by the
   "Record provider adapter contract" task (copy it from a built-in role;
   `workstation_capability` and `workstation_provider_path` are passed in).
   Implement `install` / `configure` / `health`. Implement `export` / `import` /
   `verify` only where the backend supports them — otherwise list them as
   *manual*. Never claim an unsupported operation succeeded.
3. **Health output:** write `~/.local/state/workstation-<capability>/latest.txt`
   with exactly one `OVERALL:` line and register it in `workstation_report_sources`
   so the weekly report and GNOME alerts pick it up. Backup providers must
   additionally write `~/.local/state/workstation-backup/status.json` + append
   to `history.jsonl`, upload a per-file SHA-256 `manifest.json`, deploy a
   monthly restore-drill script/timer (copy `proton/drive`), and set the
   `workstation_backup_monitor_service` / `workstation_backup_monitor_timer`
   facts to their own unit names. Extend `scripts/preflight-collect.py` with a
   read-only section for your provider (never print secrets; truncate device IDs).
4. **Secrets stay local:** tokens, keys, vault files go in `~/.config`, the
   keyring, or mode-0600 files — never in Git, never in backup sources. Pin
   downloaded artifacts with checksums (see the `proton/_deb` role).
5. **Unit naming:** use provider-specific unit names
   (e.g. `workstation-rclone-backup.*`), never rename existing units in place,
   so old and new providers can run side by side during a migration.
6. **Disable semantics:** capability `enabled: false` and provider `none` skip
   dispatch; they never implicitly stop a previous provider. Implement an explicit
   disable flag for managed units, including auxiliary timers, and test it with
   existing and absent units. Preserve data and credentials. If runtime shutdown
   is manual, list `disable` in `workstation_provider_manual_actions` rather than
   claiming support. See [DEPLOY.md](docs/DEPLOY.md#provider-disabling-and-profile-changes).
7. **Validate before opening the PR:** `--syntax-check`, `--list-tasks` with your
   provider selected via `-e`, a `--check --diff` run, the repo audit script,
   and gitleaks. Update `docs/PROVIDERS.md` (table row: capability, provider,
   role path, account/subscription, secret location).

## Adding a profile (a new "setup template")

Profiles are data, not code: one file in `profiles/<name>.yml`. The playbook
validates that the selected profile exists and fails with the list of available
ones. No playbook or role edits are needed.

Rules:

1. Copy `profiles/developer_gnome.yml` as a starting point; set `description`,
   `workstation_capabilities`, `workstation_providers`, the `workstation_role_*`
   toggles, and (if the role set changes) `workstation_health_system_services` /
   `workstation_health_user_services`.
2. Keep the legacy enable flags (`workstation_backup_enabled`,
   `workstation_syncthing_enabled`, `workstation_backup_timer_enabled`) consistent
   with the capability flags. For existing hosts, stop the previous provider
   explicitly before switching to a profile that skips it (see DEPLOY above).
3. A profile must never delete data or credentials; it only selects what Ansible
   installs/starts (migration rules: [MIGRATE.md](docs/MIGRATE.md)).
4. Ubuntu 26.04 LTS only — no distro conditionals.
5. Validate: `--syntax-check`, `--list-tasks -e workstation_profile=<name>`, a
   `--check --diff` run for your profile, the repo audit script and gitleaks.
   Document the profile in `docs/DEPLOY.md` §8 (table row) and mention it in
   `README.md` if it is a starter profile.

## Reporting security issues

See [SECURITY.md](SECURITY.md). Please do not open public issues for
vulnerabilities.
