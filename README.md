# Ubuntu Workstations

Personal Ubuntu 26.04 LTS workstations managed with Ansible and Git. The default
setup includes GNOME, Fish/Ghostty, development tools, Docker, virtualization,
Syncthing, Proton applications, cloud backups and maintenance jobs.

**Start with [TUTORIAL.md](TUTORIAL.md)** for a walkthrough of an existing setup
or a first installation. `workstation` serves a local web dashboard: open the
private browser link printed in your terminal. Overview summarizes evidence;
Setup offers forms and reviewed inventory changes; Operations provides job
inspection and confirmed monitoring runs. Changes guides Ansible preview/apply,
and Activity records session outcomes. Light and dark themes keep text and
actions clear; the theme switch remembers your choice.
`workstation --status` and `workstation --json` retain lightweight CLI inspection.
See [dashboard usage](docs/OPERATIONS.md#web-dashboard) and
[installation](docs/DEPLOY.md#install-only-the-dashboard).

## Dashboard

After installation, run `workstation` and open the private browser link printed
in its terminal. Keep that terminal open for the server and any confirmed
Ansible actions; passwords and full Ansible output stay there.

To try the interface from a checkout without reading or changing host state:

```fish
python3 ansible/roles/workstation_console/files/workstation.py --demo
```

The dashboard listens only on loopback and manages the machine serving it.
Other inventory entries are shown as unconnected; remote management is deferred.
Browsing is read-only. Configuration saves and supported job runs require a
separate review and confirmation. The lightweight CLI remains available through
`workstation --status`, `--json`, `--detail JOB` and `--logs JOB`.

## Documentation

| Document | Use it for |
| --- | --- |
| [Tutorial](TUTORIAL.md) | Learn the workflow; install and enroll a new machine |
| [Operations](docs/OPERATIONS.md) | Automation map, inspection commands, routine maintenance, troubleshooting and recovery |
| [Deploy](docs/DEPLOY.md) | Apply configuration, choose profiles, manage identity and stop selected providers |
| [Providers](docs/PROVIDERS.md) | Available adapters and selection reference |
| [Migration](docs/MIGRATE.md) | Transfer data, verify a replacement, plan cutover and rollback |
| [Roadmap](docs/TODO.md) | Dashboard priorities, open work and future CLI expansion |
| [Contributing](CONTRIBUTING.md) | Repository validation and implementation rules |

[Archived records](docs/archive/README.md) retain previous release evidence and
proposals. [Security](SECURITY.md) covers vulnerability reporting;
[test coverage](tests/README.md) explains the isolated regression tests.

## How it works

Git declares intent; Ansible applies it locally; systemd schedules installed jobs;
reports/journals record outcomes; GNOME alerts draw attention to some failures.
Monitoring does not repair problems. Inventory names `desktop` and `laptop` both
execute **locally**: a laptop limit on the desktop does not manage the laptop.

`profiles/` selects features/providers, `ansible/inventory/` holds shared and
per-host settings, `ansible/playbooks/` orchestrates roles in `ansible/roles/`.
`dotfiles/` and `assets/` hold managed settings, `scripts/` holds repository tools,
and `tests/` holds isolated checks. Real hostnames, credentials and device
identities remain machine-local.

`v1.3.0` is the released baseline; the working tree has later changes. A release
tag does not certify current host state. A healthy timer is not a successful job,
a successful upload is not a verified restore, and Syncthing is not backup. Only
selected source paths are protected; verify coverage and recovery separately.
