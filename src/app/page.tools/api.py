SAFE_COMMANDS = {
    "docker.version",
    "docker.info",
    "swarm.info",
    "swarm.nodes",
    "swarm.join-token.worker",
    "swarm.join-token.manager",
    "swarm.network.inspect",
    "proxy.nginx.version",
    "proxy.nginx.configtest",
    "diagnostic.success",
    "diagnostic.failure",
    "diagnostic.timeout",
}


def load():
    catalog = wiz.model("struct/infra_catalog_registry")
    code = 200
    payload = {}

    try:
        payload = catalog.tools()
    except RuntimeError as exc:
        code = 503
        payload = {"message": str(exc), "error_code": "DATABASE_UNAVAILABLE"}

    wiz.response.status(code, **payload)


def run_command():
    executor = wiz.model("struct").local_executor
    body = wiz.request.query()
    command_id = body.get("command_id") or "docker.info"
    code = 200
    payload = {}

    try:
        if command_id not in SAFE_COMMANDS:
            code = 400
            payload = {"message": "화면에서 실행할 수 없는 command입니다.", "error_code": "UNSAFE_COMMAND"}
        else:
            payload = {
                "result": executor.run(
                    command_id,
                    timeout_seconds=body.get("timeout_seconds", 10),
                    params=body.get("params") or {},
                )
            }
    except executor.LocalCommandError as exc:
        code = exc.status_code
        payload = {"message": exc.message, "error_code": exc.error_code, **exc.extra}

    wiz.response.status(code, **payload)
