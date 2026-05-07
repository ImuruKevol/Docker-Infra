import uuid

import season

auth_model = wiz.model("struct").auth
terminal_model = wiz.model("struct/nodes_terminal")
APP_ID = "page.servers"


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


def _cache_root(wiz):
    if "server_terminal_sessions" not in wiz.server.app:
        wiz.server.app.server_terminal_sessions = season.util.stdClass()
    return wiz.server.app.server_terminal_sessions


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
        node_id = str((data or {}).get("node_id") or "").strip()
        cols = int((data or {}).get("cols") or 120)
        rows = int((data or {}).get("rows") or 32)
        app_ns = _namespace(wiz)
        cache = _cache(wiz, room, create=True)
        _close_terminal(cache)

        try:
            session = terminal_model.create_session(node_id, cols=cols, rows=rows)
        except terminal_model.NodeError as exc:
            io.emit("terminal_error", {"message": exc.message}, to=room, namespace=app_ns)
            return
        except Exception as exc:
            io.emit("terminal_error", {"message": str(exc)}, to=room, namespace=app_ns)
            return

        cache["session"] = session
        cache["token"] = uuid.uuid4().hex
        cache["node_id"] = node_id
        token = cache["token"]

        io.emit(
            "terminal_status",
            {"connected": True, "node_id": node_id, "node_name": session.get("node_name")},
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
                    socketio.emit("ptyoutput", {"output": output}, to=room, namespace=app_ns)
                if terminal_model.is_alive(session_ref):
                    continue
                exit_code = terminal_model.exit_code(session_ref)
                remaining = terminal_model.read(session_ref)
                if remaining:
                    socketio.emit("ptyoutput", {"output": remaining}, to=room, namespace=app_ns)
                terminal_model.close(session_ref)
                current["session"] = None
                socketio.emit("exit", {"exit_code": exit_code}, to=room, namespace=app_ns)
                break

        wiz.server.app.socketio.start_background_task(target=stream_output)

    def ptyinput(self, wiz, data):
        if not _auth(wiz):
            return
        room = _room(data)
        cache = _cache(wiz, room)
        if not cache or not cache.get("session"):
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
        _close_terminal(cache)
        io.emit("exit", {"closed": True}, to=room, namespace=_namespace(wiz))
