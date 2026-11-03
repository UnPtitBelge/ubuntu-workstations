# Phase 22 — Read-only Ubuntu workstation audit

Extract this package at the repository root. It **adds** `ansible/playbooks/validate-workstation.yml` and does not alter existing roles or the provisioning playbook.

```fish
cd ~/Projects/ubuntu-workstations/ansible
ansible-playbook playbooks/validate-workstation.yml --syntax-check
ansible-playbook playbooks/validate-workstation.yml
```

If your inventory is not automatically loaded from `ansible.cfg`, pass `-i inventory/hosts.yml`.

The audit is **read-only**. It checks software visibility in a path that includes user-managed mise, uv and rustup binaries; service status; GNOME appearance and enabled extensions; Syncthing folder; KVM availability; and installed Proton DEB packages. It deliberately does not contact Proton APIs, access passwords, inspect Syncthing's credentials, or modify any files or services.

Missing commands and unavailable services are shown as findings but do not fail the default audit. To make it a gating check:

```fish
ansible-playbook playbooks/validate-workstation.yml -e audit_enforce=true
```

Edit the variables at the top of the audit playbook if you customize your desktop theme or required tools. The audit checks only shortcut **paths**, not whether the shortcuts launch the expected command; we deliberately avoid invoking applications. It checks the installed Proton DEB package list, not whether you can sign in.

Run it as the logged-in desktop user, while a GNOME session is active. Commands probing GUI/session services may report unavailable if run over headless SSH. The playbook uses read-only `command`/`shell` probes, with `changed_when: false` and `check_mode: false` to ensure they run even under `--check`; no state-changing Ansible modules are used. In an Ansible recap, fact-gathering may create local temporary files as Ansible normally does, but the managed workstation configuration is not changed.

To check it after customization:

```fish
ansible-playbook playbooks/validate-workstation.yml -e audit_enforce=true
```

Commit only after the output matches your intended workstation configuration.
