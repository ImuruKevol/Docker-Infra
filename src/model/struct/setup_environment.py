import json
import socket


local_executor = wiz.model("struct/local_executor")
config = wiz.config("docker_infra")


def _run_probe(command_id, env=None):
    result = local_executor.run(command_id, timeout_seconds=3, env=env)
    output = (result["stdout"] or result["stderr"] or "").strip()
    if result["status"] == "missing":
        return {"installed": False, "status": "missing", "message": f"{result['command'][0]} not found"}
    if result["status"] == "timeout":
        return {"installed": True, "status": "timeout", "message": f"{result['command'][0]} timed out"}
    return {
        "installed": True,
        "status": result["status"],
        "exit_code": result["exit_code"],
        "version": output.splitlines()[0] if output else "",
    }


def detect_advertise_address(env=None):
    configured = config.advertise_address(env)
    if configured:
        return configured
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "127.0.0.1"


def detect_docker(env=None):
    result = local_executor.run("docker.info", timeout_seconds=3, env=env)
    if result["status"] == "missing":
        return {
            "installed": False,
            "daemon": "missing",
            "swarm": {"state": "unknown", "manager": False},
            "message": "docker CLI is not installed",
        }
    if result["status"] == "timeout":
        return {
            "installed": True,
            "daemon": "timeout",
            "swarm": {"state": "unknown", "manager": False},
            "message": "docker info timed out",
        }
    if result["status"] != "ok":
        return {
            "installed": True,
            "daemon": "error",
            "swarm": {"state": "unknown", "manager": False},
            "message": (result["stderr"] or result["stdout"] or "").strip(),
        }

    try:
        info = json.loads(result["stdout"])
    except Exception:
        info = {}
    swarm = info.get("Swarm") or {}
    return {
        "installed": True,
        "daemon": "ok",
        "server_version": info.get("ServerVersion"),
        "hostname": info.get("Name"),
        "swarm": {
            "state": swarm.get("LocalNodeState", "unknown"),
            "manager": bool(swarm.get("ControlAvailable")),
            "node_id": swarm.get("NodeID"),
        },
    }


def detect_proxy(env=None):
    nginx = _run_probe("proxy.nginx.version", env=env)
    apache = _run_probe("proxy.apache2.version", env=env)
    if apache["status"] == "missing":
        apache = _run_probe("proxy.apachectl.version", env=env)
    return {"nginx": nginx, "apache2": apache}


def detect_local_environment(env=None):
    return {
        "advertise_address": detect_advertise_address(env),
        "docker": detect_docker(env),
        "proxy": detect_proxy(env),
    }


class SetupEnvironment:
    detect_advertise_address = staticmethod(detect_advertise_address)
    detect_docker = staticmethod(detect_docker)
    detect_proxy = staticmethod(detect_proxy)
    detect_local_environment = staticmethod(detect_local_environment)


Model = SetupEnvironment()
