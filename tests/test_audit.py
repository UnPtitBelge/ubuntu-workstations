"""Regression coverage for profiles and nested provider repository auditing."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AuditTests(unittest.TestCase):
    def test_profiles_and_nested_provider_defaults(self):
        with tempfile.TemporaryDirectory(prefix='workstation-audit-') as tmp:
            root = Path(tmp)
            role = root / 'ansible/roles/providers/vendor/example'
            (role / 'tasks').mkdir(parents=True)
            (role / 'defaults').mkdir()
            (root / 'profiles').mkdir()
            (root / 'ansible/inventory/group_vars').mkdir(parents=True)
            (role / 'tasks/main.yml').write_text('---\n[]\n')
            (role / 'defaults/main.yml').write_text('workstation_example: true\n')
            (root / 'ansible/inventory/group_vars/all.yml').write_text('workstation_example: false\n')
            profile = root / 'profiles/example.yml'
            profile.write_text('description: valid\n')
            command = [sys.executable, str(ROOT / 'scripts/audit-workstation.py'), str(root)]
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn('providers has no tasks/main.yml', result.stdout)
            self.assertIn('Variable workstation_example defined in multiple layers', result.stdout)
            profile.write_text('description: first\ndescription: duplicate\n')
            result = subprocess.run(command, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn('profiles/example.yml: YAML parse / duplicate-key error', result.stdout)
            self.assertNotIn('description: duplicate', result.stdout, 'Audit errors must not echo YAML values')


if __name__ == '__main__':
    unittest.main()
