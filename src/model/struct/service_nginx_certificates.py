import json
import re
from pathlib import Path


local_executor = wiz.model("struct/local_executor")
webserver = wiz.model("struct/webserver")
config = wiz.config("docker_infra")
USABLE_CERT_STATUSES = {"valid", "expiring"}


def _safe_segment(value):
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "").strip()).strip(".-") or "service"


class ServiceNginxCertificates:
    def _usable(self, cert):
        return (
            cert
            and cert.get("status") in USABLE_CERT_STATUSES
            and cert.get("key_exists") is True
            and cert.get("key_matches") is not False
            and cert.get("key_permission_secure") is not False
        )

    def self_signed_test_enabled(self, env=None):
        return config.self_signed_cert_test_enabled(env)

    def _letsencrypt_cert(self, domain):
        live = Path("/etc/letsencrypt/live") / _safe_segment(domain)
        cert_path = live / "fullchain.pem"
        key_path = live / "privkey.pem"
        if not cert_path.is_file() or not key_path.is_file():
            return None
        try:
            return webserver._analyze_certificate({
                "domain": domain,
                "label": f"Let's Encrypt {domain}",
                "cert_path": str(cert_path),
                "key_path": str(key_path),
                "enabled": True,
                "metadata": {"source": "certbot", "cert_name": _safe_segment(domain), "live_dir": str(live)},
            })
        except Exception:
            return {
                "domain": domain,
                "cert_path": str(cert_path),
                "key_path": str(key_path),
                "status": "error",
                "key_exists": key_path.is_file(),
                "metadata": {"source": "certbot", "cert_name": _safe_segment(domain), "live_dir": str(live)},
            }

    def _self_signed_paths(self, domain, env=None):
        root = Path(config.data_dir(env)) / "test-self-signed-certificates" / _safe_segment(domain)
        return root, root / "certificate.pem", root / "private.key"

    def _self_signed_cert(self, domain, env=None):
        _root, cert_path, key_path = self._self_signed_paths(domain, env=env)
        if not cert_path.is_file() or not key_path.is_file():
            return None
        try:
            return webserver._analyze_certificate({
                "domain": domain,
                "label": f"Self-signed test {domain}",
                "cert_path": str(cert_path),
                "key_path": str(key_path),
                "enabled": True,
                "metadata": {"source": "self_signed_test"},
            })
        except Exception:
            return {
                "domain": domain,
                "cert_path": str(cert_path),
                "key_path": str(key_path),
                "status": "error",
                "key_exists": key_path.is_file(),
                "metadata": {"source": "self_signed_test"},
            }

    def valid_cert(self, domain, zone_id=None, env=None):
        certs = webserver.certificates_for_domain(domain, zone_id=zone_id, env=env).get("certificates") or []
        for item in certs:
            if self._usable(item):
                return item
        candidates = [self._letsencrypt_cert(domain)]
        if self.self_signed_test_enabled(env=env):
            candidates.append(self._self_signed_cert(domain, env=env))
        for item in candidates:
            if self._usable(item):
                return item
        return None

    def certbot_certificate(self, domain, env=None):
        return self._letsencrypt_cert(str(domain or "").strip().lower())

    def certificate_mode(self, cert):
        source = (cert or {}).get("metadata", {}).get("source")
        if source == "certbot":
            return "certbot"
        if source == "self_signed_test":
            return "self_signed"
        return "existing" if cert else "http"

    def automatic_renewal_status(self, env=None):
        result = local_executor.run("certbot.renewal.status", timeout_seconds=20, env=env)
        payload = {}
        if result.get("status") == "ok":
            try:
                payload = json.loads(result.get("stdout") or "{}")
            except Exception:
                payload = {}
        return {
            "status": result.get("status"),
            "configured": bool(payload.get("configured")),
            "method": payload.get("method") or "unknown",
            "schedule": payload.get("schedule") or "",
            "installed": bool(payload.get("installed")),
            "details": payload,
            "check": result,
        }

    def ensure_automatic_renewal(self, commands, env=None):
        result = local_executor.run("certbot.renewal.ensure", timeout_seconds=120, env=env)
        commands.append({"step": "certbot auto renewal", "result": result})
        return result

    def service_certificates(self, domains, env=None):
        rows = []
        for row in domains or []:
            domain = str(row.get("domain") or "").strip().lower()
            if not domain:
                continue
            metadata = dict(row.get("metadata") or {})
            cert = self.certbot_certificate(domain, env=env)
            requested = row.get("ssl_mode") == "certbot"
            applied = metadata.get("nginx_ssl_mode") == "certbot"
            detected = (cert or {}).get("metadata", {}).get("source") == "certbot"
            if not requested and not applied and not detected:
                continue
            rows.append({
                "domain_id": str(row.get("id") or ""),
                "domain": domain,
                "requested_ssl_mode": row.get("ssl_mode"),
                "applied_ssl_mode": metadata.get("nginx_ssl_mode"),
                "certificate": cert,
                "auto_renewal": None,
                "manual_renew_enabled": bool(cert and cert.get("cert_path")),
            })
        if rows:
            renewal = self.automatic_renewal_status(env=env)
            for row in rows:
                row["auto_renewal"] = renewal
        return rows

    def renew_certificate(self, domain, commands=None, env=None):
        commands = commands if commands is not None else []
        cert_name = _safe_segment(str(domain or "").strip().lower())
        result = local_executor.run(
            "certbot.renew",
            params={"cert_name": cert_name, "force": True},
            timeout_seconds=300,
            env=env,
        )
        commands.append({"step": f"certbot renew {cert_name}", "result": result})
        if result.get("status") != "ok":
            raise RuntimeError(f"{domain} 무료 인증서를 갱신할 수 없습니다.")
        renewal = self.ensure_automatic_renewal(commands, env=env)
        return {
            "domain": str(domain or "").strip().lower(),
            "certificate": self.certbot_certificate(domain, env=env),
            "auto_renewal": self.automatic_renewal_status(env=env),
            "renewal_ensure": renewal,
            "commands": commands,
        }

    def issue_certificates(self, targets, commands, env=None):
        issued_certbot = False
        for domain in targets:
            if config.self_signed_cert_test_enabled(env):
                root, cert_path, key_path = self._self_signed_paths(domain, env=env)
                root.mkdir(parents=True, exist_ok=True)
                result = local_executor.run(
                    "openssl.self_signed_cert.issue",
                    params={
                        "domain": domain,
                        "cert_path": str(cert_path),
                        "key_path": str(key_path),
                        "days": config.self_signed_cert_days(env),
                    },
                    timeout_seconds=30,
                    env=env,
                )
                commands.append({"step": f"self-signed cert {domain}", "result": result})
                if result.get("status") != "ok":
                    raise RuntimeError(f"{domain} 테스트 인증서를 발급할 수 없습니다.")
                continue
            result = local_executor.run(
                "certbot.nginx.issue",
                params={
                    "domain": domain,
                    "email": config.certbot_email(env),
                    "staging": config.certbot_staging(env),
                },
                timeout_seconds=300,
                env=env,
            )
            commands.append({"step": f"certbot {domain}", "result": result})
            if result.get("status") != "ok":
                raise RuntimeError(f"{domain} 무료 인증서를 발급할 수 없습니다.")
            issued_certbot = True
        if issued_certbot:
            self.ensure_automatic_renewal(commands, env=env)


Model = ServiceNginxCertificates()
