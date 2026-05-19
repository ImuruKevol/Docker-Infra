#!/usr/bin/env bash
set -Eeuo pipefail
umask 027

APP_NAME="${APP_NAME:-docker-infra}"
INSTALL_BASE="${INSTALL_BASE:-/opt/docker-infra}"
INSTALLER_ROOT="${INSTALLER_ROOT:-$INSTALL_BASE/installer}"
ENV_DIR="${ENV_DIR:-/etc/docker-infra}"
INSTALLER_ENV_FILE="${INSTALLER_ENV_FILE:-$ENV_DIR/installer.env}"
INSTALLER_LOG="${INSTALLER_LOG:-/var/log/docker-infra/installer.log}"
INSTALLER_PORT="${INSTALLER_PORT:-8088}"
INSTALLER_API_HOST="${INSTALLER_API_HOST:-127.0.0.1}"
INSTALLER_API_PORT="${INSTALLER_API_PORT:-8791}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${DOCKER_INFRA_PROJECT_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
WORKSPACE_ROOT="${DOCKER_INFRA_WORKSPACE_ROOT:-$(cd "$PROJECT_ROOT/../.." && pwd)}"

log() {
    printf '[docker-infra-preinstall] %s\n' "$*"
}

fail() {
    log "ERROR: $*"
    exit 1
}

require_root() {
    if [[ "$(id -u)" != "0" ]]; then
        fail "run as root"
    fi
}

install_prerequisites() {
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y --no-install-recommends nginx python3 openssl ca-certificates zstd
    systemctl enable --now nginx
}

copy_installer_files() {
    install -d -m 0755 "$INSTALLER_ROOT" "$ENV_DIR" "$(dirname "$INSTALLER_LOG")"
    install -m 0755 "$SCRIPT_DIR/install.sh" "$INSTALLER_ROOT/install.sh"
    install -m 0755 "$SCRIPT_DIR/cleanup.sh" "$INSTALLER_ROOT/cleanup.sh"
    install -m 0755 "$SCRIPT_DIR/installer_api.py" "$INSTALLER_ROOT/installer_api.py"
    install -m 0644 "$SCRIPT_DIR/installer.html" "$INSTALLER_ROOT/index.html"
    install -m 0644 "$SCRIPT_DIR/docker-infra.env.example" "$INSTALLER_ROOT/docker-infra.env.example"
    if [[ -d "$SCRIPT_DIR/payload" ]]; then
        rm -rf "$INSTALLER_ROOT/payload"
        cp -a "$SCRIPT_DIR/payload" "$INSTALLER_ROOT/payload"
    fi

    cat >"$INSTALLER_ENV_FILE" <<EOF
DOCKER_INFRA_PROJECT_ROOT=$PROJECT_ROOT
DOCKER_INFRA_WORKSPACE_ROOT=$WORKSPACE_ROOT
DOCKER_INFRA_INSTALLER_SCRIPT=$INSTALLER_ROOT/install.sh
DOCKER_INFRA_INSTALLER_LOG=$INSTALLER_LOG
DOCKER_INFRA_INSTALLER_STATE=$INSTALLER_ROOT/state.json
DOCKER_INFRA_INITIAL_SETUP_FILE=$ENV_DIR/initial-setup.json
INSTALLER_ROOT=$INSTALLER_ROOT
PAYLOAD_DIR=$INSTALLER_ROOT/payload
PIP_REQUIREMENTS=$INSTALLER_ROOT/payload/requirements.txt
WIZ_BUNDLE_ARCHIVE=$INSTALLER_ROOT/payload/wiz-bundle.tar.zst
INSTALLER_SERVICE_NAME=docker-infra-installer.service
INSTALLER_NGINX_SITE=docker-infra-installer
EOF
    chmod 0640 "$INSTALLER_ENV_FILE"

    log "installer files copied to $INSTALLER_ROOT"
}

configure_installer_service() {
    cat >/etc/systemd/system/docker-infra-installer.service <<EOF
[Unit]
Description=Docker Infra installer API
After=network.target

[Service]
Type=simple
EnvironmentFile=$INSTALLER_ENV_FILE
ExecStart=/usr/bin/python3 $INSTALLER_ROOT/installer_api.py --host $INSTALLER_API_HOST --port $INSTALLER_API_PORT
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable --now docker-infra-installer.service
    log "installer API service started"
}

configure_nginx_installer_site() {
    install -d -m 0755 /etc/nginx/sites-available /etc/nginx/sites-enabled
    cat >/etc/nginx/sites-available/docker-infra-installer.conf <<EOF
server {
    listen $INSTALLER_PORT;
    server_name _;
    root $INSTALLER_ROOT;
    index index.html;

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    location /installer-api/ {
        proxy_pass http://$INSTALLER_API_HOST:$INSTALLER_API_PORT/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 3600;
    }
}
EOF
    ln -sfn /etc/nginx/sites-available/docker-infra-installer.conf /etc/nginx/sites-enabled/docker-infra-installer.conf
    nginx -t
    systemctl reload nginx
    log "installer page is available on port $INSTALLER_PORT"
}

main() {
    require_root
    install_prerequisites
    copy_installer_files
    configure_installer_service
    configure_nginx_installer_site
    log "installer is ready"
}

main "$@"
