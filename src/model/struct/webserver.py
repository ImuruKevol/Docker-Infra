import datetime
import json
import re
import shutil
import subprocess
import uuid
from pathlib import Path


settings = wiz.model("struct/settings")
config = wiz.config("docker_infra")

CERTIFICATE_SETTING_KEY = "domains.ssl_certificates"
LEGACY_CERTIFICATE_SETTING_KEY = "proxy.ssl_certificates"
DEFAULT_NGINX = {
    "key": "nginx",
    "label": "Nginx",
    "service_name": "nginx",
    "binary_path": "/usr/sbin/nginx",
    "config_path": "/etc/nginx/nginx.conf",
    "site_path": "/etc/nginx/sites-enabled",
    "available_site_path": "/etc/nginx/sites-available",
    "ssl_certificate_dir": "/etc/ssl/certs",
    "ssl_key_dir": "/etc/ssl/private",
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
        metadata={"group": "domains"},
        env=env,
    )


def _service_status(name):
    result = _run(["systemctl", "is-active", name], timeout=2)
    status = (result["stdout"] or result["stderr"]).strip()
    return status or "unknown"


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


def _safe_segment(value, fallback="domain"):
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value or "").strip()).strip(".-")
    return cleaned or fallback


def _certificate_id():
    return uuid.uuid4().hex


class Webserver:
    def nginx_defaults(self):
        binary = shutil.which("nginx") or DEFAULT_NGINX["binary_path"]
        version = _run([binary, "-v"]) if binary else {"ok": False, "stdout": "", "stderr": ""}
        installed = Path(binary).exists() or shutil.which("nginx") is not None
        return {
            **DEFAULT_NGINX,
            "installed": installed,
            "binary_path": binary,
            "daemon_status": _service_status(DEFAULT_NGINX["service_name"]) if installed else "missing",
            "version": (version["stderr"] or version["stdout"]).splitlines()[0] if (version["stderr"] or version["stdout"]) else "",
            "fixed": True,
            "settings": {
                "config_path": DEFAULT_NGINX["config_path"],
                "site_path": DEFAULT_NGINX["site_path"],
                "service_name": DEFAULT_NGINX["service_name"],
            },
        }

    def _load_certificates(self, env=None):
        certificates = list(_load_setting(CERTIFICATE_SETTING_KEY, [], env=env) or [])
        if certificates:
            return certificates
        return list(_load_setting(LEGACY_CERTIFICATE_SETTING_KEY, [], env=env) or [])

    def _save_certificates(self, certificates, test_run_id=None, env=None):
        normalized = []
        for item in certificates or []:
            normalized.append({
                "id": item.get("id") or _certificate_id(),
                "zone_id": str(item.get("zone_id") or "").strip(),
                "domain": str(item.get("domain") or "").strip().lower(),
                "label": str(item.get("label") or "").strip(),
                "cert_path": str(item.get("cert_path") or "").strip(),
                "key_path": str(item.get("key_path") or "").strip(),
                "enabled": bool(item.get("enabled", True)),
                "metadata": dict(item.get("metadata") or {}),
            })
        _save_setting(CERTIFICATE_SETTING_KEY, normalized, "Domain SSL certificate entries", test_run_id=test_run_id, env=env)
        return normalized

    def _analyze_certificate(self, item):
        entry = {
            "id": item.get("id") or _certificate_id(),
            "zone_id": str(item.get("zone_id") or "").strip(),
            "domain": str(item.get("domain") or "").strip().lower(),
            "label": str(item.get("label") or "").strip(),
            "cert_path": str(item.get("cert_path") or "").strip(),
            "key_path": str(item.get("key_path") or "").strip(),
            "enabled": bool(item.get("enabled", True)),
            "metadata": dict(item.get("metadata") or {}),
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
        certificates = [self._analyze_certificate(item) for item in self._load_certificates(env=env)]
        nginx = self.nginx_defaults()
        return {
            "active_server": "nginx",
            "server": nginx,
            "servers": {"nginx": nginx},
            "certificates": certificates,
            "certificate_summary": self._certificate_summary(certificates),
        }

    def save(self, payload, test_run_id=None, env=None):
        certificates = self._save_certificates(list((payload or {}).get("certificates") or []), test_run_id=test_run_id, env=env)
        analyzed = [self._analyze_certificate(item) for item in certificates]
        return {
            "active_server": "nginx",
            "server": self.nginx_defaults(),
            "servers": {"nginx": self.nginx_defaults()},
            "certificates": analyzed,
            "certificate_summary": self._certificate_summary(analyzed),
        }

    def certificate_storage_dir(self, domain, certificate_id, env=None):
        root = Path(config.data_dir(env)) / "domain-certificates" / _safe_segment(domain)
        path = root / _safe_segment(certificate_id, "certificate")
        path.mkdir(parents=True, exist_ok=True)
        return path

    def store_uploaded_certificate(self, zone_id, domain, label, cert_file, key_file, test_run_id=None, env=None):
        if cert_file is None:
            raise ValueError("인증서 파일을 선택해주세요.")
        if key_file is None:
            raise ValueError("키 파일을 선택해주세요.")

        certificate_id = _certificate_id()
        storage_dir = self.certificate_storage_dir(domain, certificate_id, env=env)
        cert_path = storage_dir / "certificate.pem"
        key_path = storage_dir / "private.key"
        cert_file.save(str(cert_path))
        key_file.save(str(key_path))

        entry = {
            "id": certificate_id,
            "zone_id": str(zone_id or ""),
            "domain": str(domain or "").strip().lower(),
            "label": str(label or "").strip() or str(domain or "").strip().lower(),
            "cert_path": str(cert_path),
            "key_path": str(key_path),
            "enabled": True,
            "metadata": {
                "source": "domain_upload",
                "uploaded_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
            },
        }
        certificates = self._load_certificates(env=env)
        certificates.append(entry)
        self._save_certificates(certificates, test_run_id=test_run_id, env=env)
        return self._analyze_certificate(entry)

    def delete_certificate(self, certificate_id, zone_id=None, test_run_id=None, env=None):
        target_id = str(certificate_id or "").strip()
        if not target_id:
            raise ValueError("certificate_id가 필요합니다.")
        certificates = self._load_certificates(env=env)
        removed = None
        remaining = []
        for item in certificates:
            if str(item.get("id") or "") == target_id and (not zone_id or str(item.get("zone_id") or "") == str(zone_id)):
                removed = item
                continue
            remaining.append(item)
        if removed is None:
            raise ValueError("인증서를 찾을 수 없습니다.")
        self._save_certificates(remaining, test_run_id=test_run_id, env=env)
        cert_path = Path(str(removed.get("cert_path") or "")).expanduser()
        storage_dir = cert_path.parent if cert_path.name == "certificate.pem" else None
        if storage_dir and storage_dir.exists() and "domain-certificates" in storage_dir.as_posix():
            shutil.rmtree(storage_dir, ignore_errors=True)
        return {"deleted": True, "id": target_id}

    def certificates_for_domain(self, domain, zone_id=None, env=None):
        runtime = self.load(env=env)
        certificates = []
        for item in runtime["certificates"]:
            if zone_id and str(item.get("zone_id") or "") == str(zone_id):
                certificates.append(item)
                continue
            if any(_domain_match(domain, hostname) for hostname in (item.get("dns_names") or [])):
                certificates.append(item)
        return {"certificates": certificates, "summary": self._certificate_summary(certificates)}


Model = Webserver()
