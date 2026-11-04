# Contributing

Thanks for considering a contribution to this Ubuntu workstation repository.
It is primarily a personal, opinionated configuration, but fixes, documentation
improvements and portability patches are welcome.

## Ground rules

- **Never commit secrets.** No credentials, tokens, private keys, Syncthing
  identities, Proton session data, password-store exports or personal data
  beyond what is already public. CI runs gitleaks on every push and pull
  request; a leak blocks the build.
- Keep changes small and reviewable: one coherent change per commit.
- The two provisioned machines (`desktop`, `laptop`) must stay provisionable
  with their existing inventory. Do not replace the working inventory with
  placeholders; add separate `.example` files for generic setups.
- Documentation lives in `docs/` and must stay accurate: proposed features
  must be labeled as not implemented (see `docs/TODO.md`, `docs/DEPLOY.md`).

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
3. Run the repository-level read-only checks:

   ```fish
   cd ~/Projects/ubuntu-workstations
   python3 scripts/audit-workstation.py .
   gitleaks detect --source . --redact   # if gitleaks is installed locally
   ```

4. Update documentation (`README.md`, `docs/`) when behavior changes.
5. Open a pull request describing the change, the machines it was validated
   on, and the test results. Do not force-push to `main`; releases use
   annotated tags created by the maintainer after validation.

## Reporting security issues

See [SECURITY.md](SECURITY.md). Please do not open public issues for
vulnerabilities.
