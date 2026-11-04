# AGENTS.md — Ubuntu Workstations

Instructions for AI coding agents working in this repository. Read this file **before** proposing, editing, testing, or committing changes. These rules apply to the repository root and all descendants unless a more specific `AGENTS.md` intentionally narrows them.

## Project and scope

- **Project:** Personal, reproducible Ubuntu 26.04 LTS workstations managed with **Ansible + Git**.
- **Current released baseline:** `v1.2.0`. The current working tree may contain post-release changes; inspect Git rather than assuming it matches the tag.
- **Machines:** `Omnissiah-desktop` (inventory host `desktop`) and `Omnissiah-pocket` (inventory host `laptop`). The usual development machine is the desktop.
- **Shell:** **Fish**, not Bash. Give Fish-compatible *interactive commands*. A script with `#!/usr/bin/env bash` is acceptable when Bash is explicitly chosen and installed; do not present Bash syntax as Fish syntax.
- **Repo on each machine:** `~/Projects/ubuntu-workstations`. Always confirm the actual working directory, repository status, and target host.
- **Execution model:** Inventory currently uses **local provisioning**. A command with `--limit laptop` executed on the desktop does **not** remotely provision the laptop. Run Ansible on the intended machine, and use its matching limit.

## Read first

1. `README.md` — overview, supported machines, provisioning workflow.
2. `docs/WORKSTATION-CHEATSHEET.md` — established operations and diagnostic commands.
3. `docs/WORKSTATION-ROUTINE-CHECKLIST.md` — ongoing checks and release workflow.
4. `docs/DEPLOY.md` — current deployment constraints and generic-workstation target design.
5. `docs/MIGRATE.md` — provider migration policy and safeguards.
6. `docs/TODO.md` — priorities, missing features, and measurable acceptance criteria.
7. Relevant role defaults, tasks, templates, `ansible/playbooks/workstation.yml`, and inventory variables **before** editing them.

If a referenced document or command is absent, report the discrepancy. Do not invent paths, role variables, packages, unit names, or feature support.

## Operating principles

1. **Preserve working state.** Make the smallest necessary change; avoid refactoring unrelated roles or reinstalling functioning applications.
2. **Ansible/Git is the source of truth.** Prefer declarative changes to role defaults, inventory, tasks, or templates over manual configuration. A manual diagnostic or temporary fix must be followed by an Ansible reconciliation if it is meant to persist.
3. **Idempotency is a release requirement.** A second normal provisioning pass should normally finish with `failed=0`, `unreachable=0`, and `changed=0`. Investigate recurring changes rather than masking them.
4. **Read-only by default.** Audit and preview first. Do not automatically install upgrades, restart network/VPN services, reboot, prune Docker, remove provider data, rotate credentials, change login shells, or modify backups.
5. **No destructive or high-impact actions without explicit approval.** In particular: `docker system prune`, Docker volume deletion, `apt autoremove`, cloud deletions, sync-folder replacement, force-pushes, and provider cutovers.
6. **Never expose secrets.** No credentials, Proton sessions, private keys, Syncthing identities/certificates, password exports, mail archives, or raw diagnostic secrets in commits, logs shared externally, or generated artifacts. Redact sensitive outputs.
7. **Separate host identity from shared configuration.** Shared defaults belong in `ansible/inventory/group_vars/all.yml` or role defaults; legitimate host overrides belong in `ansible/inventory/host_vars/desktop.yml` and `laptop.yml`.
8. **Respect user-session boundaries.** GNOME notifications need a graphical session; systemd user units and lingering are distinct. An enabled timer does not prove the last service invocation succeeded.
9. **Do not turn monitoring into self-repair.** Health, drift, update-discovery, audit, and notification jobs must stay non-destructive unless a specific change is explicitly approved.
10. **State what you verified.** Distinguish static syntax checks, local unit tests, Ansible check mode, actual deployment, real cloud backup, and restore verification. Never claim tests ran when they did not.

## Repository map

```text
ansible/inventory/hosts.yml               # inventory names and local execution
ansible/inventory/group_vars/all.yml       # shared inventory configuration
ansible/inventory/host_vars/{desktop,laptop}.yml
ansible/playbooks/workstation.yml          # provisioning role order
ansible/playbooks/validate-workstation.yml # strict workstation audit
ansible/roles/                           # provisioning and maintenance roles
scripts/                                 # repository utilities
assets/                                  # optional versioned appearance assets
docs/README*                             # consult actual filenames
README.md
AGENTS.md
```

Existing role families include workstation foundation (hardware, base, shell, bootstrap, languages, containers, virtualization, gnome), data/services (syncthing, proton, backup), and maintenance (security updates, health, drift, backup monitoring, weekly report, desktop alerts, tool updates, update policies/reviews, post-update validation, release audit). **Inspect the current playbook for authoritative role names/order.**

## Change workflow

### 1. Inspect before editing

```fish
cd ~/Projects/ubuntu-workstations
git status --short
git branch --show-current
git log -3 --oneline
rg -n 'relevant_variable_or_task' ansible
```

Check existing role defaults and higher-precedence inventory overrides. When an application unexpectedly reappears, inspect **both** its Ansible declaration and existing user configuration (for example `~/.config/mise/config.toml`). Do not assume uninstalling a tool removes its declarative request.

### 2. Keep changes focused

