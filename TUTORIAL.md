# Tutorial: understand and manage your workstation

Start here for a guided path through this setup. If the machine is already
configured, follow sections 1–5. For a new machine, start with
[First installation](#first-installation), then return to the status checks.
Commands are Fish-compatible. Read each step's effect before running it; this
is a walkthrough, not a script to paste and execute all at once.

[Identify the machine](#1-confirm-which-machine-and-revision-you-are-using) ·
[Read status](#2-read-existing-results-before-running-more-checks) ·
[Inspect backups](#3-inspect-backup-evidence) ·
[Choose actions](#4-choose-an-action-deliberately) ·
[Routine](#5-establish-a-manageable-routine) · [Install](#first-installation)

## 1. Confirm which machine and revision you are using

```fish
cd ~/Projects/ubuntu-workstations
pwd
hostname
git status --short
git branch --show-current
git log -1 --oneline
```

Inventory names `desktop` and `laptop` both execute **locally**. A laptop limit
on the desktop does not manage the laptop. Keep real hostnames/identities local.
A new Git revision does not mean it has been applied to this machine.

The setup has four layers: Git/Ansible declares intent, installed systemd units
schedule work, helpers produce reports, and notifications draw attention to
some results. The `workstation` TUI brings those local observations together;
it does not run jobs or repair failures.

## 2. Read existing results before running more checks

If the console is installed, start here:

```fish
workstation
```

Use Up/Down (or j/k) to select, Space for the saved report (Enter also works),
`l` for the selected journal, `r` to reread existing evidence, `?` for help and `q` to quit. Rereading
never runs a check/upload/restore. For a single noninteractive snapshot use
`workstation --status` or `workstation --json`. Logs and full reports are shown
only on request and may contain private paths.

If the command is missing, follow [console-only installation](docs/DEPLOY.md#install-only-the-monitoring-console).
You can also inspect the underlying evidence directly:

```fish
cat ~/.local/state/workstation-weekly-report/latest.txt
systemctl --user --failed --no-pager
systemctl --user list-timers --all
```

Check the summary date and the dates of its source reports. It reads existing
results; it does not rerun all checks. Missing is unknown, not healthy. A future
timer run is scheduling evidence, not proof of a successful previous job.

Use the [automation table](docs/OPERATIONS.md#what-runs-automatically) to see what
runs, when and where the evidence is stored. Ubuntu maintenance and backup jobs
can make changes automatically; monitors discover/report problems and do not
repair them. Docker/Proton upgrades, runtime pin changes, reboots, sign-in and
provider migrations still need deliberate action.

## 3. Inspect backup evidence

For the default Proton provider:

```fish
cat ~/.local/state/workstation-backup-monitor/latest.txt
systemctl --user show workstation-proton-backup.service -p Result -p ExecMainStatus
journalctl --user -u workstation-proton-backup.service -n 50 --no-pager
jq . ~/.local/state/workstation-backup/status.json
```

For rclone, use `workstation-rclone-backup.service`. Verify the host, provider,
dataset and time; do not trust a green timer alone. A successful upload does not
prove a restore. Shared latest metadata has known limitations, tracked in the
[roadmap](docs/TODO.md#correctness-before-more-automation).

Default sources are Documents and Sync, with exclusions. Do not assume Projects,
Docker volumes, VM disks or the whole home directory are protected. Use the
[backup reference](docs/OPERATIONS.md#backups-inspect-upload-and-verify-are-different-actions)
for selection previews and the [recovery procedure](docs/OPERATIONS.md#recovery)
for a deliberate download into a separate location.

## 4. Choose an action deliberately

| Intent | Next step | Effect |
| --- | --- | --- |
| Read more detail | [Inspection commands](docs/OPERATIONS.md#quick-inspection-commands) | Reads saved reports, units and journals |
| Refresh a check | [Helper reference](docs/OPERATIONS.md#refresh-checks-deliberately) | Can query upstreams and replace local reports/baselines; installs nothing |
| Upload or test recovery | [Backup actions](docs/OPERATIONS.md#backups-inspect-upload-and-verify-are-different-actions) / [Recovery](docs/OPERATIONS.md#recovery) | A real cloud upload or download, not an ordinary status check |
| Apply approved configuration | [Deploy §3](docs/DEPLOY.md#3-preview-apply-and-verify) | Preview first; real execution changes packages/configuration and may start jobs |
| Replace a provider | [Migration](docs/MIGRATE.md) | Explicit transfer, verification, cutover and rollback planning |

Read the failure before rerunning a helper that overwrites its report. Never
reset success markers, acknowledge drift or reinstall healthy applications just
to make status look green. Keep persistent changes in Ansible/Git.

## 5. Establish a manageable routine

Use the [routine checklist](docs/OPERATIONS.md#routine-maintenance): investigate
alerts when they arrive, review results weekly, check restore evidence monthly
and recover a chosen file periodically. Verify each workstation separately.

When changing configuration, follow the one canonical workflow in Deploy:
preview → reviewed real apply → relevant validation → second normal run.
A repository test pass is not host health, and check mode is not idempotency.

## First installation

This section combines prerequisite setup and manual enrollment. The detailed
configuration reference remains [Deploy](docs/DEPLOY.md).

### 1. Prepare the machine

Install Ubuntu 26.04 LTS, create your ordinary user account, arrange disk
protection and independent backups of existing data, and verify networking/APT.
Use your own login; never copy another machine's credentials or identity.
For the full desktop profile, provision from its logged-in GNOME session.

Install prerequisites on this machine:

```fish
sudo apt-get update
sudo apt-get install -y git ansible-core ca-certificates
mkdir -p ~/Projects
```

Clone your verified repository URL into `~/Projects/ubuntu-workstations`. Use an
existing clone if present; do not clone over it or put access tokens in commands.
Check the [minimum versions and identity rules](docs/DEPLOY.md#2-prerequisites-and-machine-identity).
If privilege escalation fails, inspect the sudo implementation rather than
weakening permissions; see [compatibility](docs/DEPLOY.md#sudo-compatibility).

### 2. Choose inventory and profile

For the existing machines, use the existing `desktop` or `laptop` entry on the
matching physical machine. Both entries already exist and execute locally.
Review shared settings and host overrides instead of recreating their entries.

For a new inventory host, fill in the template:

```fish
cd ~/Projects/ubuntu-workstations
cp setup.yml.example setup.local.yml
$EDITOR setup.local.yml
python3 scripts/setup-workstation.py --verify
```

The generator writes the host entry, shared-safe host variables and a gitignored
local identity file **before** verification. `--verify` is not a preview of those
writes. It does not run provisioning. Review its output and Git diff; keep
`setup.local.yml` and local identity files out of Git.

Choose a [profile](docs/DEPLOY.md#8-profiles) and [providers](docs/PROVIDERS.md). Review
backup source paths/exclusions, hardware settings and service expectations.
Keep `workstation_backup_timer_enabled: false` during first enrollment until an
upload and separate restore have succeeded. Do not assume reduced profiles are
free of all desktop packages or have a complete profile-aware strict audit.

### 3. Provision

Follow [Deploy §3](docs/DEPLOY.md#3-preview-apply-and-verify) on the new machine, with
its matching inventory limit. Review the preview before applying. GNOME tasks
skipped because there is no suitable session do not prove desktop completion.

Some first-install tasks need real execution and authenticated cloud services
need later enrollment. Stop at the first failure; avoid reinstalling healthy
tools or bypassing assertions.

### 4. Enroll services locally

| Selected service | Manual enrollment |
| --- | --- |
| Proton Drive | `proton-drive auth login`; verify access with `proton-drive filesystem list /my-files`; precreate the configured host-specific destination |
| rclone backup | `rclone config` for the remote named by `workstation_rclone_remote`; verify its configured destination and account access |
| Syncthing | Open <http://127.0.0.1:8384>, verify this new device's identity, pair it and approve only intended folders |
| Proton VPN / Mail / Pass | Sign in through the installed applications and verify the required behavior |
| WireGuard | Supply the machine's private peer configuration as described in [Providers](docs/PROVIDERS.md); test routing/DNS deliberately |
| Thunderbird / KeePassXC | Set up accounts or create/open the vault locally; verify access and a separate recovery path |

Never copy Syncthing certificates, private keys, cloud sessions or keyrings from
another workstation. GUI login does not by itself establish unattended systemd
access to the same credentials.

### 5. Prove backup and recovery before enabling scheduling

Use the provider-specific [selection preview](docs/OPERATIONS.md#backups-inspect-upload-and-verify-are-different-actions).
Confirm sources, exclusions and the correct host destination. Start with a small
non-sensitive dataset if appropriate.

Then deliberately run one **real upload** through the installed provider service
and inspect its journal/result. For Proton, that action is:

```fish
systemctl --user start workstation-proton-backup.service
```

For rclone, the corresponding unit is `workstation-rclone-backup.service`.
This writes cloud data; it is not a health probe. Follow [Recovery](docs/OPERATIONS.md#recovery)
to download and verify a separate file. Check that status/history evidence is
valid and identifies the correct host/provider/dataset.

After acceptance, set `workstation_backup_timer_enabled: true` in approved
configuration and follow Deploy again. Verify both backup and restore timers and
a genuine scheduled service outcome, not just enablement.

### 6. Record acceptance

Record the Git revision, selected profile/providers, deployment and strict-audit
results, second-pass changes, graphical checks, service-context backup result
and recovery evidence in a private installation log. Record skipped checks too.
For post-update monitoring, inspect any baseline error and perform a deliberate
successful validation as described in [Operations](docs/OPERATIONS.md#refresh-checks-deliberately).

A foundation VM rehearsal uses [rehearsal-headless.yml](ansible/playbooks/rehearsal-headless.yml)
and requires `WORKSTATION_REHEARSAL_VM=yes` inside a disposable VM. It covers
base/shell/bootstrap/languages only. Use a single matching inventory limit;
multiple local inventory entries in one VM can race on the same home directory.
It is not proof of GNOME, full profiles or cloud enrollment.
