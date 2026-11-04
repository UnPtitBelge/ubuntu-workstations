#!/usr/bin/env python3
"""Read-only audit for the ubuntu-workstations Ansible repository.

Requires PyYAML (typically available alongside Ansible). No network or modifications.
"""
from __future__ import annotations
import argparse
import collections
import pathlib
import re
import sys

try:
    import yaml
except ImportError:
    sys.exit("PyYAML not installed. Run using the Python environment that has Ansible, or install python3-yaml.")

class UniqueLoader(yaml.SafeLoader):
    pass

def unique_mapping(loader, node):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        try:
            repeated = key in mapping
        except TypeError as exc:
            raise yaml.constructor.ConstructorError(None, None, "non-hashable mapping key", key_node.start_mark) from exc
        if repeated:
            raise yaml.constructor.ConstructorError(None, None, f"duplicate YAML key: {key!r}", key_node.start_mark)
        mapping[key] = loader.construct_object(value_node, deep=True)
    return mapping

UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)

class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info = []
    def add(self, severity, message):
        getattr(self, severity).append(message)
    def show(self):
        for title, items in (("ERROR", self.errors), ("WARN", self.warnings), ("INFO", self.info)):
            for item in items:
                print(f"[{title}] {item}")
        print(f"\nSummary: {len(self.errors)} errors, {len(self.warnings)} warnings, {len(self.info)} notes")
        return 1 if self.errors else 0

def walk_yaml(root):
    for ext in ("*.yml", "*.yaml"):
        yield from root.rglob(ext)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", default=".", help="Repository root (default: current directory)")
    args = parser.parse_args()
    root = pathlib.Path(args.repo).expanduser().resolve()
    rep = Report()
    ansible = root / "ansible"
    if not ansible.is_dir():
        parser.error(f"No ansible/ directory in {root}. Run from repo root.")
    rep.add("info", f"Read-only scan of {root}")

    data = {}
    for path in sorted(set(walk_yaml(ansible))):
        rel = path.relative_to(root)
        try:
            data[path] = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueLoader)
        except (yaml.YAMLError, UnicodeError, OSError) as exc:
            # Don't disclose file contents: errors may contain YAML snippets with secrets.
            rep.add("errors", f"{rel}: YAML parse / duplicate-key error ({type(exc).__name__}; inspect locally)")
    rep.add("info", f"Parsed {len(data)} YAML files successfully")

    roles = ansible / "roles"
    if roles.is_dir():
        names = sorted(p.name for p in roles.iterdir() if p.is_dir())
        rep.add("info", "Roles: " + (", ".join(names) if names else "none"))
        for role in roles.iterdir():
            if not role.is_dir():
                continue
            if (role / "tasks" / "main.yml").is_file():
                continue
            # Namespace directories (e.g. roles/providers/) hold roles one level deeper.
            if any((child / "tasks" / "main.yml").is_file() for child in role.iterdir() if child.is_dir()):
                continue
            rep.add("warnings", f"{role.relative_to(root)} has no tasks/main.yml")

    # Inventory duplication: overlapping variable *names* are reported, not values.
    var_paths = []
    for parent in (ansible / "inventory" / "group_vars", ansible / "inventory" / "host_vars"):
        if parent.exists():
            var_paths.extend(p for p in data if parent in p.parents)
    for path in (roles.glob("*/defaults/main.yml") if roles.exists() else []):
        if path in data:
            var_paths.append(path)
    defs = collections.defaultdict(list)
    for path in var_paths:
        doc = data.get(path)
        if isinstance(doc, dict):
            for name in doc:
                if isinstance(name, str) and name.startswith("workstation_"):
                    defs[name].append(str(path.relative_to(root)))
    for name, paths in sorted(defs.items()):
        if len(paths) > 1:
            rep.add("info", f"Variable {name} defined in multiple layers: {', '.join(paths)} (may be intentional override)")

    # Scan tracked configuration files only; do not read credential contents.
    suspicious_names = re.compile(r"(^|/)(\.env($|\.)|id_(rsa|ed25519)|.*\.(pem|key|p12|pfx)$|password($|\.)|credentials($|\.))", re.I)
    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.is_symlink():
            continue
        rel = path.relative_to(root).as_posix()
        if suspicious_names.search(rel):
            rep.add("warnings", f"Potential credential-like filename: {rel} (check git tracking; filename only)")
    obsolete = re.compile(r"restic|workstation-restic", re.I)
    text_ext = {".yml", ".yaml", ".j2", ".sh", ".md", ".ini", ".service", ".timer"}
    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.is_symlink() or path.suffix.lower() not in text_ext:
            continue
        try:
            if path.stat().st_size > 2_000_000:
                continue
            txt = path.read_text(encoding="utf-8")
        except (UnicodeError, OSError):
            continue
        if obsolete.search(txt):
            rel = path.relative_to(root).as_posix()
            rep.add("warnings", f"Restic reference: {rel} (review whether intentional historical documentation)")

    playbook = ansible / "playbooks" / "workstation.yml"
    if not playbook.exists():
        rep.add("warnings", "Missing ansible/playbooks/workstation.yml")
    else:
        rep.add("info", "Main workstation playbook present")
    if not (root / ".gitignore").exists():
        rep.add("warnings", "No .gitignore found; verify secrets and generated files are excluded")
    rep.add("info", "No files changed. Warnings are review prompts, not automatic cleanup instructions.")
    return rep.show()

if __name__ == "__main__":
    raise SystemExit(main())
