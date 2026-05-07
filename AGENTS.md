# Codex Instructions

## Runtime Environment

Use the Docker Infra conda environment for Python and WIZ commands.

- Python: `/opt/conda/envs/docker-infra/bin/python`
- WIZ: `/opt/conda/envs/docker-infra/bin/wiz`

Prefer explicit executable paths in automation and verification commands, for example:

```bash
/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api
/opt/conda/envs/docker-infra/bin/wiz project build --project main
```

Do not rely on the default shell `python` or `wiz` unless the active shell is already confirmed to be the `docker-infra` conda environment.

## Secret Handling

`/root/docker-infra/config.env` and `/root/docker-infra/domain.txt` contain integration secrets. Never print their values in logs, docs, devlogs, tests, or final responses. If they must be inspected, show only redacted key/record presence.

## WIZ Project Work

When changing files in this project, write a matching devlog entry before the final response.
