# 217. WIZ service wrapper port와 bundle 인자 순서 수정

- 날짜: 2026-05-15
- 리뷰 ID: ismjwijqevuqjalzluaiuezfxbdfprcf

## 원 요청

installer의 WIZ Service 단계가 `/usr/local/bin/wiz.docker-infra` wrapper 마지막 명령을 `/opt/docker-infra/venv/bin/wiz run --port bundle --log /var/log/wiz/docker-infra`처럼 잘못 생성하므로, `/opt/docker-infra/venv/bin/wiz run --port 3000 --bundle --log /var/log/wiz/docker-infra` 형태로 생성되게 수정해 달라고 요청했다.

## 변경 파일

- `installer/install.sh`
  - WIZ CLI `service regist` 호출 순서를 `"$SERVICE_NAME" bundle "$APP_PORT"`로 수정했다.
  - 생성된 `/usr/local/bin/wiz.{service}` wrapper의 마지막 비어있지 않은 줄이 `wiz run --port {port} --bundle --log /var/log/wiz/{service}`와 일치하는지 검증하는 `assert_wiz_service_wrapper`를 추가했다.
- `tests/api/test_installer_contract.py`
  - 올바른 WIZ service 등록 인자 순서와 wrapper 검증 함수가 installer에 포함되는지 확인했다.
  - 기존 잘못된 호출 순서인 `"$SERVICE_NAME" "$APP_PORT" bundle`이 다시 들어오지 않도록 금지했다.
- `devlog.md`
  - 이번 작업 기록을 추가했다.

## 확인 결과

- `bash -n installer/install.sh && bash -n installer/preinstall.sh && bash -n installer/cleanup.sh`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract`: 통과
- WIZ `ServiceCommand.regist("docker-infra", "bundle", "3000")`를 monkeypatch로 시뮬레이션해 마지막 명령이 `/opt/conda/envs/docker-infra/bin/wiz run --port 3000 --bundle --log /var/log/wiz/docker-infra`로 생성됨을 확인했다.

## 남은 리스크

- 실제 운영 installer에서는 `WIZ_BIN=/opt/docker-infra/venv/bin/wiz` 기준으로 wrapper가 생성된다. 현재 검증은 개발 환경의 `/opt/conda/envs/docker-infra/bin/wiz`로 시뮬레이션했다.
