#!/usr/bin/env bash
set -Eeuo pipefail
umask 027

APP_NAME="${APP_NAME:-docker-infra}"
SERVICE_NAME="${SERVICE_NAME:-docker-infra}"
PROJECT_NAME="${PROJECT_NAME:-main}"
INSTALL_BASE="${INSTALL_BASE:-/opt/docker-infra}"
WIZ_ROOT="${WIZ_ROOT:-$INSTALL_BASE/wiz}"
DATA_ROOT="${DATA_ROOT:-/var/lib/docker-infra}"
ENV_DIR="${ENV_DIR:-/etc/docker-infra}"
ENV_FILE="${ENV_FILE:-$ENV_DIR/docker-infra.env}"
INSTALLER_ENV_FILE="${INSTALLER_ENV_FILE:-$ENV_DIR/installer.env}"
INITIAL_SETUP_FILE="${INITIAL_SETUP_FILE:-$ENV_DIR/initial-setup.json}"
LOG_DIR="${LOG_DIR:-/var/log/docker-infra}"
APP_HOST="${APP_HOST:-127.0.0.1}"
APP_PORT="${APP_PORT:-3000}"
NGINX_SITE_NAME="${NGINX_SITE_NAME:-docker-infra}"
INSTALLER_SERVICE_NAME="${INSTALLER_SERVICE_NAME:-docker-infra-installer.service}"
INSTALLER_NGINX_SITE="${INSTALLER_NGINX_SITE:-docker-infra-installer}"
NODE_SOURCE_SETUP_URL="${NODE_SOURCE_SETUP_URL:-https://deb.nodesource.com/setup_lts.x}"
OFFICIAL_CODEX_PACKAGE="${OFFICIAL_CODEX_PACKAGE:-@openai/codex}"

