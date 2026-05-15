# Docker Infra Installer

Two-phase installer for Ubuntu 24.04 production hosts.

```bash
sudo project/main/installer/preinstall.sh
sudo /opt/docker-infra/installer/install.sh --step all
```

`preinstall.sh` installs nginx and a local installer page on port `8088`. The page calls the local installer API through the installer nginx site.

The `installer/` directory is intended to be copied as a self-contained install unit. Its `payload/` directory carries the packaged WIZ bundle, built custom Codex CLI binaries for `linux-x86_64` and `linux-aarch64`, Python requirements, and checksums so the production host does not need the development workspace or a Rust/Cargo build step. Payload checksums are verified before use.

After source changes, refresh only the packaged WIZ payload from the development workspace:

```bash
project/main/installer/update-wiz-bundle.sh
```

The script builds project `main`, runs `wiz bundle`, replaces `payload/wiz-bundle.tar.zst`, and rewrites `payload/checksums.sha256`.

The install flow also installs Node.js LTS and npm from NodeSource, then installs the official `@openai/codex` npm package globally as the normal `codex` command. The packaged custom Codex CLI is installed separately for Docker Infra runtime use under `/opt/docker-infra/codex-custom/bin/docker-infra-codex`, selected by host architecture before execution.

`install.sh` can run the full install or one step at a time:

```bash
sudo /opt/docker-infra/installer/install.sh --step apt
sudo /opt/docker-infra/installer/install.sh --step postgres
sudo /opt/docker-infra/installer/install.sh --step node
sudo /opt/docker-infra/installer/install.sh --step bundle
sudo /opt/docker-infra/installer/install.sh --step setup
sudo /opt/docker-infra/installer/install.sh --step cleanup
```

Rollback file artifacts without removing apt, pip, npm, PostgreSQL, or Node.js packages:

```bash
sudo /opt/docker-infra/installer/cleanup.sh --scope preinstall
sudo /opt/docker-infra/installer/cleanup.sh --scope install
sudo /opt/docker-infra/installer/cleanup.sh --scope all
```

Production PostgreSQL is installed on the host. The development compose PostgreSQL remains only for dev/test.

The installer page owns the first admin password and initial system settings. The product `/access` page only shows password login after setup is complete.

Run `cleanup` only after `verify` succeeds. It schedules removal of `docker-infra-installer.service`, the installer nginx site, installer HTML/payload files, and temporary initial setup file.
