import datetime
import json
import re
import shutil
import subprocess
import uuid
from pathlib import Path


settings = wiz.model("struct/settings")

SETTING_KEYS = {
    "nginx": "proxy.nginx.paths",
    "apache2": "proxy.apache2.paths",
    "certificates": "proxy.ssl_certificates",
}
DEFAULTS = {
    "nginx": {
        "config_path": "/etc/nginx/nginx.conf",
        "site_path": "/etc/nginx/sites-enabled",
    },
    "apache2": {
        "config_path": "/etc/apache2/apache2.conf",
        "site_path": "/etc/apache2/sites-enabled",
    },
}


def _run(argv, timeout=4):
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
        return {"ok": completed.returncode == 0, "stdout": completed.stdout or "", "stderr": completed.stderr or ""}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"ok": False, "stdout": "", "stderr": ""}


def _load_setting(key, default_value, env=None):
    row = settings.get(key, env=env)
    if row is None or row.get("value") in [None, ""]:
        return json.loads(json.dumps(default_value))
    return row.get("value")


def _save_setting(key, value, description, test_run_id=None, env=None):
    return settings.upsert(
        key=key,
        value=value,
        value_type="json",
        description=description,
        test_run_id=test_run_id,
        metadata={"group": "proxy"},
        env=env,
    )


def _first_existing(*paths):
    for path in paths:
        if path and Path(path).exists():
            return path
    return next((path for path in paths if path), "")


def _service_status(*names):
    for name in names:
        result = _run(["systemctl", "is-active", name], timeout=2)
        status = (result["stdout"] or result["stderr"]).strip()
        if status:
            return {"service_name": name, "daemon_status": status}
    return {"service_name": names[0] if names else "", "daemon_status": "unknown"}


def _parse_nginx(stderr):
    conf = re.search(r"--conf-path=([^ ]+)", stderr)
    prefix = re.search(r"--prefix=([^ ]+)", stderr)
    config_path = conf.group(1) if conf else DEFAULTS["nginx"]["config_path"]
    site_path = _first_existing("/etc/nginx/sites-enabled", "/etc/nginx/conf.d", str(Path(config_path).parent / "conf.d"))
    return {"config_path": config_path, "site_path": site_path, "install_path": prefix.group(1) if prefix else ""}


def _parse_apache(output):
    root = re.search(r'HTTPD_ROOT="([^"]+)"', output)
    conf = re.search(r'SERVER_CONFIG_FILE="([^"]+)"', output)
    install_path = root.group(1) if root else ""
    config_path = conf.group(1) if conf else DEFAULTS["apache2"]["config_path"]
    if install_path and not config_path.startswith("/"):
        config_path = str(Path(install_path) / config_path)
    site_path = _first_existing("/etc/apache2/sites-enabled", "/etc/httpd/conf.d", str(Path(config_path).parent / "sites-enabled"))
    return {"config_path": config_path, "site_path": site_path, "install_path": install_path}


