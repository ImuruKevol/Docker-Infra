# 자동 백업 정책 저장 시 crontab 등록 연결

- **ID**: 004
- **날짜**: 2026-06-22
- **유형**: 버그 수정 / 기능 보강

## 작업 요약
자동 백업 정책을 저장할 때 root 기본 crontab에 Docker Infra 관리 항목을 등록하거나, 정책이 꺼지면 해당 항목을 제거하도록 연결했다.
cron은 토큰 헤더를 포함해 로컬 자동 백업 tick route를 호출하며, route는 로컬 요청과 저장된 토큰 hash를 검증한 뒤 기존 스케줄러를 실행한다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

자동 백업이 활성화 되어있는데 마지막으로 실행된건 저번달 5월 19일이야.
설정을 하면 crontab에 등록이 되어야 해. 현재는 root계정에 crontab이 등록되어있지 않네.
자동 백업 저장을 눌렀을 때 "자동 백업 정책을 저장할 수 없습니다." 라는 에러가 뜨기도 하고.

## 리뷰 요약

- 리뷰 ID: vgosoiiihlsnzkukbdizwwevcjgpgjcg
- 제목: 시스템 설정 - 백업 UI/UX 및 기능 수정
```

## 변경 파일 목록
- `src/model/struct/backup_system_cron.py`
  - 자동 백업 crontab 항목 생성/교체/제거 로직 추가.
  - 기본 등록 대상을 root crontab으로 두고 `DOCKER_INFRA_BACKUP_CRON_USER`로 대상 계정을 바꿀 수 있게 구성.
  - cron 요청 토큰 생성, hash 저장, 로컬 요청 검증, token 검증 로직 추가.
- `src/model/struct/backup_system_policy.py`
  - 자동 백업 정책 저장 시 crontab 동기화를 수행하고 결과 metadata를 저장하도록 연결.
  - crontab 처리 실패 시 구체적인 `BackupSystemError`로 변환해 UI에 원인을 전달.
- `src/route/api-system-backup-tick/`
  - crontab에서 호출할 `/api/system/backup/tick` route 추가.
  - 로컬 요청과 `X-Docker-Infra-Cron-Token` 검증 후 `service_image_backup_tick.tick()` 실행.
- `tests/api/test_backup_system_schedule.py`
  - crontab 항목 등록/교체와 비활성화 시 관리 항목 제거 테스트 추가.
- `tests/api/test_backup_system_ui.py`
  - 정책 저장과 cron route/token 계약 정적 검증 추가.

## 검증 결과
- 통과: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_backup_system_ui tests.api.test_backup_system_schedule tests.api.test_backup_registry_nodes`
- 통과: `wiz_project_build(clean=true)`
- 통과: `git diff --check`
- 확인: `POST /api/system/backup/tick`를 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키와 함께 token 없이 호출하면 `INVALID_CRON_TOKEN`으로 거부됨.
