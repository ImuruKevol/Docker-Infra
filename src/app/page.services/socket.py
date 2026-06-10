import uuid

import season

auth_model = wiz.model("struct").auth
services_model = wiz.model("struct").services
terminal_model = wiz.model("struct/nodes_terminal")
APP_ID = "page.services"


def _auth(wiz):
    try:
        wiz.session = wiz.model("portal/season/session").use()
        token = wiz.session.get("docker_infra_session_token", None)
        return auth_model.is_session_valid(token)
    except Exception:
        return False


def _namespace(wiz):
    return f"/wiz/app/{wiz.project()}/{APP_ID}"


def _room(data):
    room = str((data or {}).get("namespace") or "").strip()
    if not room:
        raise ValueError("namespace is required")
    return room


def _container_id_matches(actual, requested):
    actual = str(actual or "").strip()
    requested = str(requested or "").strip()
    if not actual or not requested:
        return False
    return actual == requested or actual.startswith(requested) or requested.startswith(actual)


def _validate_service_container(service_id, node_id, container_id):
    service_id = str(service_id or "").strip()
    node_id = str(node_id or "").strip()
    container_id = str(container_id or "").strip()
    if not service_id:
        raise ValueError("service_id는 필수입니다.")
    if not node_id:
        raise ValueError("node_id는 필수입니다.")
    if not container_id:
        raise ValueError("container_id는 필수입니다.")

    detail = services_model.detail_overview(
        service_id,
        include_certificates=False,
        include_operations=False,
        include_backup_system=False,
    )
    containers = ((detail.get("runtime_status") or {}).get("containers") or {}).get("containers") or []
    target = next(
        (
            item for item in containers
            if _container_id_matches(item.get("id"), container_id) and str(item.get("node_id") or "") == node_id
        ),
        None,
    )
    if target is None:
        raise ValueError("선택한 서비스 컨테이너를 찾을 수 없습니다. 상태 확인 후 다시 시도해주세요.")
    return target


def _cache_root(wiz):
    if "service_container_terminal_sessions" not in wiz.server.app:
        wiz.server.app.service_container_terminal_sessions = season.util.stdClass()
    return wiz.server.app.service_container_terminal_sessions


def _cache(wiz, room, create=False):
    root = _cache_root(wiz)
    if room not in root and create:
        root[room] = season.util.stdClass()
    return root.get(room)


def _close_terminal(cache):
    if not cache:
        return
    session = cache.get("session")
    if session:
        terminal_model.close(session)
    cache["session"] = None


