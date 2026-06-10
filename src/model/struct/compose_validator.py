import copy


rules = wiz.model("struct/compose_rules")
NAMESPACE_PATTERN = rules.NAMESPACE_PATTERN
DEFAULT_FILENAME = rules.DEFAULT_FILENAME
ALLOWED_FILENAMES = rules.ALLOWED_FILENAMES
OVERLAY_NETWORK = rules.OVERLAY_NETWORK
DEFAULT_UPDATE_CONFIG = rules.DEFAULT_UPDATE_CONFIG
DEFAULT_ROLLBACK_CONFIG = rules.DEFAULT_ROLLBACK_CONFIG
DEFAULT_RESTART_POLICY = rules.DEFAULT_RESTART_POLICY
ComposeValidationError = rules.ComposeValidationError
_error = rules.error
_merge_defaults = rules.merge_defaults
_has_health_check_override = rules.has_health_check_override
_load_compose = rules.load_compose
_network_names = rules.network_names
_qualify_environment_refs = rules.qualify_environment_refs


def _safe_int(value, fallback=0):
    try:
        return int(value)
    except Exception:
        return fallback


def _has_host_published_ports(service):
    for item in service.get("ports") or []:
        if not isinstance(item, dict):
            continue
        mode = str(item.get("mode") or "").strip().lower()
        if mode == "host" and _safe_int(item.get("published") or item.get("target"), 0) > 0:
            return True
    return False