if [[ -f "$INSTALLER_ENV_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$INSTALLER_ENV_FILE"
    set +a
fi
INITIAL_SETUP_FILE="${DOCKER_INFRA_INITIAL_SETUP_FILE:-$INITIAL_SETUP_FILE}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALLER_ROOT="${INSTALLER_ROOT:-$SCRIPT_DIR}"
PAYLOAD_DIR="${PAYLOAD_DIR:-$SCRIPT_DIR/payload}"
PROJECT_ROOT="${DOCKER_INFRA_PROJECT_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
WORKSPACE_ROOT="${DOCKER_INFRA_WORKSPACE_ROOT:-$(cd "$PROJECT_ROOT/../.." && pwd)}"
BUNDLE_ROOT="${BUNDLE_ROOT:-$WORKSPACE_ROOT/bundle}"
WIZ_BUNDLE_ARCHIVE="${WIZ_BUNDLE_ARCHIVE:-$PAYLOAD_DIR/wiz-bundle.tar.zst}"
PIP_REQUIREMENTS="${PIP_REQUIREMENTS:-$PAYLOAD_DIR/requirements.txt}"
if [[ ! -f "$PIP_REQUIREMENTS" ]]; then
    PIP_REQUIREMENTS="$PROJECT_ROOT/requirements.txt"
fi

if [[ -z "${PYTHON_BIN:-}" ]]; then
    if [[ -x /opt/conda/envs/docker-infra/bin/python ]]; then
        PYTHON_BIN="/opt/conda/envs/docker-infra/bin/python"
    elif [[ -x "$INSTALL_BASE/venv/bin/python" ]]; then
        PYTHON_BIN="$INSTALL_BASE/venv/bin/python"
    else
        PYTHON_BIN="$(command -v python3 || true)"
    fi
fi

if [[ -z "${WIZ_BIN:-}" ]]; then
    if [[ -x /opt/conda/envs/docker-infra/bin/wiz ]]; then
        WIZ_BIN="/opt/conda/envs/docker-infra/bin/wiz"
    elif [[ -x "$INSTALL_BASE/venv/bin/wiz" ]]; then
        WIZ_BIN="$INSTALL_BASE/venv/bin/wiz"
    else
        WIZ_BIN="$(command -v wiz || true)"
    fi
fi

APT_PACKAGES=(
    ca-certificates
    curl
    gnupg
    openssl
    network-manager
    nginx
    postgresql
    postgresql-contrib
    certbot
    python3-certbot-nginx
    docker.io
    openssh-client
    rsync
    git
    zstd
    python3
    python3-pip
    python3-venv
)

DOCKER_COMPOSE_PACKAGES=(
    docker-compose-plugin
    docker-compose-v2
)

log() {
    printf '[docker-infra-install] %s\n' "$*" >&2
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

require_file() {
    local path="$1"
    [[ -f "$path" ]] || fail "required file is missing: $path"
}

require_executable() {
    local path="$1"
    [[ -n "$path" && -x "$path" ]] || fail "required executable is missing: $path"
}

verify_payload_checksums() {
    local checksum_file="$PAYLOAD_DIR/checksums.sha256"
    if [[ -f "$checksum_file" ]]; then
        local checksum_output
        log "verifying installer payload checksums"
        if ! checksum_output="$(cd "$PAYLOAD_DIR" && sha256sum -c checksums.sha256 2>&1)"; then
            printf '%s\n' "$checksum_output" >&2
            fail "installer payload checksum verification failed"
        fi
    fi
}

load_runtime_env() {
    if [[ -f "$ENV_FILE" ]]; then
        set -a
        # shellcheck disable=SC1090
        source "$ENV_FILE"
        set +a
    fi
}

random_secret() {
    openssl rand -base64 36 | tr -d '\n'
}

write_env_line() {
    local key="$1"
    local value="$2"
    printf '%s=%s\n' "$key" "$value"
}

set_env_value() {
    local key="$1"
    local value="$2"
    local env_tmp
    env_tmp="$(mktemp)"
    install -d -m 0750 "$ENV_DIR"
    if [[ -f "$ENV_FILE" ]]; then
        awk -v key="$key" -v value="$value" '
            BEGIN { written = 0 }
            $0 ~ "^" key "=" {
                print key "=" value
                written = 1
                next
            }
            { print }
            END {
                if (!written) print key "=" value
            }
        ' "$ENV_FILE" >"$env_tmp"
    else
        write_env_line "$key" "$value" >"$env_tmp"
    fi
    install -m 0640 "$env_tmp" "$ENV_FILE"
    rm -f "$env_tmp"
}

safe_identifier() {
    [[ "$1" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]
}

escape_sql_literal() {
    printf "%s" "${1//\'/\'\'}"
}

as_postgres() {
    if command -v runuser >/dev/null 2>&1; then
        runuser -u postgres -- "$@"
    else
        sudo -u postgres "$@"
    fi
}

fetch_setup_status() {
    local output_path="$1"
    local url="http://$APP_HOST:$APP_PORT/api/system/setup"
    for _ in $(seq 1 30); do
        if curl -fsS "$url" -o "$output_path"; then
            return 0
        fi
        sleep 1
    done
    return 1
}

ensure_runtime_env() {
    install -d -m 0750 "$ENV_DIR" "$LOG_DIR" "$DATA_ROOT" "$DATA_ROOT/data" "$DATA_ROOT/ssh" "$DATA_ROOT/backup-harbor" "$DATA_ROOT/codex-home"
    load_runtime_env

    local db_host="${DOCKER_INFRA_DB_HOST:-127.0.0.1}"
    local db_port="${DOCKER_INFRA_DB_PORT:-5432}"
    local db_name="${DOCKER_INFRA_DB_NAME:-docker_infra}"
    local db_user="${DOCKER_INFRA_DB_USER:-docker_infra}"
    local db_password="${DOCKER_INFRA_DB_PASSWORD:-$(random_secret)}"
    local db_schema="${DOCKER_INFRA_DB_SCHEMA:-public}"
    local secret_key="${DOCKER_INFRA_SECRET_KEY:-$(random_secret)}"
    local official_codex_bin="${DOCKER_INFRA_SYSTEM_CODEX_BIN:-$(command -v codex || true)}"
    if [[ -z "$official_codex_bin" ]]; then
        official_codex_bin="/usr/local/bin/codex"
    fi
    local env_tmp
    env_tmp="$(mktemp)"

    {
        write_env_line "DOCKER_INFRA_DB_HOST" "$db_host"
        write_env_line "DOCKER_INFRA_DB_PORT" "$db_port"
        write_env_line "DOCKER_INFRA_DB_NAME" "$db_name"
        write_env_line "DOCKER_INFRA_DB_USER" "$db_user"
        write_env_line "DOCKER_INFRA_DB_PASSWORD" "$db_password"
        write_env_line "DOCKER_INFRA_DB_SCHEMA" "$db_schema"
        write_env_line "DOCKER_INFRA_SECRET_KEY" "$secret_key"
        write_env_line "DOCKER_INFRA_DATA_DIR" "$DATA_ROOT/data"
        write_env_line "DOCKER_INFRA_SSH_KEY_DIR" "$DATA_ROOT/ssh"
        write_env_line "DOCKER_INFRA_BACKUP_HARBOR_DATA_DIR" "$DATA_ROOT/backup-harbor"
        write_env_line "DOCKER_INFRA_BACKUP_HARBOR_HTTP_PORT" "${DOCKER_INFRA_BACKUP_HARBOR_HTTP_PORT:-5000}"
        write_env_line "DOCKER_INFRA_BACKUP_HARBOR_HTTPS_PORT" "${DOCKER_INFRA_BACKUP_HARBOR_HTTPS_PORT:-5443}"
        write_env_line "DOCKER_INFRA_SESSION_COOKIE_SECURE" "${DOCKER_INFRA_SESSION_COOKIE_SECURE:-false}"
        write_env_line "DOCKER_INFRA_SYSTEM_CODEX_BIN" "$official_codex_bin"
        write_env_line "CODEX_HOME" "${CODEX_HOME:-$DATA_ROOT/codex-home}"
    } >"$env_tmp"

    install -m 0640 "$env_tmp" "$ENV_FILE"
    rm -f "$env_tmp"
    load_runtime_env
    log "runtime environment file prepared at $ENV_FILE"
}

install_apt_packages() {
    export DEBIAN_FRONTEND=noninteractive
    log "installing apt packages"
    apt-get update
    apt-get install -y --no-install-recommends "${APT_PACKAGES[@]}"
    if ! apt-get install -y --no-install-recommends "${DOCKER_COMPOSE_PACKAGES[0]}"; then
        apt-get install -y --no-install-recommends "${DOCKER_COMPOSE_PACKAGES[1]}"
    fi
    systemctl enable --now postgresql
    systemctl enable --now nginx
}

install_postgresql_database() {
    ensure_runtime_env
    load_runtime_env

    safe_identifier "$DOCKER_INFRA_DB_USER" || fail "invalid DOCKER_INFRA_DB_USER"
    safe_identifier "$DOCKER_INFRA_DB_NAME" || fail "invalid DOCKER_INFRA_DB_NAME"
    safe_identifier "$DOCKER_INFRA_DB_SCHEMA" || fail "invalid DOCKER_INFRA_DB_SCHEMA"
    systemctl enable --now postgresql

    local role_exists
    role_exists="$(as_postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname = '$DOCKER_INFRA_DB_USER'" | tr -d '[:space:]')"
    if [[ "$role_exists" != "1" ]]; then
        as_postgres createuser "$DOCKER_INFRA_DB_USER"
    fi

    local password_sql
    password_sql="$(escape_sql_literal "$DOCKER_INFRA_DB_PASSWORD")"
    as_postgres psql -v ON_ERROR_STOP=1 -c "ALTER ROLE \"$DOCKER_INFRA_DB_USER\" WITH LOGIN PASSWORD '$password_sql';"

    local database_exists
    database_exists="$(as_postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname = '$DOCKER_INFRA_DB_NAME'" | tr -d '[:space:]')"
    if [[ "$database_exists" != "1" ]]; then
        as_postgres createdb -O "$DOCKER_INFRA_DB_USER" "$DOCKER_INFRA_DB_NAME"
    fi

    as_postgres psql -v ON_ERROR_STOP=1 -d "$DOCKER_INFRA_DB_NAME" -c "CREATE SCHEMA IF NOT EXISTS \"$DOCKER_INFRA_DB_SCHEMA\" AUTHORIZATION \"$DOCKER_INFRA_DB_USER\";"
    as_postgres psql -v ON_ERROR_STOP=1 -d "$DOCKER_INFRA_DB_NAME" -c "GRANT ALL ON SCHEMA \"$DOCKER_INFRA_DB_SCHEMA\" TO \"$DOCKER_INFRA_DB_USER\";"
    log "postgresql database and schema are ready"
}

install_python_packages() {
    require_file "$PIP_REQUIREMENTS"
    verify_payload_checksums
    if [[ ! -x "$PYTHON_BIN" || "$PYTHON_BIN" == "$(command -v python3 2>/dev/null || true)" ]]; then
        python3 -m venv "$INSTALL_BASE/venv"
        PYTHON_BIN="$INSTALL_BASE/venv/bin/python"
    fi
    require_executable "$PYTHON_BIN"
    log "installing pip packages from $PIP_REQUIREMENTS"
    "$PYTHON_BIN" -m pip install --upgrade pip
    "$PYTHON_BIN" -m pip install -r "$PIP_REQUIREMENTS"
    if [[ -x "$INSTALL_BASE/venv/bin/wiz" ]]; then
        WIZ_BIN="$INSTALL_BASE/venv/bin/wiz"
    fi
}

install_nodejs_and_official_codex() {
    export DEBIAN_FRONTEND=noninteractive
    log "installing Node.js LTS and npm"
    apt-get update
    apt-get install -y --no-install-recommends ca-certificates curl gnupg
    local setup_script
    setup_script="$(mktemp)"
    curl -fsSL "$NODE_SOURCE_SETUP_URL" -o "$setup_script"
    bash "$setup_script"
    rm -f "$setup_script"
    apt-get install -y --no-install-recommends nodejs

    require_executable "$(command -v node || true)"
    require_executable "$(command -v npm || true)"
    node --version >/dev/null
    npm --version >/dev/null
    log "installing official Codex CLI package $OFFICIAL_CODEX_PACKAGE"
    npm install -g "$OFFICIAL_CODEX_PACKAGE"
    npm list -g "$OFFICIAL_CODEX_PACKAGE" --depth=0 >/dev/null
    local official_bin
    official_bin="$(command -v codex || true)"
    require_executable "$official_bin"
    "$official_bin" --version >/dev/null
    set_env_value "DOCKER_INFRA_SYSTEM_CODEX_BIN" "$official_bin"
    log "official Codex CLI installed at $official_bin"
}

build_and_deploy_bundle() {
    local bundle_source_root="$BUNDLE_ROOT"
    local bundle_extract_root=""

    if [[ -f "$WIZ_BUNDLE_ARCHIVE" ]]; then
        verify_payload_checksums
        bundle_extract_root="$(mktemp -d)"
        tar --zstd -xf "$WIZ_BUNDLE_ARCHIVE" -C "$bundle_extract_root"
        bundle_source_root="$bundle_extract_root/bundle"
        log "using packaged WIZ bundle payload"
    else
        require_executable "$WIZ_BIN"
        log "building WIZ deployment bundle for project $PROJECT_NAME"
        (cd "$WORKSPACE_ROOT" && "$WIZ_BIN" bundle --project="$PROJECT_NAME")
    fi

    local project_bundle="$bundle_source_root/project/$PROJECT_NAME/bundle"
    [[ -d "$project_bundle" ]] || fail "WIZ project bundle not found: $project_bundle"

    install -d -m 0755 "$WIZ_ROOT/config" "$WIZ_ROOT/public" "$WIZ_ROOT/plugin" "$WIZ_ROOT/project/$PROJECT_NAME"
    rsync -a --delete "$bundle_source_root/config/" "$WIZ_ROOT/config/"
    rsync -a --delete "$bundle_source_root/public/" "$WIZ_ROOT/public/"
    rsync -a --delete "$bundle_source_root/plugin/" "$WIZ_ROOT/plugin/"
    rsync -a --delete "$project_bundle/" "$WIZ_ROOT/project/$PROJECT_NAME/bundle/"
    ln -sfn "$ENV_FILE" "$WIZ_ROOT/config.env"
    if [[ -n "$bundle_extract_root" ]]; then
        rm -rf "$bundle_extract_root"
    fi
    log "bundle files deployed to $WIZ_ROOT"
}

cleanup_installer() {
    local root_real
    local base_real
    root_real="$(readlink -f "$INSTALLER_ROOT" 2>/dev/null || true)"
    base_real="$(readlink -f "$INSTALL_BASE" 2>/dev/null || true)"

    [[ -n "$root_real" && -n "$base_real" ]] || fail "installer cleanup paths are not resolvable"
    [[ "$root_real" == "$base_real/installer" || "$root_real" == "$base_real/installer/"* ]] || fail "refusing to remove unexpected installer root: $INSTALLER_ROOT"

    local cleanup_script
    cleanup_script="$(mktemp /tmp/docker-infra-installer-cleanup.XXXXXX.sh)"
    chmod 0700 "$cleanup_script"
    cat >"$cleanup_script" <<EOF
#!/usr/bin/env bash
set +e
sleep 3
systemctl disable --now "$INSTALLER_SERVICE_NAME" >/dev/null 2>&1
rm -f "/etc/systemd/system/$INSTALLER_SERVICE_NAME"
rm -f "/etc/nginx/sites-enabled/$INSTALLER_NGINX_SITE.conf"
rm -f "/etc/nginx/sites-available/$INSTALLER_NGINX_SITE.conf"
systemctl daemon-reload >/dev/null 2>&1
if command -v nginx >/dev/null 2>&1 && nginx -t >/dev/null 2>&1; then
    systemctl reload nginx >/dev/null 2>&1
fi
rm -f "$INITIAL_SETUP_FILE"
rm -f "$INSTALLER_ENV_FILE"
rm -rf "$root_real"
rm -f "$cleanup_script"
EOF
    nohup bash "$cleanup_script" >/dev/null 2>&1 &
    log "installer cleanup scheduled"
}

run_database_migrations() {
    ensure_runtime_env
    load_runtime_env
    require_executable "$PYTHON_BIN"

    local migration_path="$WIZ_ROOT/project/$PROJECT_NAME/bundle/src/model/db/migration.py"
    require_file "$migration_path"
    log "applying database migrations"
    MIGRATION_PATH="$migration_path" "$PYTHON_BIN" - <<'PY'
import importlib.util
import os
from pathlib import Path

path = Path(os.environ["MIGRATION_PATH"])
spec = importlib.util.spec_from_file_location("docker_infra_migration", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
applied = module.migrate_up()
print("Applied migrations: " + (", ".join(applied) if applied else "none"))
PY
}

assert_wiz_service_wrapper() {
    local service_key="${SERVICE_NAME,,}"
    local command_path="/usr/local/bin/wiz.$service_key"
    local expected_command="$WIZ_BIN run --port $APP_PORT --bundle --log /var/log/wiz/$service_key"
    local actual_command

    require_file "$command_path"
    actual_command="$(awk 'NF { line = $0 } END { print line }' "$command_path")"
    if [[ "$actual_command" != "$expected_command" ]]; then
        fail "WIZ service wrapper command mismatch: expected '$expected_command', got '${actual_command:-empty}'"
    fi
}

register_wiz_service() {
    ensure_runtime_env
    load_runtime_env
    require_executable "$WIZ_BIN"
    [[ -d "$WIZ_ROOT/project/$PROJECT_NAME/bundle" ]] || fail "bundle is not deployed: $WIZ_ROOT"

    log "registering WIZ systemd service wiz.$SERVICE_NAME"
    if systemctl list-unit-files "wiz.$SERVICE_NAME.service" >/dev/null 2>&1; then
        (cd "$WIZ_ROOT" && "$WIZ_BIN" service stop "$SERVICE_NAME") || true
        (cd "$WIZ_ROOT" && "$WIZ_BIN" service unregist "$SERVICE_NAME") || true
    fi

    (cd "$WIZ_ROOT" && "$WIZ_BIN" service regist "$SERVICE_NAME" bundle "$APP_PORT")
    assert_wiz_service_wrapper
    install -d -m 0755 "/etc/systemd/system/wiz.$SERVICE_NAME.service.d"
    cat >"/etc/systemd/system/wiz.$SERVICE_NAME.service.d/10-docker-infra-env.conf" <<EOF
[Service]
EnvironmentFile=$ENV_FILE
WorkingDirectory=$WIZ_ROOT
Environment=PATH=/opt/conda/envs/docker-infra/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
EOF
    systemctl daemon-reload
    systemctl enable "wiz.$SERVICE_NAME.service"
    (cd "$WIZ_ROOT" && "$WIZ_BIN" service start "$SERVICE_NAME") || systemctl restart "wiz.$SERVICE_NAME.service"
    log "WIZ service started"
}

run_initial_setup() {
    ensure_runtime_env
    load_runtime_env
    require_executable "$PYTHON_BIN"

    systemctl is-active --quiet "wiz.$SERVICE_NAME.service" || fail "wiz.$SERVICE_NAME.service is not active"

    local status_json
    status_json="$(mktemp)"
    fetch_setup_status "$status_json"
    if SETUP_JSON="$status_json" "$PYTHON_BIN" - <<'PY'
import json
import os
from pathlib import Path

payload = json.loads(Path(os.environ["SETUP_JSON"]).read_text(encoding="utf-8"))
setup = (payload.get("data") or {}).get("setup") or {}
raise SystemExit(0 if setup.get("requires_setup") is False else 1)
PY
    then
        rm -f "$status_json"
        rm -f "$INITIAL_SETUP_FILE"
        log "initial setup is already completed"
        return 0
    fi
    rm -f "$status_json"

    require_file "$INITIAL_SETUP_FILE"
    log "applying initial Docker Infra setup from installer payload"
    local setup_response
    setup_response="$(mktemp)"
    curl -fsS \
        -H "Content-Type: application/json" \
        --data-binary "@$INITIAL_SETUP_FILE" \
        "http://$APP_HOST:$APP_PORT/api/system/setup" -o "$setup_response"
    SETUP_RESPONSE="$setup_response" "$PYTHON_BIN" - <<'PY'
import json
import os
from pathlib import Path

payload = json.loads(Path(os.environ["SETUP_RESPONSE"]).read_text(encoding="utf-8"))
data = payload.get("data") or {}
if data.get("backup_error"):
    raise SystemExit(data["backup_error"].get("message") or "backup system setup failed")
if (data.get("setup") or {}).get("requires_setup"):
    raise SystemExit("initial setup is still required")
PY
    rm -f "$setup_response"
    rm -f "$INITIAL_SETUP_FILE"
    log "initial setup completed"
}

configure_nginx_app() {
    install -d -m 0755 /etc/nginx/sites-available /etc/nginx/sites-enabled
    cat >"/etc/nginx/sites-available/$NGINX_SITE_NAME.conf" <<EOF
server {
    listen 80;
    server_name _;
    client_max_body_size 4g;

    location / {
        proxy_pass http://$APP_HOST:$APP_PORT;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 3600;
        proxy_send_timeout 3600;
    }
}
EOF
    ln -sfn "/etc/nginx/sites-available/$NGINX_SITE_NAME.conf" "/etc/nginx/sites-enabled/$NGINX_SITE_NAME.conf"
    rm -f /etc/nginx/sites-enabled/default
    nginx -t
    systemctl reload nginx
    log "nginx reverse proxy is ready"
}

verify_installation() {
    ensure_runtime_env
    load_runtime_env
    require_executable "$PYTHON_BIN"

    systemctl is-active --quiet postgresql || fail "postgresql service is not active"
    systemctl is-active --quiet "wiz.$SERVICE_NAME.service" || fail "wiz.$SERVICE_NAME.service is not active"

    local setup_json
    setup_json="$(mktemp)"
    fetch_setup_status "$setup_json"
    SETUP_JSON="$setup_json" "$PYTHON_BIN" - <<'PY'
import json
import os
from pathlib import Path

payload = json.loads(Path(os.environ["SETUP_JSON"]).read_text(encoding="utf-8"))
data = payload.get("data") or {}
setup = data.get("setup") or {}
print(
    "Setup status: "
    f"database_configured={setup.get('database_configured')} "
    f"requires_setup={setup.get('requires_setup')} "
    f"configured={setup.get('configured')}"
)
if not setup.get("database_configured"):
    raise SystemExit("database is not configured")
if setup.get("requires_setup"):
    raise SystemExit("initial setup is not completed")
PY
    rm -f "$setup_json"
    log "verification completed"
}

run_all_steps() {
    install_apt_packages
    ensure_runtime_env
    install_postgresql_database
    install_python_packages
    install_nodejs_and_official_codex
    build_and_deploy_bundle
    run_database_migrations
    register_wiz_service
    run_initial_setup
    configure_nginx_app
    verify_installation
}

usage() {
    cat <<'EOF'
Usage: install.sh [--step STEP]

Steps:
  all        Run every deployment step in order.
  apt        Install apt packages and enable nginx/postgresql.
  env        Create /etc/docker-infra/docker-infra.env.
  postgres   Create PostgreSQL role, database, and schema.
  python     Install Python pip packages from requirements.txt.
  node       Install Node.js LTS, npm, and official @openai/codex.
  bundle     Deploy packaged WIZ bundle files, or build and deploy them.
  migrate    Apply Docker Infra database migrations.
  service    Register and start the WIZ systemd service.
  setup      Apply admin password and initial system settings from installer HTML.
  nginx      Configure nginx reverse proxy for Docker Infra.
  verify     Check DB, service, and initial setup status.
  cleanup    Remove installer API service, HTML, and temporary setup file.
EOF
}

main() {
    local step="all"
    if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
        usage
        exit 0
    fi
    require_root

    if [[ "${1:-}" == "--step" ]]; then
        step="${2:-}"
    elif [[ $# -gt 0 ]]; then
        step="$1"
    fi

    case "$step" in
        all) run_all_steps ;;
        apt) install_apt_packages ;;
        env) ensure_runtime_env ;;
        postgres) install_postgresql_database ;;
        python) install_python_packages ;;
        node) install_nodejs_and_official_codex ;;
        bundle) build_and_deploy_bundle ;;
        migrate) run_database_migrations ;;
        service) register_wiz_service ;;
        setup) run_initial_setup ;;
        nginx) configure_nginx_app ;;
        verify) verify_installation ;;
        cleanup) cleanup_installer ;;
        *) usage; fail "unknown step: $step" ;;
    esac
}

main "$@"
