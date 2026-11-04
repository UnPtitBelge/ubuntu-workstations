# Phase 31.4: Controlled APT update review

This role installs a **read-only** helper for Docker and Proton VPN package upgrade reviews.

```text
~/.local/bin/workstation-apt-update-review --group docker --plan
~/.local/bin/workstation-apt-update-review --group proton --plan
```

`--plan` runs `apt-get -s` and prints a suggested manual command, but does not install or upgrade anything. Review the full simulation before executing any suggested command. Package versions and available APT candidates depend on the workstation's locally cached package indexes.