class ComposeValidator:
    ComposeValidationError = ComposeValidationError

    def validate(self, payload):
        payload = payload or {}
        errors = []
        warnings = []
        warning_codes = set(payload.get("warning_codes") or [])
        allow_warnings = bool(payload.get("allow_warnings"))
        filename = payload.get("filename") or DEFAULT_FILENAME
        namespace = payload.get("namespace")
        has_health_check = _has_health_check_override(payload)

        if filename not in ALLOWED_FILENAMES:
            errors.append(
                _error(
                    "filename",
                    "INVALID_COMPOSE_FILENAME",
                    "Compose filename은 docker-compose.yaml 또는 docker-compose.yml이어야 합니다.",
                    allowed=sorted(ALLOWED_FILENAMES),
                )
            )

        if not isinstance(namespace, str) or not NAMESPACE_PATTERN.fullmatch(namespace):
            errors.append(
                _error(
                    "namespace",
                    "INVALID_NAMESPACE",
                    "namespace는 ^[a-z0-9_]+$ 규칙을 따라야 합니다.",
                )
            )

        compose, load_errors = _load_compose(payload)
        errors.extend(load_errors)
        if compose is None:
            self._raise_if_errors(errors)

        if not isinstance(compose, dict):
            errors.append(
                _error("content", "INVALID_COMPOSE_DOCUMENT", "Compose 문서 root는 object여야 합니다.")
            )
            self._raise_if_errors(errors)

        normalized = copy.deepcopy(compose)
        services = normalized.get("services")
        if not isinstance(services, dict) or not services:
            errors.append(
                _error("services", "SERVICES_REQUIRED", "Compose services object는 필수입니다.")
            )
            self._raise_if_errors(errors)

        root_networks = normalized.get("networks")
        if root_networks is not None and not isinstance(root_networks, dict):
            errors.append(
                _error("networks", "INVALID_NETWORKS", "Compose networks는 object여야 합니다.")
            )
        if isinstance(root_networks, dict):
            for network_name in sorted(root_networks):
                if network_name != OVERLAY_NETWORK:
                    errors.append(
                        _error(
                            f"networks.{network_name}",
                            "UNSUPPORTED_NETWORK",
                            f"{OVERLAY_NETWORK} network만 사용할 수 있습니다.",
                            expected=OVERLAY_NETWORK,
                            actual=network_name,
                        )
                    )
                elif root_networks[network_name] is not None and not isinstance(
                    root_networks[network_name],
                    dict,
                ):
                    errors.append(
                        _error(
                            f"networks.{network_name}",
                            "INVALID_NETWORK",
                            "Compose network 설정은 object여야 합니다.",
                        )
                    )

        for service_name, service in services.items():
            service_path = f"services.{service_name}"
            if not isinstance(service_name, str) or not service_name:
                errors.append(
                    _error("services", "INVALID_SERVICE_NAME", "service name은 비어 있을 수 없습니다.")
                )
                continue
            if not isinstance(service, dict):
                errors.append(
                    _error(service_path, "INVALID_SERVICE", "service 정의는 object여야 합니다.")
                )
                continue

            if "container_name" in service:
                issue = _error(
                    f"{service_path}.container_name",
                    "FORBIDDEN_CONTAINER_NAME",
                    "container_name은 사용할 수 없습니다.",
                )
                (warnings if "FORBIDDEN_CONTAINER_NAME" in warning_codes else errors).append(issue)
            if "hostname" in service:
                errors.append(
                    _error(
                        f"{service_path}.hostname",
                        "FORBIDDEN_HOSTNAME",
                        "hostname은 기본 정책상 사용할 수 없습니다.",
                    )
                )

            if isinstance(namespace, str) and NAMESPACE_PATTERN.fullmatch(namespace) and "environment" in service:
                service["environment"] = _qualify_environment_refs(
                    service.get("environment"),
                    namespace,
                    services.keys(),
                )

            service_networks = service.get("networks")
            network_names = _network_names(service_networks)
            if network_names is None:
                errors.append(
                    _error(
                        f"{service_path}.networks",
                        "INVALID_SERVICE_NETWORKS",
                        "service networks는 list 또는 object여야 합니다.",
                    )
                )
            elif not network_names:
                service["networks"] = [OVERLAY_NETWORK]
            elif network_names != [OVERLAY_NETWORK]:
                errors.append(
                    _error(
                        f"{service_path}.networks",
                        "FIXED_OVERLAY_NETWORK_REQUIRED",
                        f"service network는 {OVERLAY_NETWORK}만 사용할 수 있습니다.",
                        expected=OVERLAY_NETWORK,
                        actual=network_names,
                    )
                )

            deploy = service.get("deploy")
            if deploy is None:
                deploy = {}
                service["deploy"] = deploy
            if not isinstance(deploy, dict):
                errors.append(
                    _error(
                        f"{service_path}.deploy",
                        "INVALID_DEPLOY",
                        "deploy는 object여야 합니다.",
                    )
                )
                continue
            deploy["replicas"] = deploy.get("replicas", 1)
            for key, defaults in [
                ("update_config", DEFAULT_UPDATE_CONFIG),
                ("rollback_config", DEFAULT_ROLLBACK_CONFIG),
                ("restart_policy", DEFAULT_RESTART_POLICY),
            ]:
                merged = _merge_defaults(deploy.get(key), defaults)
                if merged is None:
                    errors.append(
                        _error(
                            f"{service_path}.deploy.{key}",
                            "INVALID_DEPLOY_POLICY",
                            f"deploy.{key}는 object여야 합니다.",
                        )
                    )
                else:
                    deploy[key] = merged
            if _has_host_published_ports(service) and isinstance(deploy.get("update_config"), dict):
                deploy["update_config"]["order"] = "stop-first"

        self._raise_if_errors(errors, warnings=warnings, allow_warnings=allow_warnings)

        networks = normalized.setdefault("networks", {})
        overlay_config = networks.get(OVERLAY_NETWORK)
        if overlay_config is None:
            networks[OVERLAY_NETWORK] = {"external": True}
        elif isinstance(overlay_config, dict):
            overlay_config["external"] = True

        return {
            "valid": True,
            "namespace": namespace,
            "stack_name": namespace,
            "filename": filename,
            "network": OVERLAY_NETWORK,
            "has_health_check": has_health_check,
            "warnings": warnings,
            "normalized": normalized,
        }

    def _raise_if_errors(self, errors, warnings=None, allow_warnings=False):
        warnings = warnings or []
        if errors:
            raise ComposeValidationError(
                400,
                "Compose validation failed.",
                "COMPOSE_VALIDATION_FAILED",
                details=errors,
            )
        if warnings and not allow_warnings:
            raise ComposeValidationError(
                409,
                "Compose에 확인이 필요한 항목이 있습니다.",
                "COMPOSE_VALIDATION_WARNING",
                details=warnings,
                warning=True,
                can_continue=True,
            )


Model = ComposeValidator()
