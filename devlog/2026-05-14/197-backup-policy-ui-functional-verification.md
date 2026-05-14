# 197. 자동 백업 UI 개선과 실제 백업 기능 검증

- 날짜: 2026-05-14
- 리뷰 ID: `nweydhaljsjvjvdsjkvyxmxwjmjlgihs`
- 요청자: 권태욱

## 원 요청

자동 백업 설정 UI가 투박하므로 더 보기 좋게 수정하고, 메인 노드와 등록 서버의 실제 작은 이미지로 백업 시스템 기능을 테스트해달라는 요청.

확인 범위:

- 이미지 일반 백업
- 컨테이너 상태까지 백업
- 서비스별 보존 개수 초과 시 이전 이미지 삭제
- 백업 주기 로직
- 자동 백업 주기를 며칠마다가 아니라 매주/매월 실행일과 시간 선택 방식으로 변경

## 변경 파일

- `src/app/page.system/view.pug`
  - 자동 백업 설정 UI를 실행 일정, 보관 방식, 실행 버튼 영역으로 재구성.
  - 매주/매월 선택, 요일/날짜, 실행 시간 입력 UI 추가.
  - 자동 백업을 끄면 상세 설정을 숨기는 흐름 유지.
- `src/app/page.system/view.ts`
  - 자동 백업 일정 요약, 주기 선택, 요일 선택 helper 추가.
  - 저장 payload에 `schedule_type`, `schedule_weekday`, `schedule_month_day`, `schedule_time` 포함.
- `src/model/struct/backup_system_policy_defaults.py`
  - 자동 백업 기본 정책에 매주/매월 실행 필드 추가.
  - 기존 `interval_days`는 호환용으로 유지.
- `src/model/struct/service_image_backup_scheduler.py`
  - `interval_days` 기반 실행 조건을 실행일/시간 기반 due 판정으로 변경.
  - 같은 예약 회차는 `last_run_at` 기준으로 중복 실행하지 않도록 처리.
- `src/model/struct/images_harbor.py`
  - Harbor artifact 전체 삭제 대신 개별 tag 삭제 API 추가.
- `src/model/struct/service_image_backup_cleanup.py`
  - 보존 초과 정리 시 artifact 삭제가 아니라 tag 삭제를 사용하도록 수정.
- `tests/api/test_backup_system_schedule.py`
  - 매주/매월 일정 정규화와 due 판정 테스트 추가.
- `tests/api/test_backup_system_cleanup.py`
  - 보존 정리가 tag 삭제 API를 사용한다는 계약 테스트 추가.
- `tests/api/test_backup_system_ui.py`
  - 새 자동 백업 UI와 일정 필드 노출 계약 보강.

## 검증 결과

- 정적/단위 테스트:
  - `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_backup_system_schedule tests.api.test_backup_system_ui tests.api.test_backup_system_cleanup tests.api.test_backup_system_runtime tests.api.test_local_executor`
  - 결과: `Ran 12 tests`, `OK`, `skipped=2`
- 문법 검사:
  - `/opt/conda/envs/docker-infra/bin/python -m py_compile ...`
  - 결과: 성공
- diff 검사:
  - `git diff --check`
  - 결과: 성공
- WIZ 빌드:
  - `wiz_project_build(clean=false, projectName="main")`
  - 결과: 성공

## 실제 기능 테스트

테스트용 `reviewops-*` namespace, Swarm 서비스, Harbor 프로젝트, DB 레코드를 생성한 뒤 완료 후 정리했다.

- 백업 시스템 상태: 실행 중, 설치됨
- 일반 이미지 백업:
  - `busybox:1.36` 기반 테스트 이미지 백업 성공
  - Harbor artifact 1개 확인
- 메인 노드 컨테이너 스냅샷:
  - `mini1`에서 테스트 컨테이너 스냅샷 백업 성공
- 서비스별 보존 개수 초과 삭제:
  - 백업 3개 생성 후 보존 개수 1개 기준 cleanup 실행
  - 이전 백업 2개 삭제, 남은 artifact 1개 확인
  - cleanup operation 성공
- 스케줄 로직:
  - 현재 요일/시간은 due 판정 `None`
  - 다른 요일은 실행일 아님으로 skip
  - 같은 예약 회차 `last_run_at` 존재 시 이미 실행됨으로 skip
- 정리 확인:
  - 테스트 Swarm 서비스 잔여 없음
  - 테스트 로컬 이미지 잔여 없음
  - 테스트 DB 서비스 레코드 0건
  - 테스트 Harbor 프로젝트 잔여 없음

## 남은 리스크

- 등록 서버 `mini3` 컨테이너 스냅샷은 원격 Docker가 내부 백업 레지스트리에 HTTPS로 접속해 실패했다.
- 현재 백업 저장소는 HTTP Harbor이므로 원격 Docker daemon에 insecure registry 설정이 없으면 원격 노드 스냅샷 push가 실패한다.
- 메인 노드 스냅샷과 일반 백업, 보존 정리, 스케줄 due 판정은 실제 환경에서 성공 확인했다.
