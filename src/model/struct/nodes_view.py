shared = wiz.model("struct/nodes_shared")
_container_summary = shared.container_summary


class NodeView:
    def _result_reason(self, result, default_message="Docker를 사용할 수 없습니다."):
        result = result or {}
        for value in [result.get("stderr"), result.get("stdout")]:
            if not value:
                continue
            lines = [line.strip() for line in str(value).splitlines() if line.strip()]
            if lines:
                return lines[-1][:160]
        return default_message

    def metric(self, latest_metric):
        latest_metric = latest_metric or {}
        return {
            "cpu_percent": latest_metric.get("cpu_percent"),
            "memory": latest_metric.get("memory") or {},
            "storage": latest_metric.get("storage") or {},
            "reported_at": latest_metric.get("reported_at"),
        }

    def credential(self, credential):
        credential = credential or {}
        return {
            "username": credential.get("username"),
            "has_key_file": bool(credential.get("has_key_file")),
            "key_file_path": credential.get("key_file") or (credential.get("metadata") or {}).get("key_file"),
            "fingerprint_registered": bool(credential.get("ssh_fingerprint")),
        }

    def docker(self, node, docker_result=None):
        node = node or {}
        metadata = node.get("metadata") or {}
        last_check = metadata.get("last_check") or {}
        result = docker_result or last_check.get("docker")
        if isinstance(result, dict):
            available = result.get("status") == "ok"
            return {
                "available": available,
                "status": result.get("status") or ("ok" if available else "error"),
                "reason": None if available else self._result_reason(result),
            }
        if metadata.get("docker"):
            return {"available": True, "status": "ok", "reason": None}
        return {"available": None, "status": "unknown", "reason": None}

    def node(self, node, docker_result=None):
        node = node or {}
        metadata = node.get("metadata") or {}
        mode = shared.server_mode_payload(node)
        return {
            "id": node.get("id"),
            "name": node.get("name"),
            "role": node.get("role"),
            "host": node.get("host"),
            "private_host": node.get("private_host") or metadata.get("private_host") or metadata.get("node_access_host") or node.get("host"),
            "public_ip": node.get("public_ip") or metadata.get("public_ip") or "",
            "ssh_port": node.get("ssh_port"),
            "status": node.get("status"),
            "swarm_node_id": node.get("swarm_node_id"),
            "is_local_master": node.get("is_local_master"),
            **mode,
            "credential": self.credential(node.get("credential")),
            "latest_metric": self.metric(node.get("latest_metric")),
            "docker": self.docker(node, docker_result=docker_result),
            "monitoring_agent": metadata.get("monitoring_agent") or {},
        }

    def container(self, item):
        return {
            "id": item.get("id"),
            "name": item.get("name"),
            "image": item.get("image"),
            "state": item.get("state"),
            "status": item.get("status"),
            "service_namespace": item.get("service_namespace"),
            "runtime_service_name": item.get("runtime_service_name"),
            "port_bindings": item.get("port_bindings") or [],
        }

    def panel(self, items, groups):
        return {
            "summary": _container_summary(items),
            "service_groups": [
                {
                    "service": group["service"],
                    "summary": group["summary"],
                    "containers": [self.container(item) for item in group["containers"]],
                }
                for group in groups.get("service_groups") or []
            ],
            "unmanaged_containers": [self.container(item) for item in groups.get("unmanaged_containers") or []],
        }


Model = NodeView()