- One coherent feature/fix per change; preserve role ordering and conditional guards.
- Prefer explicit variables and reusable templates rather than hard-coded hostnames or filenames.
- Do not mutate release tags or rewrite history to fix working-tree issues.
- Avoid extra scheduling loops when existing systemd timers can be reused.
- Validate any Python helper with `python3 -m py_compile`; validate YAML/Ansible before provisioning.
- If packaging artifacts, build **actual files**, inspect archive contents, and test extraction and executable syntax before distributing. Do not generate Python through nested quoted Fish/Python snippets when an ordinary file or archive will do.

### 3. Validate on the machine being configured

The examples below target the desktop. On the laptop, run them *on the laptop* with `--limit laptop`.

```fish
cd ~/Projects/ubuntu-workstations/ansible
ansible-playbook playbooks/workstation.yml --syntax-check
ansible-playbook playbooks/workstation.yml --check --diff -K --limit desktop
# Review the preview; then explicitly approve real deployment:
ansible-playbook playbooks/workstation.yml -K --limit desktop
ansible-playbook playbooks/validate-workstation.yml -e audit_enforce=true --limit desktop
# Idempotency check:
ansible-playbook playbooks/workstation.yml -K --limit desktop
```

`--check` is not a full integration test: roles may skip first-install or repository-bootstrap tasks. If a real run fails, stop at the **first failed task** and diagnose that task; don't rerun unrelated installers or disable assertions just to get a green recap.

### 4. Inspect effects and commit deliberately

```fish
cd ~/Projects/ubuntu-workstations
git diff --check
git status --short
git diff --stat
git diff
# Stage only reviewed files, then inspect the staged patch:
git diff --cached --check
git diff --cached
```

Never auto-commit/push/tag as part of a provisioning role. Before pushing, confirm the intended branch and inspect staged files for secrets. Apply reviewed changes to the other workstation separately; validate on each machine. Releases use annotated tags only after a clean working tree, strict audit, and synchronized remote branch.

## Components and safety boundaries

### Backup and recovery

- Backups currently use the **Proton Drive CLI** and filtered, host-specific destinations under `/my-files/Workstation-Backups/<hostname>/`.
- Both workstation backup timers are intended to be enabled through Ansible; check host overrides and actual unit status if a monitor fails.
- **Syncthing is synchronization, not backup.** Preserve distinct device identities; do not overwrite shared folders or resolve conflicts unilaterally.
- A successful backup command/timer or `last-success` timestamp does **not** prove recoverability. Test restoring a file to a **separate** location; compare contents and confirm the correct host's dataset.
- Do not run a real upload, delete remote files, or reset success markers simply to make monitoring appear healthy.

### Updates

- Ubuntu security updates are unattended with **automatic reboot disabled**. Third-party Docker and Proton package upgrades remain approval-based.
- mise, Node, Java, Rust, npm CLI tools, Docker, and Proton versions must remain aligned with approved Ansible intent.
- Read-only review helpers include `workstation-tool-update-check`, `workstation-tool-update-policy`, and `workstation-apt-update-review --group docker|proton --plan`.
- Before approved Docker changes, inspect active containers, APT simulation, dependency changes, and expected daemon restart; validate Docker API/Compose/Buildx afterward.
- Never equate an APT candidate with an approved update.

### Monitoring and alerts

- User timers monitor health, selected-file drift, backup freshness, reports, update discovery, and desktop notifications. Consult `systemctl --user list-timers --all` and relevant `journalctl --user -u <unit>` logs.
- Selected-file drift detection is **not** full Git-to-host compliance; routine provisioning may refresh its baseline. Preserve and investigate unexpected differences.
- GNOME notifications require a suitable active graphical session. `Linger=yes` keeps the user service manager available after logout; it does not create a graphical session or guarantee cloud authentication.
- Post-update validation may legitimately have an old or missing successful report if no monitored package changed; don't alert on staleness alone. Alert on actual failure.

## Provider portability: current state versus target

The repository **currently** has provider-specific Proton roles and monitoring. A generic capability/provider interface is **proposed, not implemented**. Follow `docs/DEPLOY.md`, `docs/MIGRATE.md`, and `docs/TODO.md` when designing changes.

Prefer capability boundaries such as **backup**, **file sync**, **VPN**, **mail**, and **password manager** over a single provider-owned monolith. Future adapters should document supported `install`, `configure`, `health`, `export`, `import`, `verify`, and `disable` operations; unsupported operations must be clearly marked manual.

Changing a provider variable must **never implicitly migrate, erase, or decommission** another provider. Migration should follow: inventory → independent backup/restore proof → parallel setup → transfer → verification → explicit cutover → observation → separately approved decommissioning. Preserve encryption, metadata, identities, retention, and a rollback path.

## Agent collaboration and handoff

When working with other agents, include in each handoff:

- Goal, scope, affected machine(s), and current Git branch/commit.
- Files examined or changed and the reason for each change.
- Exact tests **actually run**, their results, and any skipped tests.
- Risks, machine-specific assumptions, outstanding questions, and rollback instructions.
- Whether any deployment, backup upload, commit, push, or release tag occurred.

Agents should not run concurrently against the **same working tree** or machine configuration without isolation (separate branches/worktrees and explicit ownership). Never delegate secrets or live infrastructure modifications without authorization. Request approval for network-affecting or destructive operations and for promotion to the second workstation.

## Definition of done

A change is ready to merge/release when it has a clear requirement, a minimal reviewed diff, no secrets, valid syntax, appropriate tests, a successful target-machine deployment when applicable, a clean strict audit, idempotency, updated documentation (including TODO/DEPLOY/MIGRATE where relevant), and a reversible rollout plan. If any of these are not verified, say so explicitly.
