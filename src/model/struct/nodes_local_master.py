from psycopg.types.json import Jsonb

connect = wiz.model("db/postgres").connect
setup = wiz.model("struct/setup")
shared = wiz.model("struct/nodes_shared")
metric_history = wiz.model("struct/nodes_metric_history")
DEFAULT_OVERLAY_NETWORK = shared.DEFAULT_OVERLAY_NETWORK
NodeError = shared.NodeError
_node_to_dict = shared.node_to_dict
_load_json = shared.load_json
_parse_docker_ps_lines = shared.parse_docker_ps_lines
_container_summary = shared.container_summary
_swarm_from_docker_info = shared.swarm_from_docker_info
_node_status_from_swarm = shared.node_status_from_swarm
_parse_reported_at = shared.parse_reported_at


class NodeLocalMasterMixin:
    def _write_node_metric(self, cursor, node_id, payload, test_run_id=None, metadata=None):
        payload = payload or {}
        containers = payload.get("containers") or {"items": []}
        metadata = dict(metadata or {})
        metadata["source"] = metadata.get("source") or "node_metric"
        reported_at = _parse_reported_at(payload.get("reported_at"))
        memory = payload.get("memory") or {}
        storage = payload.get("storage") or {}
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"node_metrics:{node_id}",))
        cursor.execute(
            """
            SELECT *
            FROM node_metrics
            WHERE node_id = %s
              AND reported_at >= %s::timestamptz - interval '60 seconds'
              AND reported_at <= %s::timestamptz + interval '60 seconds'
            ORDER BY ABS(EXTRACT(EPOCH FROM (reported_at - %s::timestamptz))) ASC, created_at DESC
            LIMIT 1
            """,
            (node_id, reported_at, reported_at, reported_at),
        )
        existing = cursor.fetchone()
        if existing is not None:
            cursor.execute(
                """
                UPDATE node_metrics
                SET cpu_percent = %s,
                    memory = %s,
                    storage = %s,
                    containers = %s,
                    reported_at = %s,
                    test_run_id = COALESCE(%s, test_run_id),
                    metadata = COALESCE(metadata, '{}'::jsonb) || %s
                WHERE id = %s
                RETURNING *
                """,
                (
                    payload.get("cpu_percent"),
                    Jsonb(memory),
                    Jsonb(storage),
                    Jsonb(containers),
                    reported_at,
                    test_run_id,
                    Jsonb(metadata),
                    existing["id"],
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO node_metrics(node_id, cpu_percent, memory, storage, containers, reported_at, test_run_id, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    node_id,
                    payload.get("cpu_percent"),
                    Jsonb(memory),
                    Jsonb(storage),
                    Jsonb(containers),
                    reported_at,
                    test_run_id,
                    Jsonb(metadata),
                ),
            )
        row = cursor.fetchone()
        try:
            metric_history.append_db_row(row, source=metadata.get("source"))
        except Exception:
            pass
        return row

    def _local_metric_payload(self, env=None):
        metric_result = self.local_executor.run("system.metrics", timeout_seconds=5, env=env)
        containers_result = self.local_executor.run("docker.containers", timeout_seconds=10, env=env)
        metric = _load_json(metric_result["stdout"]) if metric_result["status"] == "ok" else {}
        items = _parse_docker_ps_lines(containers_result["stdout"]) if containers_result["status"] == "ok" else []
        metric["containers"] = {"summary": _container_summary(items), "items": items}
        return metric, {"system": metric_result, "containers": containers_result}

    def _write_local_master(self, cursor, advertise_address, test_run_id, docker_info, swarm, network):
        metadata = {
            "source": "local_master_ensure",
            "docker": docker_info,
            "swarm": swarm,
            "overlay_network": network,
        }
        status = "active" if swarm.get("ControlAvailable") else _node_status_from_swarm(swarm)
        cursor.execute(
            """
            UPDATE nodes
            SET
                name = %s,
                role = 'local_master',
                host = %s,
                ssh_port = NULL,
                auth_type = NULL,
                status = %s,
                swarm_node_id = %s,
                is_local_master = true,
                labels = %s,
                test_run_id = COALESCE(%s, test_run_id),
                metadata = COALESCE(metadata, '{}'::jsonb) || %s
            WHERE is_local_master = true
            RETURNING *
            """,
            (
                "local-master",
                advertise_address,
                status,
                swarm.get("NodeID"),
                Jsonb({"scope": "local", "swarm_role": "manager"}),
                test_run_id,
                Jsonb(metadata),
            ),
        )
        row = cursor.fetchone()
        if row is not None:
            return _node_to_dict(row)
        cursor.execute(
            """
            INSERT INTO nodes(
                name, role, host, ssh_port, auth_type, status, swarm_node_id,
                is_local_master, labels, test_run_id, metadata
            )
            VALUES (%s, 'local_master', %s, NULL, NULL, %s, %s, true, %s, %s, %s)
            RETURNING *
            """,
            (
                "local-master",
                advertise_address,
                status,
                swarm.get("NodeID"),
                Jsonb({"scope": "local", "swarm_role": "manager"}),
                test_run_id,
                Jsonb(metadata),
            ),
        )
        return _node_to_dict(cursor.fetchone())

    def sync_local_master(self, env=None):
        advertise_address = setup.detect_advertise_address()
        docker_result = self.local_executor.run("docker.info", timeout_seconds=10, env=env)
        if docker_result["status"] != "ok":
            raise NodeError(
                409,
                "Docker Infra 실행 서버의 Docker 상태를 확인할 수 없습니다.",
                "LOCAL_DOCKER_UNAVAILABLE",
                docker=docker_result,
            )
        docker_info, swarm = _swarm_from_docker_info(docker_result["stdout"])
        metric, metric_checks = self._local_metric_payload(env=env)
        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                local_master = self._write_local_master(
                    cursor,
                    advertise_address,
                    None,
                    docker_info,
                    swarm,
                    {"name": DEFAULT_OVERLAY_NETWORK, "status": "unknown", "created": False},
                )
                self._write_node_metric(
                    cursor,
                    local_master["id"],
                    metric,
                    test_run_id=local_master["test_run_id"],
                    metadata={"source": "local_master_sync", "checks": metric_checks},
                )
        return {"ok": True, "local_master": local_master}

    def _manager_addr(self, docker_info, advertise_address):
        swarm = docker_info.get("Swarm") or {}
        managers = swarm.get("RemoteManagers") or []
        if managers and managers[0].get("Addr"):
            return managers[0]["Addr"]
        node_addr = swarm.get("NodeAddr") or advertise_address
        return f"{node_addr}:2377"

    def ensure_local_master(self, payload=None, env=None):
        payload = payload or {}
        advertise_address = payload.get("advertise_address") or setup.detect_advertise_address()
        network_name = payload.get("network_name") or DEFAULT_OVERLAY_NETWORK
        test_run_id = payload.get("test_run_id")
        actions = []

        docker_result = self.local_executor.run("docker.info", timeout_seconds=payload.get("timeout_seconds"), env=env)
        if docker_result["status"] != "ok":
            raise NodeError(
                409,
                "Docker daemon 상태를 확인할 수 없습니다.",
                "LOCAL_DOCKER_UNAVAILABLE",
                docker=docker_result,
            )
        docker_info, swarm = _swarm_from_docker_info(docker_result["stdout"])

        initialized = False
        if swarm.get("LocalNodeState") != "active" or not swarm.get("ControlAvailable"):
            init_result = self.local_executor.run(
                "swarm.init",
                params={"advertise_addr": advertise_address},
                timeout_seconds=payload.get("timeout_seconds"),
                env=env,
            )
            actions.append({"action": "swarm.init", "result": init_result})
            if init_result["status"] != "ok":
                raise NodeError(409, "Swarm init에 실패했습니다.", "SWARM_INIT_FAILED", result=init_result)
            initialized = True
            docker_result = self.local_executor.run("docker.info", timeout_seconds=payload.get("timeout_seconds"), env=env)
            docker_info, swarm = _swarm_from_docker_info(docker_result["stdout"])
        else:
            actions.append({"action": "swarm.init", "status": "skipped", "reason": "already_manager"})

        inspect_result = self.local_executor.run(
            "swarm.network.inspect",
            params={"network_name": network_name},
            timeout_seconds=payload.get("timeout_seconds"),
            env=env,
        )
        network = {"name": network_name, "status": "existing", "created": False, "inspect": inspect_result}
        if inspect_result["status"] != "ok":
            create_result = self.local_executor.run(
                "swarm.network.ensure",
                params={"network_name": network_name},
                timeout_seconds=payload.get("timeout_seconds"),
                env=env,
            )
            actions.append({"action": "swarm.network.ensure", "result": create_result})
            if create_result["status"] != "ok":
                raise NodeError(409, "overlay network 생성에 실패했습니다.", "OVERLAY_NETWORK_CREATE_FAILED", result=create_result)
            network = {"name": network_name, "status": "created", "created": True, "inspect": inspect_result, "create": create_result}
        else:
            actions.append({"action": "swarm.network.ensure", "status": "skipped", "reason": "already_exists"})

        with connect(env=env) as connection:
            with connection.cursor() as cursor:
                local_master = self._write_local_master(cursor, advertise_address, test_run_id, docker_info, swarm, network)
                metric, metric_checks = self._local_metric_payload(env=env)
                self._write_node_metric(
                    cursor,
                    local_master["id"],
                    metric,
                    test_run_id=test_run_id,
                    metadata={"source": "local_master_ensure", "checks": metric_checks},
                )

        return {
            "local_master": local_master,
            "docker": {"status": docker_result["status"], "info": docker_info},
            "swarm": {
                "state": swarm.get("LocalNodeState"),
                "manager": bool(swarm.get("ControlAvailable")),
                "node_id": swarm.get("NodeID"),
                "manager_addr": self._manager_addr(docker_info, advertise_address),
                "initialized": initialized,
            },
            "overlay_network": network,
            "actions": actions,
        }


Model = NodeLocalMasterMixin
