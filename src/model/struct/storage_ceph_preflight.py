from concurrent.futures import ThreadPoolExecutor, as_completed
GIB = 1024 * 1024 * 1024
catalog = wiz.model("struct/local_command_catalog")
shared = wiz.model("struct/nodes_shared")

GUIDANCE = {
    "node_inspect": {
        "reason": "SSH 인증 정보가 없거나 서버에서 점검 스크립트를 실행하지 못했습니다.",
        "remediation": "서버 관리에서 SSH 연결 상태와 등록된 계정/key를 확인한 뒤 다시 점검하세요.",
        "auto_fix": {"available": True, "type": "route", "label": "서버 관리 열기", "route": "/servers"},
    },
    "docker": {
        "reason": "Docker CLI가 없거나 Docker daemon이 응답하지 않습니다.",
        "remediation": "대상 서버에 Docker를 설치하고 daemon을 시작한 뒤, 등록된 SSH 계정이 docker 명령을 실행할 수 있게 권한을 조정하세요.",
    },
    "swarm": {
        "reason": "서버가 active Swarm node가 아니거나 저장된 swarm_node_id와 실제 node id가 다릅니다.",
        "remediation": "서버 관리에서 Swarm 등록을 다시 실행하거나, stale node 등록을 정리한 뒤 다시 점검하세요.",
        "auto_fix": {"available": True, "type": "route", "label": "Swarm 등록 화면 열기", "route": "/servers"},
    },
    "kernel_module": {
        "reason": "kernel CephFS client module을 찾지 못했습니다.",
        "remediation": "서버에서 ceph kernel module을 제공하는 kernel package를 설치하거나 module load 상태를 확인하세요.",
    },
    "host_network": {
        "reason": "Docker host network를 inspect할 수 없습니다.",
        "remediation": "Docker daemon 상태를 복구하세요. host network는 Docker 기본 network라 별도 생성보다 daemon 복구가 우선입니다.",
    },
    "free_space": {
        "reason": "요청한 OSD slot 크기보다 여유 공간이 부족합니다.",
        "remediation": "불필요한 image/container/cache를 정리하거나 더 작은 slot 크기로 다시 점검하세요.",
    },
    "gpt_partition": {
        "reason": "GPT partition 후보를 확인할 lsblk와 parted/sgdisk 조합이 부족합니다.",
        "remediation": "서버에 util-linux와 parted 또는 gdisk package를 설치한 뒤 다시 점검하세요.",
    },
    "lvm_optional": {
        "reason": "LVM 명령을 찾지 못해 LVM LV slot 선택 모드를 사용할 수 없습니다.",
        "remediation": "LVM 선택 모드가 필요하면 lvm2 package를 설치하세요. 기본 GPT partition slot만 쓸 경우 계속 진행할 수 있습니다.",
    },
    "ceph_volume": {
        "reason": "Ceph container 안에서 ceph-volume 명령을 실행하지 못했습니다.",
        "remediation": "대상 서버가 Ceph image를 pull/run 할 수 있는지 확인하세요. host에 ceph-volume을 설치할 필요는 없습니다.",
    },
    "ceph_image": {
        "reason": "Ceph container image를 가져오거나 inspect하지 못했습니다.",
        "remediation": "서버의 registry 접근 권한과 Docker image pull 가능 여부를 확인하세요.",
    },
    "ceph_container": {
        "reason": "Ceph container 실행 자체가 실패했습니다.",
        "remediation": "Docker runtime 권한, image platform, seccomp/AppArmor 제한을 확인한 뒤 다시 점검하세요.",
    },
    "swarm_host_count": {
        "reason": "eligible Swarm host가 3대 미만입니다.",
        "remediation": "Ceph 운영 기본값은 host failure domain 분산을 위해 Swarm 서버 3대 이상이 필요합니다.",
        "auto_fix": {"available": True, "type": "route", "label": "서버 등록/Swarm 연결", "route": "/servers"},
    },
}

def _text(value):
    return str(value or "").strip()

def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def _kv(stdout):
    data = {}
    for line in str(stdout or "").splitlines():
        if "\t" not in line:
            continue
        key, value = line.split("\t", 1)
        data[key.strip()] = value.strip()
    return data

def _node_label(node):
    return _text(node.get("name")) or _text(node.get("host")) or _text(node.get("id"))

def _guidance(check_id):
    data = dict(GUIDANCE.get(check_id) or {})
    data.setdefault("reason", "점검 기준을 만족하지 못했습니다.")
    data.setdefault("remediation", "상세 상태를 확인한 뒤 다시 점검하세요.")
    data.setdefault("auto_fix", {"available": False})
    return data

def _selected_set(value):
    if isinstance(value, str):
        items = value.replace(",", " ").split()
    else:
        items = value or []
    return {str(item).strip() for item in items if str(item).strip()}


