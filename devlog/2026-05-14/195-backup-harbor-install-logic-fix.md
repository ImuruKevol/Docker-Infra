# 195. 서비스 백업 Harbor 설치 설정과 실패 상태 보존 수정

- **ID**: 195
- **날짜**: 2026-05-14
- **유형**: 버그 수정

## 작업 요약
서비스 백업 시스템 설치 실패 원인을 확인한 결과, Harbor `v2.15.0`의 `prepare`가 요구하는 `jobservice.logger_sweeper_duration` 등 필수 설정이 생성된 `harbor.yml`에 누락되어 `KeyError`로 중단되고 있었다.
또한 실패한 설치 후 상태 갱신이 `failed`와 `last_error`를 `pending_install`로 덮어써 화면에서 실제 실패 원인이 사라지는 흐름을 확인해 함께 수정했다.

## 원문 요청사항
```text
작업을 진행해줘.

리뷰어 요청 내용:
시스템 설정에서 백업 시스템에 대해 설치 후 시작을 눌렀는데 실패라고 에러 모달이 떴어. 근데 생태 갱신을 해보면 harbor URL은 뜬 상태야. 원인을 확인하고 설치 로직 등을 싹 확인해줘.
```

## 변경 파일 목록
- `src/model/struct/backup_system_resources.py`: Harbor 2.15 설정 생성에 필요한 `external_url`, jobservice, notification, trivy, cache 필드를 보강하고 `hostname: 127.0.0.1` 검증 실패를 피하도록 hostname 산출을 분리.
- `src/model/struct/backup_system_runtime.py`: Harbor 설치 명령의 stdout/stderr를 모두 operation log에 남기고, 실패 메시지와 API 응답에 실제 stderr 마지막 원인을 반영하며 secret 값을 마스킹.
- `tests/api/test_backup_system_runtime.py`: Harbor 설정 생성 필드, 실패 명령 로그 기록, 설치 실패 상태 보존 회귀 테스트 추가.
- `devlog.md`, `devlog/2026-05-14/195-backup-harbor-install-logic-fix.md`: 작업 이력 기록.

## 확인 결과
- 성공: 실제 실패 데이터에서 최근 `backup.harbor.enable` operation이 `KeyError: 'logger_sweeper_duration'`로 중단된 것을 확인.
- 성공: 수정된 `harbor.yml` 생성 결과로 Harbor `prepare`를 임시 디렉토리에서 실행해 `docker-compose.yml` 생성까지 통과 확인.
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_backup_system_runtime`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_backup_system_runtime tests.api.test_local_executor`
- 성공: `wiz_project_build(clean=false)`

## 남은 리스크
- 실제 백업 Harbor 컨테이너 `docker compose up -d`까지는 실행하지 않았다.
- 현재 DB의 이전 실패 상태는 이미 상태 갱신으로 `pending_install`/`last_error=null`로 덮인 상태라, 이번 수정은 재시도 이후의 설치와 실패 상태 보존에 적용된다.
