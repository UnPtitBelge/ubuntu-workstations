#!/bin/sh

set -eu

echo "==> Installing workstation prerequisites"

sudo apt-get update

sudo apt-get install -y \
    ca-certificates \
    curl \
    git \
    ansible-core

echo
echo "==> Bootstrap prerequisites installed"
echo
echo "Next steps:"
echo "  1. Clone your workstation repository."
echo "  2. Configure this machine in the Ansible inventory."
echo "  3. Run the workstation playbook."
