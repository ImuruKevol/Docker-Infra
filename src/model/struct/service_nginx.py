import re
from pathlib import Path

from psycopg.types.json import Jsonb


connect = wiz.model("db/postgres").connect
local_executor = wiz.model("struct/local_executor")
webserver = wiz.model("struct/webserver")
certificates = wiz.model("struct/service_nginx_certificates")
domains_model = wiz.model("struct/domains")
ddns_model = wiz.model("struct/domains_ddns")
config = wiz.config("docker_infra")

DOMAIN_RE = re.compile(r"^[A-Za-z0-9*.][A-Za-z0-9.*-]{0,251}[A-Za-z0-9]$")
PROXY_HOST_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")


def _safe_segment(value):
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "").strip()).strip(".-") or "service"


def _read(path):
    if not path.exists():
        return None
    if path.is_symlink():
        return {"type": "symlink", "target": str(path.readlink())}
    return {"type": "file", "content": path.read_text(encoding="utf-8")}


def _restore(path, snapshot):
    if path.exists() or path.is_symlink():
        path.unlink()
    if snapshot is None:
        return
    if snapshot.get("type") == "symlink":
        path.symlink_to(snapshot.get("target"))
        return
    path.write_text(snapshot.get("content") or "", encoding="utf-8")


def _proxy_host(value):
    host = str(value or "").strip()
    if not host or PROXY_HOST_RE.match(host) is None:
        host = "127.0.0.1"
    if ":" in host and not host.startswith("[") and host.count(":") >= 2:
        return f"[{host}]"
    return host


def _proxy_location(host, port):
    upstream = f"{_proxy_host(host)}:{int(port)}"
    return f"""
    location / {{
        proxy_pass http://{upstream};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }}
""".rstrip()


def _comment_value(value):
    return re.sub(r"[\r\n#]+", " ", str(value or "")).strip()


