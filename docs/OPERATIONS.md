# Operating your workstation

Use this guide to answer three questions: what is scheduled, what last happened,
and what you need to do. Commands are Fish-compatible and run as your ordinary
user on the machine you are checking. This guide describes repository intent;
it is not a live audit of either workstation.

## Contents

[Quick inspection commands](#quick-inspection-commands) ·
[Automatic jobs](#what-runs-automatically) ·
[Refresh checks](#refresh-checks-deliberately) ·
[Backup actions](#backups-inspect-upload-and-verify-are-different-actions) ·
[Warnings](#respond-to-a-warning) ·
[Routine maintenance](#routine-maintenance) · [Recovery](#recovery)

## Start here

Begin with the summary and scheduling commands in [Quick inspection](#quick-inspection-commands).

The summary is a snapshot of existing reports, not a fresh execution of every
check. Compare its date with the source report. A missing report means unknown
state, not healthy state. A missing helper can mean its role was skipped or the
latest repository changes have not been deployed.

### Web dashboard

After [dashboard installation](DEPLOY.md#install-only-the-dashboard), run:

```fish
workstation
```

Open the private session link printed in that terminal. The on-demand server
listens only on `127.0.0.1:8765`; `--port NUMBER` selects another port. The session
link changes on restart and should stay private. No cloud hosting, telemetry,
external fonts, frontend build or background timer is required. Ctrl+C stops
the server; it does not undo actions already started. The Textual TUI is removed.

Use the header's **Dark mode / Light mode** button to switch themes. The first
visit follows your system preference; an explicit choice is saved in browser
local storage and applied before the page renders. Both themes use stronger
text/status contrast and visible button boundaries. Eligible monitoring jobs
also show **Run check** directly in Operations; it opens the same command/effect
review and does not bypass confirmation.

| Section | Purpose |
| --- | --- |
| Overview | Local machine identity, health/backup/update summaries and attention items |
| Machines | Current local target and other inventory entries; unconnected entries have no observed health or controls |
| Setup | Forms for supported backup, development, desktop and notification settings; provider selections are inspection-only |
| Operations | Search/filter jobs, read saved reports and journals, review supported manual monitoring runs |
| Changes | Review a host-file diff, save configuration, preview effects, apply and audit |
| Activity | Running/completed/failed/unknown action outcomes, kept in memory for this server session (up to 50) |
| Lifecycle | Installation, feature changes, provider transition and recovery guidance |

The dashboard manages **only the machine serving it**. Both inventory hosts use
local execution. Remote management is deferred; run a separate dashboard on
each workstation. Ordinary browsing rereads local evidence every 30 seconds;
it does not run checks, refresh baselines, upload, download or repair anything.
The read-only demo is available with `workstation --demo` and uses only sample
data, without reading host reports, credentials or inventory.

#### Configuration workflow

1. Edit the supported fields in Setup. Draft values stay in browser memory;
   leaving/reloading the page can discard them.
2. Open Changes → Review & save. Inspect the exact host-file diff and explicitly
   confirm. Cancel leaves inventory untouched. Saving changes only
   `ansible/inventory/host_vars/<host>.yml`, preserving unrelated values,
   formatting and comments; comments inside a changed list can be replaced.
   Duplicate YAML keys and anchors/aliases require manual editing. No commit,
   push or provisioning occurs.
3. Preview the saved inventory. Review the command and confirm. Continue in
   the **launching terminal** for sudo and full Ansible output; passwords are
   never accepted or relayed in the browser.
4. Review & apply requires a successful preview of unchanged repository inputs
   in this server session. Each execution has a separate confirmation. Failed
   or repeated applies require another preview; stop at the first failed task.
5. Run the strict audit, then another preview/apply to verify idempotency.

Ansible actions are unavailable when the dashboard lacks an interactive input
terminal. Browsing and supported monitoring runs remain available. The server
permits one operation at a time; navigating away does not cancel it. Do not
start parallel provisioning in another terminal.

Supported forms cover backup/restore calendars, backup sources/exclusions,
backup timer intent, update notifications, Python versions and the GNOME,
containers, virtualization and languages role switches. Values combine the
last deployed defaults with host-file overrides, rather than fully resolved
current inventory; other overrides can take precedence. Inspect the preview.
Unknown/nonliteral values are not editable in forms. Use `--repo PATH` for a
checkout outside `~/Projects/ubuntu-workstations`.

Disabling a foundation switch skips its role; it does not uninstall packages
or stop existing services. Health/service lists may need manual changes.
Provider/profile transitions, component removal and cutovers remain manual
workflows in [Deploy](DEPLOY.md) and [Migrate](MIGRATE.md). Check mode is not an
integration or recovery test. Configuration rollback does not automatically
restore old package versions or provider data.

#### Manual job runs

Open Operations → Details → Review manual run. Read the local target, command
and effects, then explicitly confirm. Reports/journals are literal text shown
only on request and may contain private paths. Custom reports cannot introduce
executable commands. The fixed user-service allowlist includes:

| Job | Effect of a confirmed run |
| --- | --- |
| Health | Checks local disks/services and replaces the report |
| Drift | Checks selected files, replaces its report and records observed history; does not change the baseline or acknowledge drift |
| Weekly summary | Rebuilds its summary from existing reports without rerunning source checks |
| Update discovery | Queries upstream versions/cached APT candidates and replaces its report; installs nothing |
| Failure/update notifications | Reads reports, may send GNOME notifications and updates deduplication state; does not authorize upgrades |

The server rechecks intent, host and unit state immediately before execution.
Disabled, missing/masked, running or unavailable services are refused. Backup
uploads, restore drills, system package jobs, Syncthing restarts, baseline
changes and custom jobs remain inspection-only. Ansible apply can change
managed services separately, after preview and confirmation.

A completed invocation does not certify healthy evidence or notification
delivery. Systemctl waits up to 120 seconds; a timeout is **unknown**, and the
systemd job may still run. Inspect its journal before retrying. There is no
automatic retry, service restart, failure clearing or repair. Session activity
is not persistent job history; reports and journals are the underlying evidence.

#### Evidence and CLI

The dashboard and retained inspection CLI share the same collector. HEALTHY,
FAILED, STALE, UNKNOWN and DISABLED describe evidence, not action authorization.
Missing/malformed evidence, unavailable buses and unattributed legacy restore
records stay unknown. Disabled intent with a leftover enabled schedule fails.
Successful inactive oneshots are not treated as broken daemons. A timer does
not prove execution, a successful upload does not prove recovery, and Syncthing
is not backup. Notification success does not prove desktop delivery.

`~/.config/workstation/console.json` is a mode-0600 Ansible-generated intent
snapshot, not a live Git-to-host comparison. Use `--config PATH` for an override.
Updating Git alone does not update this snapshot or the installed dashboard.

```fish
workstation --status
workstation --json
workstation --detail health
workstation --logs health
workstation --dashboard --port 8765
workstation --demo
```

The first four commands read existing evidence without starting a server.
Status/JSON exit 0 when all observed items are healthy/disabled, 1 for
failed/stale/unknown evidence (or unavailable requested journal), and 2 for
argument/startup errors. Consume JSON even on exit 1. Detail/log arguments are
job IDs, listed in JSON; there is no CLI mutation command.

The API requires a per-process bearer token and same-origin requests, rejects
untrusted Host headers, serves only fixed assets, and stores reviews server-side
for up to ten minutes. Confirmations are single use; stale file/intent reviews
fail closed. No arbitrary shell execution, LAN binding or password input is
provided. Treat this as a local user tool, not a hardened multi-user service.

| Symptom | What to check |
| --- | --- |
| Old terminal interface or missing assets | Update the reviewed checkout and apply the scoped dashboard playbook on this machine |
| Connection/session error | Reopen the current private session link from the launching terminal |
| Port already used | Stop your earlier dashboard or choose another `--port` |
| Settings unavailable | Inspect the configured repository, intent snapshot and host YAML; redeploy the dashboard if needed |
| Ansible actions unavailable | Launch `workstation` from an interactive terminal |
| Wrong host/intent warning | Review local identity and matching inventory entry before redeploying the console snapshot |
| Manual run refused or failed | Inspect intent, user bus, service activity, report and journal; do not clear failures to hide them |

## Quick inspection commands

These commands inspect existing state on the **local** machine. They do not run
backups, refresh reports, install updates or apply configuration. Missing files
or units mean you need to check deployment/feature selection; they are not proof
of health. The following sections explain interpretation and actions.

### Overview

```fish
cat ~/.local/state/workstation-weekly-report/latest.txt
systemctl --user --failed --no-pager
systemctl --user list-timers --all
systemctl list-timers apt-daily.timer apt-daily-upgrade.timer
loginctl show-user (whoami) -p Linger
```

### Read saved results

```fish
cat ~/.local/state/workstation-health/latest.txt
cat ~/.local/state/workstation-drift/latest.txt
cat ~/.local/state/workstation-backup-monitor/latest.txt
cat ~/.local/state/workstation-tool-updates/latest.txt
cat ~/.local/state/workstation-post-update/latest.txt
```

Check the date inside each report; use `stat` for its file timestamp. An old
post-update success may be normal when no monitored packages changed.

### Backup evidence

The commands below use Proton. For rclone, replace `workstation-proton-backup`
with `workstation-rclone-backup` in unit names.

```fish
systemctl --user status workstation-proton-backup.timer --no-pager
systemctl --user show workstation-proton-backup.service -p Result -p ExecMainStatus
journalctl --user -u workstation-proton-backup.service -n 50 --no-pager
systemctl --user status workstation-proton-backup-restore-test.timer --no-pager
journalctl --user -u workstation-proton-backup-restore-test.service -n 50 --no-pager
jq . ~/.local/state/workstation-backup/status.json
tail -3 ~/.local/state/workstation-backup/history.jsonl
tail -3 ~/.local/state/workstation-backup/restore-tests.jsonl
```

A oneshot service can be inactive after success. Verify provider, host, dataset,
run time and restore evidence together. A timer or `last-success` stamp alone is
insufficient.

### Other useful checks

```fish
systemctl --user status syncthing.service --no-pager
journalctl --user -u workstation-post-update-validation.service -n 50 --no-pager
journalctl --user -u workstation-desktop-alerts.service -n 50 --no-pager
df -h / /home
docker system df
test -e /var/run/reboot-required; and echo 'Reboot required'; or echo 'No reboot pending'
cd ~/Projects/ubuntu-workstations
git status --short
git log -3 --oneline
```

Docker disk usage is information, not an instruction to prune. Do not share raw
journals or reports before reviewing them for private paths and account details.

## What runs automatically

These are configured defaults, in local time. Host/profile overrides, randomized
delays and whether the user manager is running affect actual execution. Use
`systemctl --user list-timers --all` for installed next/last runs. User timers
marked persistent may catch up after downtime; that does not guarantee success.

| Job | Default trigger | What it does | Evidence |
| --- | --- | --- | --- |
| Ubuntu security maintenance | System APT timers; daily policy | Refreshes package lists and installs packages from configured Ubuntu origins; no automatic reboot or dependency removal | `apt-daily.timer`, `apt-daily-upgrade.timer`; unattended-upgrades logs |
| Backup upload | Daily 20:00, up to 30m delay | Uploads selected folders and a checksum manifest; writes local run metadata | Provider backup service journal; backup `status.json` |
| Restore drill | Monthly, up to 2h delay | Downloads one small selected file into temporary storage and compares its checksum | `restore-tests.jsonl`; `verified_restore_at` |
| System health | Daily, up to 30m delay | Checks configured services, disk, APT timers and reboot requirement | `workstation-health/latest.txt` |
| Selected-file drift | Daily, up to 45m delay | Compares a small allowlist of files against the deployed baseline | `workstation-drift/latest.txt` |
| Backup health | Daily 08:00, up to 30m delay | Checks upload age, selected provider timer/service and restore-test age | `workstation-backup-monitor/latest.txt` |
| Weekly summary | Sunday 10:00, up to 20m delay | Reads configured source reports; does not rerun them | `workstation-weekly-report/latest.txt` |
| Development update discovery | Sunday 11:00, up to 30m delay | Queries mise/uv/rustup and selected APT candidates; installs nothing | `workstation-tool-updates/latest.txt` |
| Failure notifications | Every 30m, up to 5m delay | Reads reports and notifies in GNOME; suppresses repeats | `workstation-desktop-alerts.service` journal |
| Update notifications | Daily 14:00, up to 15m delay | Reads the update report and notifies; installs nothing | `workstation-tool-update-alerts.service` journal |
| Post-update validation | APT database change; 10m after boot then every 30m | Compares monitored package versions; validates changed groups when a baseline exists | `workstation-post-update/latest.txt`; service journal |

Report paths in the table are relative to `~/.local/state/`. Backup metadata is
under `~/.local/state/workstation-backup/`. The source schedules are in the
[role defaults and units](../ansible/roles/) and
[shared inventory](../ansible/inventory/group_vars/all.yml).

Syncthing is a continuously running user service, not a backup timer. Its own
GUI at <http://127.0.0.1:8384> shows peers, folders and conflicts. Pairing and
folder approval are manual.

`Linger=yes` keeps the user manager available after logout; it does not create a
GNOME session or unlock cloud credentials. Notifications require a suitable
graphical session. Background backups still require usable authentication.

## What still needs your action

- Sign in to cloud services, pair Syncthing as a unique device and approve folders.
- Review Docker/Proton package upgrades and changes to pinned development tools.
- Apply Git/Ansible changes on each machine; the other workstation is not updated remotely.
- Schedule reboots and disruptive work, resolve drift/conflicts and investigate failures.
- Verify backup coverage and recovery; migrate providers and retire old datasets explicitly.

Monitoring does not restart broken services, repair configuration, clear failures,
apply third-party upgrades, prune Docker or delete cloud data. Initial provisioning
can install packages, start services and refresh baselines; it is a separate action.

## Read the right evidence

| Question | Inspect | Interpretation |
| --- | --- | --- |
| What should this host use? | Profile, shared inventory and host overrides | Desired configuration; not installed state |
| Is the job scheduled? | Installed timer, `is-enabled`, next run | Scheduling only |
| Did the last service invocation succeed? | Journal and `Result` / `ExecMainStatus` | Job outcome; a oneshot service may be inactive after success |
| Is the result recent? | Report timestamp and underlying run timestamp | Freshness of the check and of the work are separate |
| Was a backup uploaded? | Backup service result and `checked_at` / `result` | Check the recorded host, provider and dataset too |
| Can a file be recovered? | Successful restore drill plus a chosen-file recovery test | One verified file does not prove every file or old revision is recoverable |

Normal monitor reports end with `OVERALL: HEALTHY`; drift uses
`OVERALL: NO DRIFT DETECTED`. An update report can be healthy while listing
`[AVAILABLE]` versions: discovery succeeded, but upgrades still need review.
`ATTENTION REQUIRED` means inspect the details, not rerun provisioning blindly.

Default freshness limits are 48h for daily source reports/upload age, 192h for
the weekly update-discovery report and 1080h (45 days) for verified restore age.
An old successful post-update report alone is not an error: no monitored versions
may have changed. Inspect an actual failure or missing baseline in the journal.

## Refresh checks deliberately

The quick inspection commands above only read existing state. These helpers **run checks**:
they can write local reports/baselines or query upstreams, but do not repair the
system or install upgrades. Read an existing failure before replacing its report.

| Task | Existing command | Effects and limits |
| --- | --- | --- |
| Health check | `~/.local/bin/workstation-health-check` | Writes its report; checks only configured services |
| Drift check | `~/.local/bin/workstation-drift-check` | Writes its report; covers selected files, not full Git compliance |
| Backup health | `~/.local/bin/workstation-backup-health-check` | Writes report; checks local evidence, does not upload/download |
| Rebuild summary | `~/.local/bin/workstation-weekly-report` | Reads existing source reports, writes summary |
| Discover updates including default APT packages | `systemctl --user start workstation-tool-update-check.service` | Runs deployed service arguments, queries upstreams, updates report; no installation |
| Node pin proposal | `~/.local/bin/workstation-tool-update-policy` | Queries candidates; limited to supported Node patch/minor proposals |
| Docker package simulation | `~/.local/bin/workstation-apt-update-review --group docker --plan` | Runs APT simulation against cached indexes; prints a proposal only |
| Proton package simulation | `~/.local/bin/workstation-apt-update-review --group proton --plan` | Same; Proton group currently targets VPN packages |
| Validate after an approved update | `~/.local/bin/workstation-post-update-validate --check all` | Writes report and advances version baseline only on success; checks selected groups |
| Preview failure notifications | `~/.local/bin/workstation-desktop-alerts --dry-run` | Prints proposed notifications; sends none |
| Preview update notifications | `~/.local/bin/workstation-tool-update-alerts --dry-run` | Prints proposed notifications; sends none |
| Local release assessment | `~/.local/bin/workstation-release-audit` | Writes a report; not full deployment, freshness or recovery proof |

For a missing post-update baseline, first inspect the journal and current package
state. An explicit successful `--check all` validates and records versions.
`--baseline` records versions **without validation**; it is not a failure-repair
command. `--watch` with unchanged versions does not clear an earlier failure.

`workstation-tool-update-check` without arguments omits APT package selection;
the installed service supplies it. APT candidates reflect cached package indexes.
Exact mise pins can hide newer releases from ordinary outdated checks.

## Backups: inspect, upload and verify are different actions

The default provider is `proton/drive`; `google/drive` uses rclone. Choose the
row matching your configured **and installed** provider:

| Resource | Proton | rclone |
| --- | --- | --- |
| Upload service | `workstation-proton-backup.service` | `workstation-rclone-backup.service` |
| Upload timer | `workstation-proton-backup.timer` | `workstation-rclone-backup.timer` |
| Restore timer | `workstation-proton-backup-restore-test.timer` | `workstation-rclone-backup-restore-test.timer` |
| Selection preview | `~/.local/bin/workstation-proton-backup --dry-run` | `~/.local/bin/workstation-rclone-backup --dry-run` |
| Restore drill | `~/.local/bin/workstation-proton-backup-restore-test` | `~/.local/bin/workstation-rclone-backup-restore-test` |

A selection preview can create temporary staging files but does not upload.
Starting an upload service performs a **real cloud upload**. Running a restore
drill performs a **real download** and records its result locally; it is not a
preview. For enrollment and the first upload use [Install](../TUTORIAL.md#first-installation);
for recovery and drills use [Recovery](OPERATIONS.md#recovery).

Default sources are `~/Documents` and `~/Sync`, subject to exclusions in
`workstation_backup_sources` / `workstation_backup_excludes` and host overrides.
Do not assume `~/Projects`, home configuration, Docker volumes or VM disks are
included. Proton's destination defaults to
`/my-files/Workstation-Backups/<hostname>/`; rclone uses its configured remote and
`Workstation-Backups/<hostname>/` path. Verify the record and actual destination.

The normalized `status.json` and local manifest are shared latest records.
During parallel-provider tests another run can overwrite them; use provider
journals and the append-only history to identify which run they describe. Do
not infer that a monitor's healthy result validates every provider or dataset.

## Respond to a warning

| Symptom | First step | Follow-up |
| --- | --- | --- |
| Backup stale or failed | Read backup monitor report and provider service journal | Check auth, destination, last real run and restore evidence; never reset success markers |
| Restore drill failed | Read restore-test journal and `restore-tests.jsonl` | Recover a chosen file separately; a changed local source can also cause checksum mismatch |
| Drift detected | Read the named paths and compare with managed sources | Reconcile intent before provisioning refreshes the baseline; acknowledgement is a deliberate state change |
| Update candidate available | Read discovery report, then relevant simulation/proposal | Review compatibility and service impact before changing approved configuration |
| Post-update failure | Read saved report and service journal | Diagnose the failed group before rerunning an explicit validation |
| Post-update watcher fails without a report | Inspect `workstation-post-update-validation.service` journal | Missing/invalid version baseline can fail before writing a report |
| Report missing or stale | Check its own timer and service journal | Check downtime/session conditions; rebuilding the summary does not rerun its sources |
| No GNOME notification | Inspect reports and alert journal in a logged-in session | Check delivery separately from lingering; optional `--test-notification` sends a real notification |
| Syncthing conflict or missing peer | Inspect its GUI and user-service journal | Preserve distinct identities; do not overwrite folders to resolve conflicts |

For persistent schedule/feature changes use [Deploy](DEPLOY.md), especially
[provider disabling](DEPLOY.md#provider-disabling-and-profile-changes). Stopping
a timer manually is temporary operational state; keep intended changes in Ansible.

## Routine maintenance

Use the evidence guidance and quick inspection commands above. These checklists
are review points, not additional scheduled jobs. Work on the machine being checked.

| When | Review |
| --- | --- |
| An alert arrives | Read the named report/date and journal; distinguish failed work, missed execution and stale summary. Preserve evidence, diagnose the first failure, then verify a focused fix. |
| Weekly | Read summary/source results and the last real backup; review update proposals, failed units, space, reboot requirement and Git changes. Check each workstation separately. |
| Monthly | Verify future timer runs and job outcomes, restore evidence for the intended host/dataset, Syncthing state/conflicts, backup coverage after tool/data changes and any planned reboot. |
| Quarterly or after recovery changes | Restore a chosen file separately and open/compare it; verify host destination, retention and independent credentials. Test Syncthing transfer only with both devices available, and GNOME delivery after login/logout/login. |
| After configuration/package changes | Follow [Deploy](DEPLOY.md#3-preview-apply-and-verify), inspect relevant real outcomes and run monitor self-tests where appropriate. A repository pass is not a host deployment pass. |

A fresh summary may contain old source results. Default restore freshness is 45
days, and a drill covers one file. Use [Recovery](#recovery) for a chosen-file
test. Do not reset backup markers, accept drift or reinstall working tools to
clear an alert; notification delivery is separate from job success.

### Before a release

- [ ] Review staged files for scope and secrets; repository validation passes.
- [ ] Record the exact revision and target-host deployment/audit results.
- [ ] Verify a second normal provisioning pass has `changed=0`, or document an exception.
- [ ] Verify current monitoring, scheduled job outcomes and recent restore evidence.
- [ ] Validate the other workstation after its separately approved deployment, or record it as unverified.
- [ ] Ensure the working tree is clean and the intended branch is synchronized with its remote.
- [ ] Create an annotated tag only as a separate release decision; never overwrite an existing tag.

Past release evidence belongs in [the archive](archive/README.md). It does not
establish that a newer working tree or either live host is ready for release.

## Recovery

Git/Ansible reconstructs managed configuration. Cloud copies can recover selected
files. Syncthing replicates changes and may replicate deletions. None of these
alone is a full disk image or a complete recovery plan.

### 1. Protect the data first

Stop unnecessary writes to a disk that may be failing. Preserve conflicts,
logs and still-working versions before reinstalling anything. Decide whether
you need a single file, an older revision or a machine rebuild.

Restore into a **separate directory**. Check the source host, destination and
version before replacing any live data. Recovery credentials must be accessible
from a trusted device independently of the failed workstation.

### 2. Restore a chosen file or folder

For Syncthing, inspect conflicts and `.stversions` where folder versioning was
enabled. Stop conflicting edits on peers. Earlier versions may not exist;
copy the candidate into a separate location and inspect it first.

For cloud backup, identify the provider and host-specific destination from your
configuration and saved evidence. On a replacement machine, the backup may be
under the **old** hostname, not its current hostname.

#### Proton example

With an authenticated CLI session, inspect available backups:

```fish
proton-drive filesystem list /my-files/Workstation-Backups
set restore_dir (mktemp -d "$HOME/workstation-restore.XXXXXXXX")
echo $restore_dir
```

Set the actual backup hostname and download into the separate directory. This
performs a real download:

```fish
set backup_host 'replace-with-the-backup-hostname'
proton-drive filesystem download /my-files/Workstation-Backups/$backup_host/Documents $restore_dir
```

Inspect the resulting files and compare selected originals with `cmp` or
`sha256sum` when available. Open the recovered file. If you need an older
revision, inspect provider version history; the ordinary download is not proof
that a particular historical revision was retrieved.

#### rclone

Use the enrolled remote named by `workstation_rclone_remote` and the configured
`workstation_rclone_remote_parent`. Download a chosen file to a separate directory
using that remote's verified workflow. The `google/drive` adapter can target
non-Google backends, so confirm which remote/account you are reading. Do not use
mirror/delete operations or download over a live source tree.

Record the provider, source host, remote path/version, recovered local path and
comparison/open result privately. A manifest can help reconcile selected file
counts/checksums, but is not a consistent filesystem snapshot or proof of every
older revision.

### 3. Run a restore drill deliberately

The installed monthly drill chooses a small regular file from the current
filtered local selection, downloads the remote counterpart to temporary storage
and compares SHA-256. It does not overwrite the local source or delete remote
files. It performs a real download and can write local result metadata.

Use the command matching the installed provider:

```fish
# Proton:
~/.local/bin/workstation-proton-backup-restore-test
# For rclone use instead: ~/.local/bin/workstation-rclone-backup-restore-test
```

Inspect its exit result and output, `restore-tests.jsonl`, `status.json` and the
restore service journal. If metadata is missing, inconsistent or invalid, retain
the direct verification evidence and investigate; do not forge a success marker.
Early errors may only appear in the journal. The current scripts' metadata paths
need further hardening, tracked in [TODO](TODO.md#correctness-before-more-automation).

This test covers one file that still exists locally. It does not prove recovery
of a deleted file, an older version, every dataset or a full machine. If the local
file changed since the upload, a mismatch needs investigation rather than an
automatic reupload. Perform a chosen-file recovery as well.

### 4. Rebuild after reinstall or disk replacement

1. Install supported Ubuntu, create your own user and arrange disk protection.
2. Follow [Install](../TUTORIAL.md#first-installation), keeping backup scheduling disabled during enrollment.
3. Recreate machine-local credentials; pair Syncthing as a new device unless an independently reviewed identity recovery is intended.
4. Restore selected data into separate locations; verify it before copying into live folders.
5. Re-clone development repositories and recover unpushed work separately if it was backed up.
6. Run the relevant audit/service checks and second provisioning pass; prove a new service-context upload and restore before enabling timers.

Ansible does not restore authenticated sessions, SSH keys, Syncthing private
identities, passwords, live Docker volumes, VM disks or paths outside the backup
selection. Default backup sources are Documents and Sync, not the whole home or
Projects directory. Rebuild caches/tool binaries from approved configuration;
restore irreplaceable data from independently protected sources.

### 5. Recovery limits

Filtered uploads are not immutable point-in-time snapshots. Exclusions prevent
future uploads but do not automatically remove old cloud data. A checksum match
for one file does not establish retention, whole-dataset integrity or independence
from account lockout/cloud deletion.

Keep an independent recovery path and a rollback window when changing providers.
Use [Migration](MIGRATE.md) before retiring old data or credentials. Legacy Restic
repositories/password files, if present from an earlier setup, are not used by
current backup adapters; inspect privately before any separately approved cleanup.