class StorageCephPreflight:
    def __init__(self, nodes=None, local_executor=None):
        self.nodes = nodes or wiz.model("struct/nodes")
        self.local_executor = local_executor or wiz.model("struct/local_executor")

    def _check(self, check_id, title, ok, message, required=True, details=None, warning=False):
        if ok:
            status = "ok"
        elif warning or not required:
            status = "warning"
        else:
            status = "error"
        guide = _guidance(check_id)
        return {
            "id": check_id,
            "title": title,
            "status": status,
            "required": bool(required),
            "message": message,
            "reason": "" if status == "ok" else guide["reason"],
            "remediation": "" if status == "ok" else guide["remediation"],
            "auto_fix": {"available": False} if status == "ok" else guide["auto_fix"],
            "details": details or {},
        }

    def _run_node_script(self, node, ceph_image, timeout_seconds=45, env=None):
        if shared.is_local_master_node(node):
            return self.local_executor.run(
                "storage.ceph.node.preflight",
                timeout_seconds=timeout_seconds,
                params={"image": ceph_image},
                env=env,
            )
        detail = self.nodes.detail(node["id"], env=env)
        return self.nodes._run_ssh_command(
            detail,
            ["sh", "-lc", catalog.STORAGE_CEPH_PREFLIGHT_SCRIPT, "sh", ceph_image],
            timeout_seconds=timeout_seconds,
            env=env,
        )

    def _inspect_node(self, node, slot_size_gb, ceph_image, timeout_seconds=45, env=None, master_only=False):
        label = _node_label(node)
        try:
            result = self._run_node_script(node, ceph_image, timeout_seconds, env=env)
        except Exception as exc:
            result = {"status": "error", "exit_code": None, "stdout": "", "stderr": str(exc)}

        if result.get("status") != "ok":
            checks = [self._check(
                "node_inspect",
                "Node preflight command",
                False,
                "서버에서 preflight 명령을 실행할 수 없습니다.",
                details={"status": result.get("status"), "exit_code": result.get("exit_code"), "stderr": result.get("stderr")},
            )]
            return self._node_result(node, label, checks, {})

        facts = _kv(result.get("stdout"))
        stored_swarm_id = _text(node.get("swarm_node_id"))
        remote_swarm_id = _text(facts.get("swarm_node_id"))
        swarm_matches = not remote_swarm_id or remote_swarm_id == stored_swarm_id or remote_swarm_id[:12] == stored_swarm_id[:12]
        free_bytes = _int(facts.get("free_bytes"))
        candidate_bytes = _int(facts.get("osd_candidate_size_bytes"))
        storage_bytes = candidate_bytes or free_bytes
        required_bytes = int(slot_size_gb) * GIB

        osd_required = not master_only
        image_required = not master_only
        checks = [
            self._check("docker", "Docker daemon", facts.get("docker") == "ok", "Docker daemon 응답을 확인했습니다."),
            self._check(
                "swarm",
                "Docker Swarm",
                facts.get("swarm_state") == "active" and swarm_matches,
                "저장된 swarm_node_id와 실제 Swarm 상태를 확인했습니다.",
                details={"stored_swarm_node_id": stored_swarm_id, "remote_swarm_node_id": remote_swarm_id, "swarm_state": facts.get("swarm_state")},
            ),
            self._check("kernel_module", "Kernel Ceph module", facts.get("kernel_ceph") == "ok", "kernel CephFS client 사용 가능 여부를 확인했습니다.", required=osd_required, warning=not osd_required),
            self._check("host_network", "Docker host network", facts.get("host_network") == "ok", "Ceph daemon용 host network 사용 가능 여부를 확인했습니다."),
            self._check(
                "free_space",
                "Free space",
                storage_bytes >= required_bytes,
                f"{slot_size_gb}GB OSD slot 후보를 만들 수 있는 여유 공간을 확인했습니다.",
                details={
                    "free_bytes": free_bytes,
                    "candidate_bytes": candidate_bytes,
                    "candidate_device": facts.get("osd_candidate_device"),
                    "required_bytes": required_bytes,
                },
                required=osd_required,
                warning=not osd_required,
            ),
            self._check("gpt_partition", "GPT partition", facts.get("gpt_partition") == "ok", "GPT partition slot 생성 도구(lsblk와 parted/sgdisk)를 확인했습니다.", required=False, warning=True),
            self._check("lvm_optional", "LVM optional mode", facts.get("lvm") == "ok", "LVM LV slot 선택 가능 여부를 확인했습니다.", required=False, warning=True),
            self._check("ceph_image", "Ceph container image", facts.get("ceph_image") == "ok", "Ceph image pull/inspect 가능 여부를 확인했습니다.", required=image_required, warning=not image_required),
            self._check("ceph_container", "Ceph container runtime", facts.get("ceph_container") == "ok", "Ceph container 실행 가능 여부를 확인했습니다.", required=image_required, warning=not image_required),
            self._check("ceph_volume", "ceph-volume in container", facts.get("ceph_volume") == "ok", "OSD prepare는 Ceph container의 ceph-volume으로 실행합니다.", required=osd_required, warning=not osd_required),
        ]
        return self._node_result(node, label, checks, facts)

    def _node_result(self, node, label, checks, facts):
        failed = [check for check in checks if check["required"] and check["status"] == "error"]
        warnings = [check for check in checks if check["status"] == "warning"]
        status = "failed" if failed else ("warning" if warnings else "ok")
        return {
            "id": node.get("id"),
            "name": node.get("name"),
            "label": label,
            "host": node.get("host"),
            "swarm_node_id": _text(node.get("swarm_node_id")),
            "eligible": not failed,
            "status": status,
            "facts": facts,
            "checks": checks,
        }

    def _global_checks(self, candidates, inspected, allow_single_host=False):
        candidate_hosts = {_text(node.get("swarm_node_id")) or _text(node.get("host")) for node in candidates}
        eligible_hosts = {_text(row.get("swarm_node_id")) or _text(row.get("host")) for row in inspected if row.get("eligible")}
        details = {"candidate_hosts": len(candidate_hosts), "eligible_hosts": len(eligible_hosts)}
        if allow_single_host:
            has_host = len(eligible_hosts) >= 1
            message = "Ceph 마스터 초기 구성은 단일 Docker Infra master에서 시작합니다." if has_host else "Ceph 마스터로 구성할 eligible Swarm host가 없습니다."
            return [self._check(
                "swarm_host_count", "Swarm host count", False, message,
                required=not has_host, warning=has_host, details={**details, "mode": "master_only"},
            )]
        return [
            self._check(
                "swarm_host_count",
                "Swarm host count",
                len(candidate_hosts) >= 3 and len(eligible_hosts) >= 3,
                "Ceph 운영 기본값은 Swarm 등록 host 3대 이상입니다.",
                details=details,
            )
        ]

    def _progress(self, on_progress, message, metadata=None):
        if not callable(on_progress):
            return
        try:
            on_progress(message, metadata or {})
        except Exception:
            pass

    def run(self, payload=None, env=None, on_progress=None):
        payload = payload or {}
        slot_size_gb = max(1, _int(payload.get("slot_size_gb"), 64))
        timeout_seconds = max(5, min(_int(payload.get("timeout_seconds"), 45), 180))
        ceph_image = _text(payload.get("ceph_image")) or _text(payload.get("image")) or "quay.io/ceph/ceph:v19.2.4"
        if ceph_image in {"quay.io/ceph/ceph:latest", "quay.io/ceph/ceph:v19"}: ceph_image = "quay.io/ceph/ceph:v19.2.4"
        allow_single_host = bool(payload.get("allow_single_host") or payload.get("master_only"))
        master_only = bool(payload.get("master_only"))
        selected = _selected_set(payload.get("node_ids"))
        nodes = self.nodes.list(env=env)
        candidates = []
        for node in nodes:
            if selected and str(node.get("id")) not in selected:
                continue
            if shared.has_swarm_node_id(node):
                candidates.append(node)

        self._progress(on_progress, f"Ceph preflight 대상 Swarm 서버 {len(candidates)}대입니다.", {"step": "candidate-filter"})

        inspected = []
        parallelism = max(1, min(_int(payload.get("parallelism"), 4), max(len(candidates), 1)))
        if candidates:
            with ThreadPoolExecutor(max_workers=parallelism) as executor:
                futures = {}
                for node in candidates:
                    label = _node_label(node)
                    self._progress(on_progress, f"{label}: Ceph preflight node 점검을 시작합니다.", {"step": "node-start", "node_id": node.get("id")})
                    futures[executor.submit(self._inspect_node, node, slot_size_gb, ceph_image, timeout_seconds, env, master_only)] = label
                for future in as_completed(futures):
                    row = future.result()
                    inspected.append(row)
                    self._progress(on_progress, f"{futures[future]}: Ceph preflight node 점검이 {row.get('status')} 상태로 끝났습니다.", {"step": "node-finish", "node_id": row.get("id"), "status": row.get("status")})
        global_checks = self._global_checks(candidates, inspected, allow_single_host=allow_single_host)
        for check in global_checks:
            self._progress(on_progress, f"{check['title']}: {check['status']} - {check['message']}", {"step": "global-check", **check})
        all_checks = global_checks + [check for row in inspected for check in row.get("checks", [])]
        failed = [check for check in all_checks if check["required"] and check["status"] == "error"]
        warnings = [check for check in all_checks if check["status"] == "warning"]
        status = "failed" if failed else ("passed_with_warnings" if warnings else "passed")
        return {
            "status": status,
            "bootstrap_allowed": not failed,
            "slot_size_gb": slot_size_gb,
            "ceph_image": ceph_image,
            "summary": {
                "swarm_candidates": len(candidates),
                "eligible": len([row for row in inspected if row.get("eligible")]),
                "failed_checks": len(failed),
                "warning_checks": len(warnings),
            },
            "checks": global_checks,
            "nodes": inspected,
        }


Model = StorageCephPreflight()
