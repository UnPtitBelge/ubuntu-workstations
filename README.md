# Phase 24 — Ubuntu 26.04 clean-install rehearsal

This is a **VM-only rehearsal**; do not run the rehearsal playbook on your laptop.
It never runs GNOME, Docker/Containerlab, virtualization, Syncthing, Proton, or backup roles. A cloud VM does not provide your user session, GPU, KVM passthrough, or secrets. These components require separate desktop testing.

## On your laptop (Fish)

First extract the package into your existing repo and commit **only the new rehearsal playbook**. Then build the VM from committed files:

```fish
cd ~/Projects/ubuntu-workstations
tar -xzf ~/Downloads/phase24-clean-install-rehearsal.tar.gz -C .
git diff --check
git add ansible/playbooks/rehearsal-headless.yml
git commit -m "test(workstation): add disposable VM foundation rehearsal"
```

From `~/Projects/ubuntu-workstations`:

```fish
# Inspect available VMs and image before creating anything
multipass list
multipass images

# Pick a unique name; this example assumes it does not exist.
multipass launch 26.04 --name workstation-rehearsal-24 --cpus 4 --memory 8G --disk 40G

# Copy only tracked, committed source files (no .git, credentials, VM images).
git archive --format=tar HEAD | gzip > /tmp/workstation-rehearsal-source.tar.gz
multipass transfer /tmp/workstation-rehearsal-source.tar.gz workstation-rehearsal-24:/tmp/workstation-source.tar.gz

# Install Ansible and prepare the test account within the disposable VM.
multipass exec workstation-rehearsal-24 -- sudo apt-get update
multipass exec workstation-rehearsal-24 -- sudo apt-get install -y ansible-core git ca-certificates
multipass exec workstation-rehearsal-24 -- sudo useradd -m -s /bin/bash -G sudo matteo
multipass exec workstation-rehearsal-24 -- sudo mkdir -p /home/matteo/Projects/ubuntu-workstations
multipass exec workstation-rehearsal-24 -- sudo tar -xzf /tmp/workstation-source.tar.gz -C /home/matteo/Projects/ubuntu-workstations
multipass exec workstation-rehearsal-24 -- sudo chown -R matteo:matteo /home/matteo/Projects
```

**Permission escalation:** the test account `matteo` requires sudo for APT tasks. In an expendable VM only, use a temporary sudoers drop-in:

```fish
multipass exec workstation-rehearsal-24 -- sudo sh -c 'echo "matteo ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/90-workstation-rehearsal'
multipass exec workstation-rehearsal-24 -- sudo chmod 0440 /etc/sudoers.d/90-workstation-rehearsal
```

### Syntax test (non-destructive)

```fish
multipass exec workstation-rehearsal-24 -- sudo -u matteo env HOME=/home/matteo ANSIBLE_ROLES_PATH=/home/matteo/Projects/ubuntu-workstations/ansible/roles ansible-playbook -i 'localhost,' -c local /home/matteo/Projects/ubuntu-workstations/ansible/playbooks/rehearsal-headless.yml --syntax-check
```

### Optional real provisioning test (modifies the **VM**)

Review the exact roles in `rehearsal-headless.yml` first. It intentionally executes the foundation roles (`base`, `shell`, `bootstrap`, `languages`) on the new VM and **does not** touch your laptop. It might download substantial toolchains and take time.

```fish
multipass exec workstation-rehearsal-24 -- sudo -u matteo env HOME=/home/matteo WORKSTATION_REHEARSAL_VM=yes ANSIBLE_ROLES_PATH=/home/matteo/Projects/ubuntu-workstations/ansible/roles ansible-playbook -i 'localhost,' -c local /home/matteo/Projects/ubuntu-workstations/ansible/playbooks/rehearsal-headless.yml
```

Repeat the same command and aim for `changed=0` on the second run. Capture errors and fix the role instead of applying untested changes to the laptop.

Note: some existing roles may assume a graphical session, user services, or preinstalled dependencies even within the foundation. That is exactly the type of gap this rehearsal aims to reveal. The guard variable protects against accidental execution on the laptop, but is not a security boundary.

### Inspect and clean up

```fish
multipass info workstation-rehearsal-24
multipass stop workstation-rehearsal-24
```

Delete **only after** you've verified the exact VM name and you no longer need its results:

```fish
multipass delete workstation-rehearsal-24
multipass purge
```

**Warning:** `multipass purge` permanently removes *all* previously deleted Multipass instances, not just this rehearsal VM. Skip it if you have other deleted VMs you might want to recover.

## Scope of this phase

- Uses explicit Ubuntu `26.04`, not floating `lts`.
- Uses `git archive HEAD`, so uncommitted work is intentionally omitted.
- Installs to a disposable VM only, with no connected secrets or Proton session.
- Explicitly excludes GNOME and user systemd services from headless testing.
- Rehearsal tests foundation roles and second-run idempotency, **not** full desktop equivalence.
- Do not run the rehearsal playbook on your real workstation.

If any role hardcodes physical hostnames, `ansible_user` or `~` assumptions, this test may fail. Fix those separately after inspecting the failing task.