class Controller:
    def __init__(self, server):
        self.server = server

    def connect(self, wiz):
        if not _auth(wiz):
            return False

    def join(self, wiz, data, io):
        if not _auth(wiz):
            return
        try:
            io.join(_room(data))
        except Exception:
            io.emit("terminal_error", {"message": "터미널 세션을 준비할 수 없습니다."})

    def create(self, wiz, data, io):
        if not _auth(wiz):
            io.emit("terminal_error", {"message": "로그인이 필요합니다."})
            return
        room = _room(data)
        mode = str((data or {}).get("mode") or "terminal").strip().lower()
        if mode not in ("terminal", "logs"):
            mode = "terminal"
        service_id = str((data or {}).get("service_id") or "").strip()
        node_id = str((data or {}).get("node_id") or "").strip()
        container_id = str((data or {}).get("container_id") or "").strip()
        tail = (data or {}).get("tail") or 200
        cols = int((data or {}).get("cols") or 120)
        rows = int((data or {}).get("rows") or 32)
        app_ns = _namespace(wiz)
        cache = _cache(wiz, room, create=True)
        _close_terminal(cache)

        try:
            target = _validate_service_container(service_id, node_id, container_id)
            container_id = str(target.get("id") or container_id)
            if mode == "logs":
                session = terminal_model.create_container_logs_session(node_id, container_id, tail=tail, cols=cols, rows=rows)
            else:
                session = terminal_model.create_container_session(node_id, container_id, cols=cols, rows=rows)
        except terminal_model.NodeError as exc:
            io.emit("terminal_error", {"message": exc.message}, to=room, namespace=app_ns)
            return
        except Exception as exc:
            io.emit("terminal_error", {"message": str(exc)}, to=room, namespace=app_ns)
            return

        cache["session"] = session
        cache["token"] = uuid.uuid4().hex
        cache["node_id"] = node_id
        cache["container_id"] = container_id
        cache["mode"] = mode
        token = cache["token"]

        status_event = "log_status" if mode == "logs" else "terminal_status"
        output_event = "log_output" if mode == "logs" else "ptyoutput"
        exit_event = "log_exit" if mode == "logs" else "exit"

        io.emit(
            status_event,
            {
                "connected": True,
                "mode": mode,
                "node_id": node_id,
                "node_name": session.get("node_name"),
                "container_id": container_id,
                "shell": session.get("shell"),
                "command": session.get("command"),
            },
            to=room,
            namespace=app_ns,
        )

        def stream_output():
            socketio = wiz.server.app.socketio
            while True:
                socketio.sleep(0.02)
                current = _cache(wiz, room)
                if current is None or current.get("token") != token:
                    break
                session_ref = current.get("session")
                if not session_ref:
                    break
                output = terminal_model.read(session_ref)
                if output:
                    socketio.emit(output_event, {"output": output}, to=room, namespace=app_ns)
                if terminal_model.is_alive(session_ref):
                    continue
                exit_code = terminal_model.exit_code(session_ref)
                remaining = terminal_model.read(session_ref)
                if remaining:
                    socketio.emit(output_event, {"output": remaining}, to=room, namespace=app_ns)
                terminal_model.close(session_ref)
                current["session"] = None
                socketio.emit(exit_event, {"exit_code": exit_code}, to=room, namespace=app_ns)
                break

        wiz.server.app.socketio.start_background_task(target=stream_output)

    def create_logs(self, wiz, data, io):
        if not _auth(wiz):
            io.emit("log_error", {"message": "로그인이 필요합니다."})
            return
        room = _room(data)
        service_id = str((data or {}).get("service_id") or "").strip()
        node_id = str((data or {}).get("node_id") or "").strip()
        container_id = str((data or {}).get("container_id") or "").strip()
        tail = (data or {}).get("tail") or 200
        app_ns = _namespace(wiz)
        cache = _cache(wiz, room, create=True)
        _close_terminal(cache)

        try:
            target = _validate_service_container(service_id, node_id, container_id)
            container_id = str(target.get("id") or container_id)
            session = terminal_model.create_container_logs_session(node_id, container_id, tail=tail, cols=120, rows=32)
        except terminal_model.NodeError as exc:
            io.emit("log_error", {"message": exc.message}, to=room, namespace=app_ns)
            return
        except Exception as exc:
            io.emit("log_error", {"message": str(exc)}, to=room, namespace=app_ns)
            return

        cache["session"] = session
        cache["token"] = uuid.uuid4().hex
        cache["node_id"] = node_id
        cache["container_id"] = container_id
        cache["mode"] = "logs"
        token = cache["token"]

        io.emit(
            "log_status",
            {
                "connected": True,
                "node_id": node_id,
                "node_name": session.get("node_name"),
                "container_id": container_id,
                "command": session.get("command"),
            },
            to=room,
            namespace=app_ns,
        )

        def stream_output():
            socketio = wiz.server.app.socketio
            while True:
                socketio.sleep(0.05)
                current = _cache(wiz, room)
                if current is None or current.get("token") != token:
                    break
                session_ref = current.get("session")
                if not session_ref:
                    break
                output = terminal_model.read(session_ref)
                if output:
                    socketio.emit("log_output", {"output": output}, to=room, namespace=app_ns)
                if terminal_model.is_alive(session_ref):
                    continue
                exit_code = terminal_model.exit_code(session_ref)
                remaining = terminal_model.read(session_ref)
                if remaining:
                    socketio.emit("log_output", {"output": remaining}, to=room, namespace=app_ns)
                terminal_model.close(session_ref)
                current["session"] = None
                socketio.emit("log_exit", {"exit_code": exit_code}, to=room, namespace=app_ns)
                break

        wiz.server.app.socketio.start_background_task(target=stream_output)

    def ptyinput(self, wiz, data):
        if not _auth(wiz):
            return
        room = _room(data)
        cache = _cache(wiz, room)
        if not cache or not cache.get("session"):
            return
        if cache.get("mode") == "logs":
            return
        terminal_model.write(cache["session"], (data or {}).get("input"))

    def resize(self, wiz, data):
        if not _auth(wiz):
            return
        room = _room(data)
        cache = _cache(wiz, room)
        if not cache or not cache.get("session"):
            return
        terminal_model.resize(cache["session"], (data or {}).get("cols"), (data or {}).get("rows"))

    def close(self, wiz, data, io):
        if not _auth(wiz):
            return
        room = _room(data)
        cache = _cache(wiz, room)
        event = "log_exit" if cache and cache.get("mode") == "logs" else "exit"
        _close_terminal(cache)
        io.emit(event, {"closed": True}, to=room, namespace=_namespace(wiz))

    def close_logs(self, wiz, data, io):
        if not _auth(wiz):
            return
        room = _room(data)
        cache = _cache(wiz, room)
        _close_terminal(cache)
        io.emit("log_exit", {"closed": True}, to=room, namespace=_namespace(wiz))
