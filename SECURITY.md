# Security Policy

## Supported versions

Security fixes are applied to the `main` branch and to the latest release tag
(currently `v1.3.0`). Older tags are kept for reference and are not maintained.

## Reporting a vulnerability

Please report suspected vulnerabilities **privately**:

- Preferred: use GitHub's private vulnerability reporting on this repository
  (Security tab → "Report a vulnerability").
- Alternative: email **unptitbelge@pm.me** (the maintainer's main GitHub email).

Do not open a public issue, discussion, or pull request for a security report.
Include the affected file/commit, reproduction steps, and impact if known.

You can expect an acknowledgement within 72 hours and a status update within
7 days. If the report is accepted, a fix is developed on a private branch,
released, and credited in the release notes if you wish.

## Scope

This repository is a personal Ansible/Git workstation configuration. It is
**expected to contain no secrets**: no credentials, tokens, private keys,
Syncthing identities, Proton sessions, or password-store data belong in the
working tree or in Git history. Automated secret scanning (gitleaks) runs in
CI on every push and pull request.

If you find a secret, a private key, or sensitive personal data anywhere in
this repository (including its Git history), treat it as a security exposure
and report it privately as above. The maintainer will treat any exposed
credential as compromised, rotate it, and — if history contains sensitive
material — publish a documented history-rewrite migration plan rather than
silently rewriting published tags.

Out of scope: vulnerabilities in upstream software installed by the roles
(Ubuntu, Docker, Proton, mise, etc.) — please report those to the respective
vendors.
