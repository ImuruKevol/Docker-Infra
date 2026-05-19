#!/usr/bin/env bash
set -Eeuo pipefail
umask 027

APP_NAME="${APP_NAME:-docker-infra}"
SERVICE_NAME="${SERVICE_NAME:-docker-infra}"
INSTALL_BASE="${INSTALL_BASE:-/opt/docker-infra}"
WIZ_ROOT="${WIZ_ROOT:-$INSTALL_BASE/wiz}"
DATA_ROOT="${DATA_ROOT:-/var/lib/docker-infra}"
ENV_DIR="${ENV_DIR:-/etc/docker-infra}"
ENV_FILE="${ENV_FILE:-$ENV_DIR/docker-infra.env}"
INSTALLER_ENV_FILE="${INSTALLER_ENV_FILE:-$ENV_DIR/installer.env}"
INITIAL_SETUP_FILE="${INITIAL_SETUP_FILE:-$ENV_DIR/initial-setup.json}"
LOG_DIR="${LOG_DIR:-/var/log/docker-infra}"
INSTALLER_ROOT="${INSTALLER_ROOT:-$INSTALL_BASE/installer}"
INSTALLER_SERVICE_NAME="${INSTALLER_SERVICE_NAME:-docker-infra-installer.service}"
INSTALLER_NGINX_SITE="${INSTALLER_NGINX_SITE:-docker-infra-installer}"
NGINX_SITE_NAME="${NGINX_SITE_NAME:-docker-infra}"

if [[ -f "$INSTALLER_ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$INSTALLER_ENV_FILE"
    set +a
fi
INITIAL_SETUP_FILE="${DOCKER_INFRA_INITIAL_SETUP_FILE:-$INITIAL_SETUP_FILE}"
INSTALLER_LOG="${DOCKER_INFRA_INSTALLER_LOG:-$LOG_DIR/installer.log}"

SCOPE="all"
DRY_RUN="0"
PURGE_DATA="0"
PURGE_LOGS="0"

log() {
    printf '[docker-infra-cleanup] %s\n' "$*"
}

fail() {
    log "ERROR: $*"
    exit 1
}

usage() {
    cat <<'EOF'
Usage: cleanup.sh [--scope preinstall|install|all] [--dry-run] [--purge-data] [--purge-logs]

Removes Docker Infra installer/deployment files only.
It does not uninstall apt packages, pip packages, npm packages, PostgreSQL packages, or Node.js.

Scopes:
  preinstall  Remove installer API service, installer nginx site, env, and installer HTML/payload.
  install     Remove Docker Infra WIZ service files, deployed bundle, runtime env, and app nginx site.
  all         Run install cleanup first, then preinstall cleanup.

Options:
  --dry-run     Print actions without deleting files.
  --purge-data  Also remove DATA_ROOT. Use only for failed installs or intentional data reset.
  --purge-logs  Also remove LOG_DIR.
EOF
}

require_root() {
    if [[ "$(id -u)" != "0" ]]; then
        fail "run as root"
    fi
}

execute() {
    log "+ $*"
    if [[ "$DRY_RUN" == "1" ]]; then
        return 0
    fi
    "$@"
}

remove_path() {
    local path
    for path in "$@"; do
        if [[ -e "$path" || -L "$path" ]]; then
            execute rm -rf "$path"
        fi
    done
}

remove_empty_dir() {
    local path="$1"
    if [[ -d "$path" ]]; then
        log "+ rmdir --ignore-fail-on-non-empty $path"
        if [[ "$DRY_RUN" != "1" ]]; then
            rmdir "$path" 2>/dev/null || true
        fi
    fi
}

disable_unit() {
    local unit="$1"
    if command -v systemctl >/dev/null 2>&1; then
        execute systemctl disable --now "$unit" || true
    fi
    remove_path "/etc/systemd/system/$unit" "/etc/systemd/system/$unit.d"
}

remove_nginx_site() {
    local site="$1"
    remove_path "/etc/nginx/sites-enabled/$site.conf" "/etc/nginx/sites-available/$site.conf"
}

reload_systemd() {
    if command -v systemctl >/dev/null 2>&1; then
        execute systemctl daemon-reload || true
    fi
}

reload_nginx() {
    if command -v nginx >/dev/null 2>&1 && command -v systemctl >/dev/null 2>&1; then
        if [[ "$DRY_RUN" == "1" ]]; then
            log "+ nginx -t && systemctl reload nginx"
            return 0
        fi
        if nginx -t >/dev/null 2>&1; then
            systemctl reload nginx || true
        fi
    fi
}

cleanup_preinstall() {
    log "removing preinstall file artifacts"
    disable_unit "$INSTALLER_SERVICE_NAME"
    remove_nginx_site "$INSTALLER_NGINX_SITE"
    remove_path "$INSTALLER_ROOT" "$INSTALLER_ENV_FILE" "$INITIAL_SETUP_FILE"
    remove_empty_dir "$ENV_DIR"
}

cleanup_install() {
    log "removing install file artifacts"
    disable_unit "wiz.$SERVICE_NAME.service"
    remove_nginx_site "$NGINX_SITE_NAME"
    remove_path \
        "$WIZ_ROOT" \
        "$INSTALL_BASE/codex" \
        "$ENV_FILE" \
        "$INITIAL_SETUP_FILE"
    if [[ "$PURGE_DATA" == "1" ]]; then
        remove_path "$DATA_ROOT"
    fi
    if [[ "$PURGE_LOGS" == "1" ]]; then
        remove_path "$LOG_DIR" "$INSTALLER_LOG"
    fi
    remove_empty_dir "$ENV_DIR"
    remove_empty_dir "$INSTALL_BASE"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --scope)
            SCOPE="${2:-}"
            shift 2
            ;;
        --dry-run)
            DRY_RUN="1"
            shift
            ;;
        --purge-data)
            PURGE_DATA="1"
            shift
            ;;
        --purge-logs)
            PURGE_LOGS="1"
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            usage
            fail "unknown argument: $1"
            ;;
    esac
done

require_root

case "$SCOPE" in
    preinstall)
        cleanup_preinstall
        ;;
    install)
        cleanup_install
        ;;
    all)
        cleanup_install
        cleanup_preinstall
        ;;
    *)
        usage
        fail "unknown scope: $SCOPE"
        ;;
esac

reload_systemd
reload_nginx
log "cleanup completed"
