# Phase 27 — Repository audit and cleanup

This phase is **read-only until you explicitly decide on changes**. It does not run provisioning, reinstall packages, or rewrite working roles.

## 1. Baseline

From the repository root, using Fish:

```fish
cd ~/Projects/ubuntu-workstations
git status --short
git log -1 --oneline
```

If there are uncommitted changes, review them before any cleanup. Don't indiscriminately reset the working tree.

## 2. Static scan

```fish
python3 scripts/audit-workstation.py .
```

This checks YAML parse errors and duplicate YAML keys, role layout, overlapping variable names, obsolete Restic references, and potentially sensitive filenames. An override in `host_vars` is often **intentional**; a warning is not proof of a bug. The tool neither writes files nor searches file contents for passwords.

## 3. Ansible checks

Run from `ansible/`:

```fish
cd ansible
ansible-inventory --graph
ansible-playbook playbooks/workstation.yml --syntax-check
ansible-playbook playbooks/validate-workstation.yml --syntax-check
ansible-playbook playbooks/validate-workstation.yml -e audit_enforce=true --limit laptop
```

If `ansible-lint` is installed, also run `ansible-lint playbooks/workstation.yml`. Do not automatically apply lint suggestions that would change runtime semantics.

## 4. Verify Git safety

From repo root:

```fish
cd ~/Projects/ubuntu-workstations
git ls-files | grep -Ei '(^|/)(\.env|id_rsa|id_ed25519|password|credentials)(\.|$)|\.(pem|p12|pfx|key)$'
git diff --check
```

The `git ls-files` command prints **filenames only**. Check any reported files privately; avoid publishing them. `.gitignore` does not untrack files already committed.

## 5. Runtime idempotency

With your GNOME session active:

```fish
cd ~/Projects/ubuntu-workstations/ansible
ansible-playbook playbooks/workstation.yml --check --diff -K --limit laptop
```

Check mode is a preview, not proof of idempotency. A real second provisioning run is needed for that; run it only when you are comfortable applying the configured roles. Watch for timers, package updates, and session-dependent tasks.

## 6. Review in small commits

Review each finding, then make one focused change at a time. Prioritize broken checks, secrets accidentally tracked, stale Restic tasks that actually execute, and duplicate settings that cause drift. **Do not delete historical documentation or intentionally overridden inventory variables automatically.** Retest and commit each change separately.

## Completion criteria

- Static audit has no unexplained errors.
- Playbook syntax checks and strict health validation pass.
- No secrets are accidentally tracked in Git.
- Provisioning remains idempotent (second real run `changed=0`).
- All intentional per-host differences remain explicit.
