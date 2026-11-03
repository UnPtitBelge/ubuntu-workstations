# Phase 23 filtered Proton backup patch

This archive replaces only `ansible/roles/backup/templates/workstation-proton-backup.sh.j2`, adds the ignore-list template and includes a small patch script. The patch script preserves all your **existing** Phase 23 variables (sources, timer, remote path) and backs up the two YAML files before modifying them.

Install (Fish shell):

```fish
cd ~/Projects/ubuntu-workstations
tar -tzf ~/Downloads/phase23-proton-filtered-safe.tar.gz
tar -xzf ~/Downloads/phase23-proton-filtered-safe.tar.gz -C .
python3 apply-phase23-filter.py
cd ansible
ansible-playbook playbooks/workstation.yml --syntax-check
ansible-playbook playbooks/workstation.yml -K
~/.local/bin/workstation-proton-backup --show-excludes
~/.local/bin/workstation-proton-backup --dry-run
```

To test actual upload, run `~/.local/bin/workstation-proton-backup` once, then confirm remote output and a test restore.

Update `workstation_backup_excludes` in `ansible/roles/backup/defaults/main.yml` to fit your projects. `.git/` is **not** excluded by default to protect local unpublished commits. If you include it, Git metadata will not be backed up. The exclude rules match at any directory level. `build/`, `dist/`, `target/`, and `*.log` might hold valuable output, so inspect the defaults and remove rules if necessary.

The Bash script stages the filtered directory using hardlinks in `~/.cache` to minimize extra disk usage. It requires sources and staging directory to reside on the same filesystem; otherwise it aborts instead of making a full second copy. It doesn't follow symlinks and is **not** a point-in-time filesystem snapshot. A file modified during upload may not be backed up consistently. The old remote files excluded going forward will **remain** in Proton Drive until manually removed; no cloud deletions occur.

After validation, delete unneeded local helper files `apply-phase23-filter.py` and `workstation-backup-excludes-defaults.yml` from the repo root before committing.
