class NodesRuntimeState:
    def docker_unavailable(self, result):
        if not isinstance(result, dict):
            return False
        output = f"{result.get('stderr', '')}\n{result.get('stdout', '')}".lower()
        patterns = [
            "docker: not found",
            "docker: command not found",
            "executable file not found",
            "cannot connect to the docker daemon",
            "is the docker daemon running",
        ]
        return any(pattern in output for pattern in patterns)


Model = NodesRuntimeState()