def _cert_datetime(value):
    try:
        return datetime.datetime.strptime(value, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        return None


def _domain_match(domain, pattern):
    domain = str(domain or "").strip().lower()
    pattern = str(pattern or "").strip().lower()
    if not domain or not pattern:
        return False
    if pattern.startswith("*."):
        suffix = pattern[1:]
        return domain.endswith(suffix) and domain != suffix[1:]
    return domain == pattern


class Webserver:
    def _load_saved(self, env=None):
        return {
            "nginx": {**DEFAULTS["nginx"], **dict(_load_setting(SETTING_KEYS["nginx"], DEFAULTS["nginx"], env=env) or {})},
            "apache2": {**DEFAULTS["apache2"], **dict(_load_setting(SETTING_KEYS["apache2"], DEFAULTS["apache2"], env=env) or {})},
            "certificates": list(_load_setting(SETTING_KEYS["certificates"], [], env=env) or []),
        }

    def _detect_nginx(self, saved):
        binary = shutil.which("nginx")
        if not binary:
            return {"key": "nginx", "label": "Nginx", "installed": False, "daemon_status": "missing", "settings": saved}
        version = _run([binary, "-V"])
        detected = _parse_nginx(version["stderr"] or version["stdout"])
        status = _service_status("nginx")
        return {
            "key": "nginx",
            "label": "Nginx",
            "installed": True,
            "binary_path": binary,
            "version": (version["stderr"] or version["stdout"]).splitlines()[0] if (version["stderr"] or version["stdout"]) else "",
            "daemon_status": status["daemon_status"],
            "service_name": status["service_name"],
            "detected_paths": detected,
            "settings": {
                "config_path": saved.get("config_path") or detected["config_path"],
                "site_path": saved.get("site_path") or detected["site_path"],
            },
        }

    def _detect_apache(self, saved):
        binary = shutil.which("apachectl") or shutil.which("apache2ctl") or shutil.which("apache2") or shutil.which("httpd")
        if not binary:
            return {"key": "apache2", "label": "Apache2(httpd)", "installed": False, "daemon_status": "missing", "settings": saved}
        version = _run([binary, "-V"])
        detected = _parse_apache((version["stdout"] or "") + "\n" + (version["stderr"] or ""))
        status = _service_status("apache2", "httpd")
        return {
            "key": "apache2",
            "label": "Apache2(httpd)",
            "installed": True,
            "binary_path": binary,
            "version": (version["stdout"] or version["stderr"]).splitlines()[0] if (version["stdout"] or version["stderr"]) else "",
            "daemon_status": status["daemon_status"],
            "service_name": status["service_name"],
            "detected_paths": detected,
            "settings": {
                "config_path": saved.get("config_path") or detected["config_path"],
                "site_path": saved.get("site_path") or detected["site_path"],
            },
        }

    def _analyze_certificate(self, item):
        entry = {
            "id": item.get("id") or uuid.uuid4().hex,
            "label": str(item.get("label") or "").strip(),
            "cert_path": str(item.get("cert_path") or "").strip(),
            "key_path": str(item.get("key_path") or "").strip(),
            "enabled": bool(item.get("enabled", True)),
        }
        if entry["enabled"] is not True:
            return {**entry, "status": "disabled", "dns_names": [], "key_exists": Path(entry["key_path"]).is_file() if entry["key_path"] else False}
        cert_file = Path(entry["cert_path"]).expanduser()
        if entry["cert_path"] == "" or cert_file.is_file() is False:
            return {**entry, "status": "missing", "message": "인증서 파일을 찾을 수 없습니다.", "dns_names": [], "key_exists": False}
        result = _run(["openssl", "x509", "-in", str(cert_file), "-noout", "-subject", "-issuer", "-dates", "-serial", "-fingerprint", "-ext", "subjectAltName"], timeout=5)
        if result["ok"] is not True:
            return {**entry, "status": "error", "message": (result["stderr"] or result["stdout"]).strip() or "인증서를 분석할 수 없습니다.", "dns_names": [], "key_exists": Path(entry["key_path"]).is_file() if entry["key_path"] else False}
        lines = [line.strip() for line in (result["stdout"] or "").splitlines() if line.strip()]
        subject = next((line.split("=", 1)[1].strip() for line in lines if line.startswith("subject=")), "")
        issuer = next((line.split("=", 1)[1].strip() for line in lines if line.startswith("issuer=")), "")
        not_before = _cert_datetime(next((line.split("=", 1)[1].strip() for line in lines if line.startswith("notBefore=")), ""))
        not_after = _cert_datetime(next((line.split("=", 1)[1].strip() for line in lines if line.startswith("notAfter=")), ""))
        serial = next((line.split("=", 1)[1].strip() for line in lines if line.startswith("serial=")), "")
        fingerprint = next((line.split("=", 1)[1].strip() for line in lines if "Fingerprint=" in line), "")
        dns_names = []
        for line in lines:
            if "DNS:" in line:
                dns_names.extend([segment.strip().replace("DNS:", "") for segment in line.split(",") if "DNS:" in segment])
        expires_at = datetime.datetime.fromisoformat(not_after.replace("Z", "+00:00")) if not_after else None
        days_remaining = None if expires_at is None else int((expires_at - datetime.datetime.now(datetime.timezone.utc)).total_seconds() / 86400)
        status = "valid"
        if days_remaining is not None and days_remaining < 0:
            status = "expired"
        elif days_remaining is not None and days_remaining <= 30:
            status = "expiring"
        return {
            **entry,
            "status": status,
            "subject": subject,
            "issuer": issuer,
            "serial": serial,
            "fingerprint": fingerprint,
            "dns_names": sorted(set(dns_names)),
            "not_before": not_before,
            "not_after": not_after,
            "days_remaining": days_remaining,
            "key_exists": Path(entry["key_path"]).expanduser().is_file() if entry["key_path"] else False,
        }

    def _certificate_summary(self, certificates):
        summary = {"total": len(certificates), "valid": 0, "expiring": 0, "expired": 0, "error": 0, "disabled": 0, "missing": 0}
        for item in certificates:
            key = item.get("status") or "error"
            if key in summary:
                summary[key] += 1
            else:
                summary["error"] += 1
        return summary

    def load(self, env=None):
        saved = self._load_saved(env=env)
        servers = {
            "nginx": self._detect_nginx(saved["nginx"]),
            "apache2": self._detect_apache(saved["apache2"]),
        }
        certificates = [self._analyze_certificate(item) for item in saved["certificates"]]
        active_server = "none"
        if servers["nginx"].get("daemon_status") == "active":
            active_server = "nginx"
        elif servers["apache2"].get("daemon_status") == "active":
            active_server = "apache2"
        elif servers["nginx"].get("installed"):
            active_server = "nginx"
        elif servers["apache2"].get("installed"):
            active_server = "apache2"
        return {
            "active_server": active_server,
            "servers": servers,
            "certificates": certificates,
            "certificate_summary": self._certificate_summary(certificates),
        }

    def save(self, payload, test_run_id=None, env=None):
        payload = dict(payload or {})
        nginx = dict(payload.get("nginx") or {})
        apache2 = dict(payload.get("apache2") or {})
        certificates = []
        for item in list(payload.get("certificates") or []):
            certificates.append({
                "id": item.get("id") or uuid.uuid4().hex,
                "label": str(item.get("label") or "").strip(),
                "cert_path": str(item.get("cert_path") or "").strip(),
                "key_path": str(item.get("key_path") or "").strip(),
                "enabled": bool(item.get("enabled", True)),
            })
        _save_setting(SETTING_KEYS["nginx"], {"config_path": str(nginx.get("config_path") or "").strip(), "site_path": str(nginx.get("site_path") or "").strip()}, "Nginx path settings", test_run_id=test_run_id, env=env)
        _save_setting(SETTING_KEYS["apache2"], {"config_path": str(apache2.get("config_path") or "").strip(), "site_path": str(apache2.get("site_path") or "").strip()}, "Apache path settings", test_run_id=test_run_id, env=env)
        _save_setting(SETTING_KEYS["certificates"], certificates, "SSL certificate entries", test_run_id=test_run_id, env=env)
        return self.load(env=env)

    def certificates_for_domain(self, domain, env=None):
        runtime = self.load(env=env)
        certificates = [
            item for item in runtime["certificates"]
            if any(_domain_match(domain, hostname) for hostname in (item.get("dns_names") or []))
        ]
        return {"certificates": certificates, "summary": self._certificate_summary(certificates)}


Model = Webserver()
