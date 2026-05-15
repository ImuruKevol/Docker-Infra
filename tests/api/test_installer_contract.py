import py_compile
import stat
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "installer"


class InstallerContractTest(unittest.TestCase):
    def read(self, name):
        return (INSTALLER / name).read_text(encoding="utf-8")

    def test_installer_files_exist(self):
        for name in [
            "preinstall.sh",
            "install.sh",
            "cleanup.sh",
            "installer_api.py",
            "installer.html",
            "docker-infra.env.example",
            "README.md",
            "payload/wiz-bundle.tar.zst",
            "payload/codex-bin/linux-x86_64/codex",
            "payload/codex-bin/linux-aarch64/codex",
            "payload/requirements.txt",
            "payload/checksums.sha256",
        ]:
            self.assertTrue((INSTALLER / name).is_file(), name)

    def test_shell_scripts_are_executable(self):
        for name in ["preinstall.sh", "install.sh", "cleanup.sh", "installer_api.py"]:
            mode = (INSTALLER / name).stat().st_mode
            self.assertTrue(mode & stat.S_IXUSR, name)

    def test_install_script_covers_production_deployment_steps(self):
        script = self.read("install.sh")

        for token in [
            "APT_PACKAGES=(",
            "postgresql",
            "docker.io",
            "docker-compose-plugin",
            "zstd",
            "pip install -r",
            "NODE_SOURCE_SETUP_URL",
            "https://deb.nodesource.com/setup_lts.x",
            "bash \"$setup_script\"",
            "apt-get install -y --no-install-recommends nodejs",
            "npm install -g \"$OFFICIAL_CODEX_PACKAGE\"",
            "@openai/codex",
            "DOCKER_INFRA_SYSTEM_CODEX_BIN",
            "DOCKER_INFRA_CODEX_BIN",
            "CODEX_CUSTOM_BIN_DIR",
            "CODEX_INSTALL_BIN_DEFAULT=\"$INSTALL_BASE/codex-custom/bin/docker-infra-codex\"",
            "LEGACY_CODEX_INSTALL_BIN=\"$INSTALL_BASE/codex/bin/codex\"",
            "target_bin=\"$CODEX_INSTALL_BIN_DEFAULT\"",
            "custom Codex CLI host architecture",
            "custom Codex CLI payload selected",
            "validate_custom_codex_payload_arch",
            "custom Codex CLI payload architecture mismatch",
            "WIZ_BUNDLE_ARCHIVE",
            "tar --zstd",
            "sha256sum -c checksums.sha256",
            "bundle --project",
            "rsync -a --delete",
            "migrate_up()",
            "EnvironmentFile=",
            "assert_wiz_service_wrapper",
            '"$WIZ_BIN" service regist "$SERVICE_NAME" bundle "$APP_PORT"',
            "--port $APP_PORT --bundle --log /var/log/wiz/$service_key",
            "run_initial_setup",
            "INITIAL_SETUP_FILE",
            "/api/system/setup",
            "requires_setup",
            "cleanup_installer",
            "installer cleanup scheduled",
        ]:
            self.assertIn(token, script)
        self.assertNotIn("cargo build", script)
        self.assertNotIn("CODEX_CUSTOM_ARCHIVE", script)
        self.assertNotIn("rustc", script)
        self.assertNotIn("cargo", script)
        self.assertNotIn('"$WIZ_BIN" service regist "$SERVICE_NAME" "$APP_PORT" bundle', script)

    def test_preinstall_provisions_html_and_api(self):
        script = self.read("preinstall.sh")
        html = self.read("installer.html")
        api = self.read("installer_api.py")

        self.assertIn("docker-infra-installer.service", script)
        self.assertIn("docker-infra-installer.conf", script)
        self.assertIn("installer_api.py", script)
        self.assertIn("cleanup.sh", script)
        self.assertIn("cp -a \"$SCRIPT_DIR/payload\"", script)
        self.assertIn("PAYLOAD_DIR=$INSTALLER_ROOT/payload", script)
        self.assertIn("CODEX_CUSTOM_BIN_DIR=$INSTALLER_ROOT/payload/codex-bin", script)
        self.assertIn("/installer-api${path}", html)
        self.assertIn("api('/run'", html)
        self.assertIn("adminPassword", html)
        self.assertIn("installer-admin-password", html)
        self.assertIn("관리자 비밀번호 설정", html)
        self.assertIn("'setup', '관리자 비밀번호 / 초기 시스템 설정'", html)
        self.assertIn("'node', 'Official Codex CLI'", html)
        self.assertIn("'cleanup', '설치 관리자 정리'", html)
        self.assertIn("prevStep", html)
        self.assertIn("nextStep", html)
        self.assertIn("runCurrent", html)
        self.assertIn("finishedAt", html)
        self.assertIn("단계 종료:", html)
        self.assertIn("stepLabel(status.step)", html)
        self.assertIn("logEl.textContent = ''", html)
        self.assertNotIn("X-Installer-Token", html)
        self.assertNotIn("X-Installer-Token", api)
        self.assertNotIn("installer.token", script)
        self.assertNotIn("installer.token", html)
        self.assertNotIn("installer.token", api)
        self.assertIn("DOCKER_INFRA_INITIAL_SETUP_FILE", api)
        self.assertIn("ALLOWED_STEPS", api)
        self.assertIn('self.log_path.open("w"', api)
        self.assertIn("단계 종료:", api)
        self.assertIn("result = \"success\" if code == 0 else \"failed\"", api)
        self.assertIn('"node"', api)
        self.assertIn('"cleanup"', api)

    def test_env_template_includes_database_and_codex_runtime(self):
        env = self.read("docker-infra.env.example")

        for token in [
            "DOCKER_INFRA_DB_HOST",
            "DOCKER_INFRA_DB_PASSWORD",
            "DOCKER_INFRA_SECRET_KEY",
            "DOCKER_INFRA_SYSTEM_CODEX_BIN",
            "DOCKER_INFRA_CODEX_AUTO_BUILD=0",
            "CODEX_HOME",
        ]:
            self.assertIn(token, env)
        self.assertIn("DOCKER_INFRA_SYSTEM_CODEX_BIN=/usr/local/bin/codex", env)
        self.assertIn("DOCKER_INFRA_CODEX_BIN=/opt/docker-infra/codex-custom/bin/docker-infra-codex", env)

    def test_codex_payload_is_binary_only(self):
        payload = INSTALLER / "payload"
        codex_bins = [
            payload / "codex-bin/linux-x86_64/codex",
            payload / "codex-bin/linux-aarch64/codex",
        ]
        checksums = (payload / "checksums.sha256").read_text(encoding="utf-8")

        for codex_bin in codex_bins:
            self.assertTrue(codex_bin.is_file(), codex_bin)
            self.assertTrue(codex_bin.stat().st_mode & stat.S_IXUSR, codex_bin)
            self.assertIn(str(codex_bin.relative_to(payload)), checksums)
        self.assertFalse((payload / "codex-bin/codex").exists())
        self.assertFalse((payload / "codex-custom.tar.zst").exists())

    def test_cleanup_script_removes_file_artifacts_only(self):
        script = self.read("cleanup.sh")

        for token in [
            "--scope preinstall|install|all",
            "cleanup_preinstall",
            "cleanup_install",
            "docker-infra-installer.service",
            "wiz.$SERVICE_NAME.service",
            "/etc/nginx/sites-enabled/$site.conf",
            "$INSTALLER_ROOT",
            "$WIZ_ROOT",
            "$INSTALL_BASE/codex-custom",
            "$INSTALL_BASE/codex",
            "It does not uninstall apt packages, pip packages, npm packages",
            "--purge-data",
            "--purge-logs",
        ]:
            self.assertIn(token, script)
        self.assertNotIn("installer.token", script)
        self.assertNotIn("apt-get remove", script)
        self.assertNotIn("pip uninstall", script)
        self.assertNotIn("npm uninstall", script)

    def test_installer_api_compiles(self):
        py_compile.compile(str(INSTALLER / "installer_api.py"), doraise=True)


if __name__ == "__main__":
    unittest.main()
