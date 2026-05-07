INTEGRATIONS = {
    "harbor": {
        "label": "Harbor",
        "fields": ["url", "username"],
        "secret": "password",
    },
    "gitlab": {
        "label": "GitLab",
        "fields": ["url"],
        "secret": "token",
    },
    "cloudflare": {
        "label": "Cloudflare",
        "fields": ["domain", "zone_id"],
        "secret": "api_token",
    },
}

GENERAL_KEYS = {
    "browser_title": "general.browser_title",
    "favicon_url": "general.favicon_url",
    "logo_url": "general.logo_url",
}


def as_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ["1", "true", "yes", "on"]
    return bool(value)


def setting_map(settings):
    return {item["key"]: item for item in settings}


def setting_value(settings, key, default=None):
    item = settings.get(key)
    if item is None:
        return default
    return item.get("value", default)


def build_settings_payload(settings_model):
    rows = settings_model.list()
    mapped = setting_map(rows)
    general = {
        "browser_title": setting_value(mapped, GENERAL_KEYS["browser_title"], "Docker Infra"),
        "favicon_url": setting_value(mapped, GENERAL_KEYS["favicon_url"], ""),
        "logo_url": setting_value(mapped, GENERAL_KEYS["logo_url"], ""),
    }
    integrations = []
    for key, spec in INTEGRATIONS.items():
        prefix = f"integration.{key}"
        secret = mapped.get(f"{prefix}.{spec['secret']}")
        integrations.append({
            "key": key,
            "label": spec["label"],
            "enabled": as_bool(setting_value(mapped, f"{prefix}.enabled", False)),
            "fields": {field: setting_value(mapped, f"{prefix}.{field}", "") for field in spec["fields"]},
            "secret_name": spec["secret"],
            "secret_configured": bool(secret and secret.get("secret", {}).get("is_configured")),
            "secret_masked_value": "" if secret is None else secret.get("secret", {}).get("masked_value", ""),
            "secret_value": "",
        })
    return {"general": general, "integrations": integrations}


def load():
    settings_model = wiz.model("struct").settings
    setup_model = wiz.model("struct").setup
    system_model = wiz.model("struct").system
    code = 200
    payload = {}
    try:
        payload = build_settings_payload(settings_model)
        payload["setup"] = setup_model.status(include_checks=False)
        payload["health"] = system_model.health()
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}
    wiz.response.status(code, **payload)


def save_general():
    settings_model = wiz.model("struct").settings
    body = wiz.request.query()
    test_run_id = body.get("test_run_id")
    code = 200
    payload = {}

    try:
        for field, key in GENERAL_KEYS.items():
            settings_model.upsert(
                key=key,
                value=body.get(field, ""),
                value_type="string",
                description=f"General setting: {field}",
                test_run_id=test_run_id,
                metadata={"group": "general"},
            )
        payload = {"general": build_settings_payload(settings_model)["general"]}
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def save_integration():
    settings_model = wiz.model("struct").settings
    body = wiz.request.query()
    key = body.get("key")
    if key not in INTEGRATIONS:
        wiz.response.status(400, message="지원하지 않는 연동입니다.", error_code="INVALID_INTEGRATION")

    spec = INTEGRATIONS[key]
    prefix = f"integration.{key}"
    test_run_id = body.get("test_run_id")
    fields = body.get("fields") or {}
    code = 200
    payload = {}

    try:
        settings_model.upsert(
            key=f"{prefix}.enabled",
            value=as_bool(body.get("enabled", False)),
            value_type="boolean",
            description=f"{spec['label']} enabled",
            test_run_id=test_run_id,
            metadata={"group": "integration", "integration": key},
        )
        for field in spec["fields"]:
            settings_model.upsert(
                key=f"{prefix}.{field}",
                value=fields.get(field, ""),
                value_type="string",
                description=f"{spec['label']} {field}",
                test_run_id=test_run_id,
                metadata={"group": "integration", "integration": key},
            )
        secret_value = body.get("secret_value")
        if secret_value:
            settings_model.upsert(
                key=f"{prefix}.{spec['secret']}",
                value=secret_value,
                value_type="secret",
                is_secret=True,
                description=f"{spec['label']} {spec['secret']}",
                test_run_id=test_run_id,
                metadata={"group": "integration", "integration": key},
            )
        payload = build_settings_payload(settings_model)
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)
