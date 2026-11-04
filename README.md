# Ubuntu Workstations

Personal Ubuntu 26.04 LTS workstations managed with Ansible and Git. The default
setup includes GNOME, Fish/Ghostty, development tools, Docker, virtualization,
Syncthing, Proton applications, cloud backups and maintenance jobs.

**Start with [TUTORIAL.md](TUTORIAL.md)** for a walkthrough of an existing setup
or a first installation. A unified management CLI is planned; today the interface
is a set of helpers and systemd commands.

## Documentation

| Document | Use it for |
| --- | --- |
| [Tutorial](TUTORIAL.md) | Learn the workflow; install and enroll a new machine |
| [Operations](docs/OPERATIONS.md) | Automation map, inspection commands, routine maintenance, troubleshooting and recovery |
| [Deploy](docs/DEPLOY.md) | Apply configuration, choose profiles, manage identity and stop selected providers |
| [Providers](docs/PROVIDERS.md) | Available adapters and selection reference |
| [Migration](docs/MIGRATE.md) | Transfer data, verify a replacement, plan cutover and rollback |
| [Roadmap](docs/TODO.md) | Open work and the proposed CLI |
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
