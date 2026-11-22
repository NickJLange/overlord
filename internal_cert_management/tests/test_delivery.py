#!/usr/bin/env python3
"""Exercise delivery scripts and Quadlet installation without production access.

Run with: python3 -m unittest discover -s tests -p 'test_*.py' -v
"""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cert-delivery-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = self.root / "app"
        shutil.copytree(PROJECT / "scripts", self.app / "scripts")
        self.ansible = self.root / "ansible"
        self.ansible.mkdir()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.executable("ansible-playbook", "exit \"${PLAYBOOK_STATUS:-0}\"\n")
        self.executable("lego", "exit 0\n")
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}")
        self.config()

    def executable(self, name, source):
        path = self.bin / name
        path.write_text("#!/bin/bash\nset -e\n" + source)
        path.chmod(0o755)

    def config(self, **overrides):
        values = {
            "REPO_PATH": str(self.root),
            "ANSIBLE_PATH": str(self.ansible),
            "ANSIBLE_INVENTORY": "test.inventory",
            "VENV_PATH": str(self.root / "no-venv"),
            "SUBDOMAINS_ENDPOINTS": "east west",
            "CERT_TYPES_ENDPOINTS": "ec256",
            "DOMAIN_SUFFIX": "example.test",
            "HOSTLIST_VAULT": "vault.example.test",
            "SUBDOMAINS_VAULT": "east.example.test",
            "CERT_TYPES_VAULT": "ec256",
            "VAULT_CERT_USER": "test-reader",
            "ADMIN_EMAIL": "test@example.test",
            "LEGO_DNS_PROVIDER": "test",
            "LEGO_DNS_RESOLVERS": "127.0.0.1:53",
            "SUBDOMAINS_EC256": "east.example.test",
            "SUBDOMAINS_RSA2048": "router.west.example.test",
        }
        values.update(overrides)
        (self.app / ".env").write_text(
            "".join(f"export {key}='{value}'\n" for key, value in values.items())
        )

    def task(self, role, name, content="---\n- debug: msg=test\n"):
        path = self.ansible / "roles" / role / "tasks" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def run_script(self, name, status=0, **env):
        result = subprocess.run(
            ["bash", str(self.app / "scripts" / name)],
            env=dict(self.env, **env), text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, status, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def test_linux_rejects_missing_empty_or_wrong_task_entrypoint(self):
        for fixture in ("missing", "empty-directory", "wrong-file", "empty-file"):
            with self.subTest(fixture=fixture):
                shutil.rmtree(self.ansible / "roles", ignore_errors=True)
                if fixture != "missing":
                    tasks = self.ansible / "roles/internal_dns_vault/tasks"
                    tasks.mkdir(parents=True)
                    if fixture == "wrong-file":
                        (tasks / "README.md").write_text("not an Ansible task")
                    if fixture == "empty-file":
                        (tasks / "install_certs_remote.yml").touch()
                output = self.run_script("update_linux.sh", status=1)
                self.assertNotIn("completed successfully", output)
                self.assertNotIn("<overlord>", output)
                self.assertIn(str(self.root), output)

    def test_linux_propagates_delivery_failure(self):
        self.task("internal_dns_vault", "install_certs_remote.yml")
        self.run_script("update_linux.sh")
        self.run_script("update_linux.sh", status=1, PLAYBOOK_STATUS="2")

    def test_linux_selects_certpush_even_when_environment_selects_admin(self):
        self.task("internal_dns_vault", "install_certs_remote.yml")
        # Substitute the external CLI boundary, checking the connection identity
        # and target group that the real orchestration script selects.
        self.executable("ansible-playbook", '''
expected="ansible_user=${EXPECTED_PUSH_USER:-certpush}"
case " $* " in *" -e $expected "*) ;; *) exit 90 ;; esac
case " $* " in *" --limit east_linux:!excluded-host "*|*" --limit west_linux:!excluded-host "*) ;; *) exit 91 ;; esac
''')
        self.config(LINUX_HOSTS_EXCLUDE="excluded-host")
        self.run_script("update_linux.sh", ANSIBLE_REMOTE_USER="admin")
        self.config(LINUX_HOSTS_EXCLUDE="excluded-host", CERT_PUSH_USER="custom-push")
        self.run_script("update_linux.sh", ANSIBLE_REMOTE_USER="admin", EXPECTED_PUSH_USER="custom-push")

    def test_vault_upload_needs_only_its_own_role_even_for_udm_secrets(self):
        self.task("internal_dns_vault", "install_certs_vault.yml")
        self.config(SUBDOMAINS_VAULT_UDM="router.west.example.test", CERT_TYPES_VAULT_UDM="rsa2048")
        self.run_script("upload-to-vault.sh")
        self.run_script("upload-to-vault.sh", status=1, PLAYBOOK_STATUS="2")
        (self.ansible / "roles/internal_dns_vault/tasks/install_certs_vault.yml").unlink()
        self.run_script("upload-to-vault.sh", status=1)

    def test_udm_exclusions_do_not_require_an_ansible_checkout(self):
        shutil.rmtree(self.ansible)
        self.config(SUBDOMAINS_UDM_EXCLUDE="west east")
        output = self.run_script("update_udm.sh")
        self.assertIn("Skipping UDM for east", output)
        self.assertIn("Skipping UDM for west", output)

    def test_udm_active_target_requires_its_entrypoint(self):
        self.config(SUBDOMAINS_UDM_EXCLUDE="east")
        self.task("udm-pro-configure", "README.md")
        self.run_script("update_udm.sh", status=1)
        self.task("udm-pro-configure", "main.yml")
        self.run_script("update_udm.sh")
        self.run_script("update_udm.sh", status=1, PLAYBOOK_STATUS="2")

    def test_staged_certificates_remain_readable_after_tree_relocation(self):
        certificates = self.app / "lego-data/certificates"
        certificates.mkdir(parents=True)
        names = ("_.east.example.test", "router.west.example.test")
        for name in names:
            for ext in ("crt", "key", "issuer.crt"):
                (certificates / f"{name}.{ext}").write_text(f"{name}:{ext}")
        self.run_script("lego.sh")
        self.run_script("lego.sh")  # Existing links can be refreshed safely.
        relocated = self.root / "relocated"
        self.app.rename(relocated)
        for domain, algorithm, name in (
            ("east.example.test", "ec256", names[0]),
            ("router.west.example.test", "rsa2048", names[1]),
        ):
            for ext in ("crt", "key", "issuer.crt"):
                link = relocated / f"lego-data/{domain}/{algorithm}/{name}.{ext}"
                self.assertTrue(link.is_symlink())
                self.assertFalse(os.path.isabs(os.readlink(link)))
                self.assertEqual(link.read_text(), f"{name}:{ext}")

    def git(self, *args, cwd=None):
        return subprocess.run(
            ["git", *args], cwd=cwd, env=self.env,
            text=True, capture_output=True, check=True,
        ).stdout.strip()

    def commit(self, repo, message):
        self.git("add", ".", cwd=repo)
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.test",
                 "commit", "-m", message, cwd=repo)

    def test_quadlet_install_refreshes_existing_and_new_checkouts(self):
        # Use real local Git remotes and execute SSH payloads locally. The only
        # substituted boundaries are transport and system-service activation.
        home = self.root / "home"
        home.mkdir()
        config = self.root / "gitconfig"
        config.touch()
        self.env.update(HOME=str(home), GIT_CONFIG_GLOBAL=str(config),
                        GIT_CONFIG_NOSYSTEM="1", GIT_ALLOW_PROTOCOL="file")
        remote = self.root / "remote"
        remote.mkdir()
        self.git("init", "-b", "master", cwd=remote)
        subsystem = remote / "internal_cert_management"
        (subsystem / "systemd").mkdir(parents=True)
        for name in ("cert-renewal.container.tmpl", "cert-renewal.timer"):
            shutil.copy(PROJECT / "systemd" / name, subsystem / "systemd" / name)
        child = self.root / "child"
        child.mkdir()
        self.git("init", "-b", "master", cwd=child)
        (child / "initialized").write_text("submodule content")
        self.commit(child, "child")
        self.git("submodule", "add", str(child), "private-smart-home-ansible", cwd=remote)
        self.commit(remote, "old deployment")
        checkout = self.root / "checkout"
        self.git("clone", str(remote), str(checkout))
        shutil.copy(PROJECT / "systemd/cert-renewal.build.tmpl", subsystem / "systemd")
        self.commit(remote, "new build template")
        self.git("config", "--global", f"url.{remote}.insteadOf",
                 "https://github.com/NickJLange/overlord.git")
        self.executable("ssh", 'if [ "$1" = -A ]; then shift; fi\nshift\nexec bash -c "$1"\n')
        self.executable("systemctl", "exit 0\n")
        self.executable("loginctl", "exit 0\n")
        shutil.copy(PROJECT / "Makefile", self.app / "Makefile")
        for state in ("existing", "new"):
            with self.subTest(state=state):
                if state == "new":
                    shutil.rmtree(checkout)
                result = subprocess.run(
                    ["make", "quadlet-install", "DEPLOY_HOST=test-host", "DEPLOY_USER=test-user",
                     f"REPO_PATH={checkout}"], cwd=self.app, env=self.env,
                    text=True, capture_output=True,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                unit = home / ".config/containers/systemd/cert-renewal.build"
                self.assertIn(f"File={checkout}/internal_cert_management/Containerfile", unit.read_text())
                self.assertEqual((checkout / "private-smart-home-ansible/initialized").read_text(), "submodule content")
                self.assertEqual(self.git("rev-parse", "HEAD", cwd=checkout),
                                 self.git("rev-parse", "HEAD", cwd=remote))


if __name__ == "__main__":
    unittest.main()