def _truthy(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _domain_dns_provider(metadata):
    provider = str((metadata or {}).get("dns_provider") or "").strip().lower()
    if provider == "ddns" or (metadata or {}).get("ddns_endpoint_id"):
        return "ddns"
    return provider or "managed"


def _preferred_proxy_host(metadata):
    metadata = metadata or {}
    topology = str(metadata.get("proxy_topology") or "").strip()
    if _truthy(metadata.get("proxy_node_is_local_master")) or topology == "local-master":
        return "127.0.0.1"
    if topology == "remote-node" and str(metadata.get("proxy_registered_node_private_host") or "").strip():
        return str(metadata.get("proxy_registered_node_private_host") or "").strip()
    if topology == "swarm-node" and str(metadata.get("proxy_swarm_addr") or "").strip():
        return str(metadata.get("proxy_swarm_addr") or "").strip()
    for key in ["proxy_host", "proxy_registered_node_private_host", "proxy_swarm_addr", "proxy_registered_node_host"]:
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    return "127.0.0.1"


def _proxy_topology(metadata, proxy_host):
    metadata = metadata or {}
    explicit = str(metadata.get("proxy_topology") or "").strip()
    if explicit:
        return explicit
    if _truthy(metadata.get("proxy_node_is_local_master")):
        return "local-master"
    if metadata.get("proxy_registered_node_private_host") or metadata.get("proxy_node_registered"):
        return "remote-node"
    if metadata.get("proxy_swarm_addr"):
        return "swarm-node"
    if _proxy_host(proxy_host) in {"127.0.0.1", "localhost", "::1", "[::1]"}:
        return "local-default"
    return "remote-node"


def _domain_proxy_profile(domain_row):
    domain_row = domain_row or {}
    domain = str(domain_row.get("domain") or "").strip().lower()
    if DOMAIN_RE.match(domain) is None:
        raise ValueError(f"{domain} 도메인 형식이 올바르지 않습니다.")
    metadata = dict(domain_row.get("metadata") or {})
    port = int(metadata.get("published_port") or domain_row.get("port") or metadata.get("target_port") or 80)
    proxy_host = _preferred_proxy_host(metadata)
    dns_provider = _domain_dns_provider(metadata)
    dns_mode = (
        metadata.get("ddns_mode")
        or metadata.get("dns_mode")
        or ("ddns_management" if dns_provider == "ddns" else "managed_dns")
    )
    topology = _proxy_topology(metadata, proxy_host)
    return {
        "domain": domain,
        "metadata": metadata,
        "port": port,
        "proxy_host": _proxy_host(proxy_host),
        "dns_provider": dns_provider,
        "dns_mode": str(dns_mode or "").strip(),
        "dns_proxied": metadata.get("dns_proxied") is True,
        "ddns_endpoint_id": str(metadata.get("ddns_endpoint_id") or "").strip(),
        "ddns_domain_suffix": str(metadata.get("ddns_domain_suffix") or metadata.get("wildcard_suffix") or "").strip(),
        "proxy_topology": topology,
        "proxy_node_name": str(metadata.get("proxy_node_name") or "").strip(),
        "proxy_node_is_local_master": topology == "local-master" or _truthy(metadata.get("proxy_node_is_local_master")),
        "proxy_registered_node_private_host": str(metadata.get("proxy_registered_node_private_host") or "").strip(),
        "proxy_registered_node_public_ip": str(metadata.get("proxy_registered_node_public_ip") or "").strip(),
        "proxy_swarm_addr": str(metadata.get("proxy_swarm_addr") or "").strip(),
    }


def _render_header(profile):
    profile = profile or {}
    lines = ["# Managed by Docker Infra. Do not edit this file directly."]
    lines.append(f"# DNS provider: {_comment_value(profile.get('dns_provider') or 'managed')}")
    lines.append(f"# DNS mode: {_comment_value(profile.get('dns_mode') or 'managed_dns')}")
    if profile.get("dns_proxied") is True:
        lines.append("# DNS proxy: enabled")
    if profile.get("ddns_endpoint_id"):
        lines.append(f"# DDNS endpoint: {_comment_value(profile.get('ddns_endpoint_id'))}")
    if profile.get("ddns_domain_suffix"):
        lines.append(f"# DDNS suffix: {_comment_value(profile.get('ddns_domain_suffix'))}")
    lines.append(f"# Proxy topology: {_comment_value(profile.get('proxy_topology') or 'local-default')}")
    if profile.get("proxy_node_name"):
        lines.append(f"# Proxy node: {_comment_value(profile.get('proxy_node_name'))}")
    lines.append(f"# Proxy upstream: {_comment_value(profile.get('proxy_host'))}:{int(profile.get('port') or 80)}")
    if profile.get("proxy_registered_node_public_ip"):
        lines.append(f"# Proxy node public IP: {_comment_value(profile.get('proxy_registered_node_public_ip'))}")
    return "\n".join(lines)


def _render(domain, host, port, cert=None, profile=None):
    header = _render_header(profile or {"dns_provider": "managed", "dns_mode": "managed_dns", "proxy_host": host, "port": port})
    if cert:
        return f"""{header}
server {{
    listen 80;
    server_name {domain};
    return 301 https://$host$request_uri;
}}

server {{
    listen 443 ssl;
    server_name {domain};
    ssl_certificate {cert["cert_path"]};
    ssl_certificate_key {cert["key_path"]};
{_proxy_location(host, port)}
}}
"""
    return f"""{header}
server {{
    listen 80;
    server_name {domain};
{_proxy_location(host, port)}
}}
"""


class ServiceNginx:
    def _paths(self, domain, env=None):
        nginx = webserver.nginx_defaults()
        available = Path(nginx.get("available_site_path") or "/etc/nginx/sites-available")
        enabled = Path(nginx.get("site_path") or "/etc/nginx/sites-enabled")
        filename = f"docker-infra-{_safe_segment(domain)}.conf"
        return nginx, available / filename, enabled / filename

    def render_preview(self, domain_row, env=None):
        profile = _domain_proxy_profile(domain_row)
        domain = profile["domain"]
        metadata = profile["metadata"]
        cert = certificates.valid_cert(domain, zone_id=metadata.get("zone_id"), env=env)
        return {
            "content": _render(domain, profile["proxy_host"], profile["port"], cert=cert, profile=profile),
            "port": profile["port"],
            "proxy_host": profile["proxy_host"],
            "ssl_mode": certificates.certificate_mode(cert),
            "dns_provider": profile["dns_provider"],
            "dns_mode": profile["dns_mode"],
            "proxy_topology": profile["proxy_topology"],
            "proxy_node_name": profile["proxy_node_name"],
            "proxy_node_is_local_master": profile["proxy_node_is_local_master"],
        }

    def _domain_rows(self, service_id, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM services WHERE id = %s", (service_id,))
                service = cursor.fetchone()
                cursor.execute("SELECT * FROM service_domains WHERE service_id = %s ORDER BY created_at ASC", (service_id,))
                domains = [dict(row) for row in cursor.fetchall()]
        return dict(service) if service else None, domains

    def _write_domain(self, domain_row, env=None):
        profile = _domain_proxy_profile(domain_row)
        domain = profile["domain"]
        metadata = profile["metadata"]
        cert = certificates.valid_cert(domain, zone_id=metadata.get("zone_id"), env=env)
        nginx, available_path, enabled_path = self._paths(domain, env=env)
        if nginx.get("installed") is not True:
            raise RuntimeError("nginx가 설치되어 있지 않습니다.")
        available_path.parent.mkdir(parents=True, exist_ok=True)
        enabled_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot = {"available": _read(available_path), "enabled": _read(enabled_path)}
        available_path.write_text(_render(domain, profile["proxy_host"], profile["port"], cert=cert, profile=profile), encoding="utf-8")
        if enabled_path.exists() or enabled_path.is_symlink():
            enabled_path.unlink()
        enabled_path.symlink_to(available_path)
        return {
            "id": str(domain_row.get("id")),
            "domain": domain,
            "port": profile["port"],
            "proxy_host": profile["proxy_host"],
            "ssl_mode": certificates.certificate_mode(cert),
            "dns_provider": profile["dns_provider"],
            "dns_mode": profile["dns_mode"],
            "dns_proxied": profile["dns_proxied"],
            "ddns_endpoint_id": profile["ddns_endpoint_id"],
            "ddns_domain_suffix": profile["ddns_domain_suffix"],
            "proxy_topology": profile["proxy_topology"],
            "proxy_node_name": profile["proxy_node_name"],
            "proxy_node_is_local_master": profile["proxy_node_is_local_master"],
            "proxy_registered_node_private_host": profile["proxy_registered_node_private_host"],
            "proxy_registered_node_public_ip": profile["proxy_registered_node_public_ip"],
            "proxy_swarm_addr": profile["proxy_swarm_addr"],
            "available_path": str(available_path),
            "enabled_path": str(enabled_path),
            "snapshot": snapshot,
        }

    def _restore_domain(self, applied):
        available_path = Path(applied["available_path"])
        enabled_path = Path(applied["enabled_path"])
        snapshot = applied.get("snapshot") or {}
        _restore(available_path, snapshot.get("available"))
        _restore(enabled_path, snapshot.get("enabled"))

    def _mark_domains(self, applied, env=None):
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                for item in applied:
                    cursor.execute("SELECT * FROM service_domains WHERE id = %s", (item["id"],))
                    row = cursor.fetchone()
                    if row is None:
                        continue
                    metadata = dict(row["metadata"] or {})
                    metadata.update({
                        "nginx_config_path": item["available_path"],
                        "nginx_enabled_path": item["enabled_path"],
                        "nginx_ssl_mode": item["ssl_mode"],
                        "published_port": item["port"],
                        "proxy_host": item["proxy_host"],
                        "dns_provider": item["dns_provider"],
                        "dns_mode": item["dns_mode"],
                        "dns_proxied": item["dns_proxied"],
                        "proxy_topology": item["proxy_topology"],
                        "proxy_node_name": item["proxy_node_name"],
                        "proxy_node_is_local_master": item["proxy_node_is_local_master"],
                        "proxy_registered_node_private_host": item["proxy_registered_node_private_host"],
                        "proxy_registered_node_public_ip": item["proxy_registered_node_public_ip"],
                        "proxy_swarm_addr": item["proxy_swarm_addr"],
                    })
                    if item["dns_provider"] == "ddns":
                        metadata.setdefault("ddns_mode", item["dns_mode"] or "ddns_management")
                    if item["ddns_endpoint_id"]:
                        metadata["ddns_endpoint_id"] = item["ddns_endpoint_id"]
                    if item["ddns_domain_suffix"]:
                        metadata["ddns_domain_suffix"] = item["ddns_domain_suffix"]
                    cursor.execute("UPDATE service_domains SET metadata = %s, updated_at = now() WHERE id = %s", (Jsonb(metadata), row["id"]))

    def _check_and_reload(self, commands, label, env=None):
        configtest = local_executor.run("proxy.nginx.configtest", timeout_seconds=20, env=env)
        commands.append({"step": f"{label} configtest", "result": configtest})
        if configtest.get("status") != "ok":
            raise RuntimeError("nginx 설정 검사를 통과하지 못했습니다.")
        reload_result = local_executor.run("proxy.nginx.reload", timeout_seconds=20, env=env)
        commands.append({"step": f"{label} reload", "result": reload_result})
        if reload_result.get("status") != "ok":
            raise RuntimeError("nginx reload에 실패했습니다.")

    def _certbot_targets(self, domains, env=None):
        targets = []
        self_signed_test = certificates.self_signed_test_enabled(env=env)
        for row in domains:
            domain = str(row.get("domain") or "").strip().lower()
            metadata = dict(row.get("metadata") or {})
            if row.get("ssl_mode") != "certbot" and self_signed_test is not True:
                continue
            if certificates.valid_cert(domain, zone_id=metadata.get("zone_id"), env=env):
                continue
            targets.append(domain)
        return sorted(set(targets))

    def _issue_certificates(self, targets, commands, env=None):
        certificates.issue_certificates(targets, commands, env=env)

    def _ensure_dns_records(self, domains, commands, env=None):
        ensured = []
        public_dns_content = None
        for row in domains:
            domain = str(row.get("domain") or "").strip().lower()
            metadata = dict(row.get("metadata") or {})
            if not domain:
                continue
            if self._uses_ddns_provider(row):
                result = {"status": "skipped", "domain": domain, "reason": "ddns_managed"}
            else:
                if public_dns_content is None:
                    public_dns_content = config.public_dns_address(env=env) or config.public_dns_address(env=env, record_type="AAAA")
                result = domains_model.ensure_service_dns_record(
                    domain,
                    zone_config_id=metadata.get("zone_id"),
                    content=public_dns_content,
                    proxied=metadata.get("dns_proxied") is True,
                    env=env,
                )
            ensured.append(result)
            commands.append({
                "step": f"dns {domain}",
                "result": {
                    "status": "ok" if result.get("status") in {"ok", "skipped"} else "error",
                    "stdout": result,
                    "stderr": "",
                    "exit_code": 0 if result.get("status") in {"ok", "skipped"} else 1,
                },
            })
        return ensured

    def _uses_ddns_provider(self, domain_row):
        metadata = dict(domain_row.get("metadata") or {})
        return metadata.get("dns_provider") == "ddns" or bool(metadata.get("ddns_endpoint_id"))

    def _ddns_domains(self, domains):
        return [row for row in domains if self._uses_ddns_provider(row)]

    def apply(self, service_id, env=None):
        service, domains = self._domain_rows(service_id, env=env)
        if not service:
            return {"status": "skipped", "message": "서비스를 찾을 수 없습니다.", "applied": []}
        if not domains:
            return {"status": "skipped", "message": "연결된 도메인이 없습니다.", "applied": []}
        nginx_domains = domains
        applied = []
        active_applied = []
        commands = []
        try:
            for domain in nginx_domains:
                applied.append(self._write_domain(domain, env=env))
            active_applied = list(applied)
            dns_records = []
            ddns_result = {"status": "skipped", "registered": [], "skipped": [], "failures": []}
            if nginx_domains:
                self._check_and_reload(commands, "nginx", env=env)
                dns_records = self._ensure_dns_records(nginx_domains, commands, env=env)
                ddns_domains = self._ddns_domains(nginx_domains)
                if ddns_domains:
                    ddns_result = ddns_model.register_service_domains(service_id, domain_rows=ddns_domains, env=env)
                    commands.append({
                        "step": "ddns register",
                        "result": {
                            "status": "ok" if ddns_result.get("status") in {"ok", "skipped"} else "error",
                            "stdout": ddns_result,
                            "stderr": "",
                            "exit_code": 0 if ddns_result.get("status") in {"ok", "skipped"} else 1,
                        },
                    })
            certbot_targets = self._certbot_targets(nginx_domains, env=env)
            if certbot_targets:
                self._issue_certificates(certbot_targets, commands, env=env)
                active_applied = []
                for domain in nginx_domains:
                    reapplied = self._write_domain(domain, env=env)
                    applied.append(reapplied)
                    active_applied.append(reapplied)
                self._check_and_reload(commands, "nginx ssl", env=env)
            self._mark_domains(active_applied, env=env)
            public_applied = [{key: value for key, value in item.items() if key != "snapshot"} for item in active_applied]
            message = "nginx 설정을 적용했습니다."
            if ddns_result.get("status") == "ok":
                message = "nginx 설정과 DDNS DNS 등록을 적용했습니다."
            return {"status": "ok", "message": message, "applied": public_applied, "dns_records": dns_records, "ddns": ddns_result, "commands": commands}
        except Exception as exc:
            for item in reversed(applied):
                self._restore_domain(item)
            rollback = {"status": "skipped", "stdout": "", "stderr": "", "exit_code": 0}
            if applied:
                rollback = local_executor.run("proxy.nginx.configtest", timeout_seconds=20, env=env)
            commands.append({"step": "nginx rollback configtest", "result": rollback})
            public_applied = [{key: value for key, value in item.items() if key != "snapshot"} for item in applied]
            return {"status": "error", "message": str(exc), "applied": public_applied, "commands": commands}


Model = ServiceNginx()
