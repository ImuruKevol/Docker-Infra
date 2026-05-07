# 022. Docker Infra 런타임 DB/env 설정을 WIZ config와 데몬 주입으로 정리

- 날짜: 2026-05-07
- 요청: "DB를 연동하는 설정이 model에 들어가있는데, 이건 config쪽으로 설정을 분리해야해. 그리고 환경변수에서 불러오고 있는데, 현재 이 Docker Infra 서비스는 데몬 형식으로 띄워져있고, wiz.docker-infra 이름으로 띄워져있어. 근데 env 파일을 주입하는 부분이 없는데 wiz 백엔드에 전반적으로 다 환경변수 형식으로 쓰이고 있어. 이 문제를 수정해줘."

## 변경 파일

- `config/docker_infra.py`: `/root/docker-infra/config.env`, process env, test override env를 합치는 Docker Infra 런타임 설정 모듈 추가. DB URL/schema, secret key, local executor allowlist, advertise address, session cookie secure 정책을 이 config로 집중.
- `src/model/db/postgres.py`: DB 연결 설정 조립을 model에서 제거하고 `wiz.config("docker_infra")`로 위임.
- `src/model/struct/settings.py`: secret key 조회를 런타임 config로 이동.
- `src/model/struct/local_executor.py`, `src/model/struct/local_command_catalog.py`: destructive command allowlist 조회와 env key 소유권을 config로 이동.
- `src/model/struct/setup_environment.py`, `src/model/struct/setup.py`: advertise address, Docker/proxy probe, setup 초기화 흐름이 동일 runtime env/config 경로를 사용하도록 정리.
- `config-sample/database.py`: sample DB config에서 직접 env 조회 제거.
- `docs/docker-infra-runtime.md`, `README.md`: daemon에서 `config.env`를 주입하고 WIZ backend가 `config/docker_infra.py`를 통해 읽는 구조로 문서 갱신.
- `tests/api/test_wiz_structure_contract.py`: runtime config 소유권과 `wiz.docker-infra` systemd `EnvironmentFile` 계약 검사 추가.
- `/root/docker-infra/config/boot.py`: session cookie secure와 WIZ secret key가 process env 또는 `config.env`에서 읽히도록 정리.
- `/etc/systemd/system/wiz.docker-infra.service`: `EnvironmentFile=-/root/docker-infra/config.env` 추가.
- `/usr/local/bin/wiz.docker-infra`: 직접 실행 시에도 `/root/docker-infra/config.env`를 export하도록 보강.

## 검증

- WIZ model loader simulation: 통과.
- Python compile check: 통과.
- `tests.api.test_wiz_structure_contract`: 4개 테스트 통과.
- `git -C /root/docker-infra/project/main diff --check`: 통과.
- `systemd-analyze verify /etc/systemd/system/wiz.docker-infra.service`: 통과.
- `wiz_project_build` (`clean=false`): 통과.
- `systemctl daemon-reload`: 수행 완료.

## 비고

- 서비스 재시작과 live API/E2E 테스트는 요청대로 리팩터링 이후 별도 테스트 단계로 남김.
