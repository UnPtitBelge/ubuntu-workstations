# Phase 31.3 — controlled mise pin review

This role installs a **read-only** CLI to propose newer Node patch/minor
versions within the currently configured major version. It never edits
mise, Git, or Ansible and never invokes an installer.

Run: `~/.local/bin/workstation-tool-update-policy`

Approval is a human-reviewed change to the Ansible-managed version pin,
followed by normal desktop provisioning and strict validation. Java, Rust,
CLI npm packages, Docker and Proton are excluded from the automated proposal
until their version and compatibility policies are defined.
