# Portable Fish + Ghostty + Starship workstation baseline

Copy `dotfiles/` and `ansible/roles/shell/tasks/main.yml` into matching locations in your existing `ubuntu-workstations` repository. These replace the current shell role; keep your existing inventory, playbook and group variables.

Before deploying, inspect diffs and back up existing files. The role backs up files it overwrites, but does not remove unmanaged Fish files. **Especially inspect `~/.config/fish/conf.d/rustup.fish` and all other old init files for duplicate setup.**

The deployment assumes Ansible connects as the target regular user and uses `become` only for APT.

The profile preserves the source WhiteSur palette, Ghostty splits, Starship modules and core Fish shortcuts. It removes pyenv fragments, a forced TERM, the hardcoded username, and the quick-terminal binding that GNOME does not support.

Some Fish aliases from the original complete `config.fish` were not available in this specific archive. The new file is a portable baseline rather than a guaranteed exhaustive transcription. Compare against the current configuration before replacement.

The Ghostty font requires JetBrainsMono Nerd Font Mono installed on both workstations; otherwise change the font-family setting to a font available on both.

Validate with `fish -n path/to/config.fish`, `python3 -m tomllib` for the TOML files, and Ghostty's `+validate-config` command if supported by your installed build. Test Ansible with `--check --diff -K` first.
