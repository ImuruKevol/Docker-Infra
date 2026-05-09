# 068. 백업 예약 tick/정리 정책과 서비스 생성 wizard 단계형 폼 적용

## 사용자 요청

남은 작업들을 순서대로 이어서 진행해줘

## 변경 사항

- WIZ 앱 활동 시 서비스 이미지 자동 백업 예약 조건을 확인하는 lightweight tick 모델을 추가했다.
- 대시보드와 시스템 설정 load API에서 백업 정책이 활성화된 경우에만 백그라운드 예약 실행을 시도하도록 연결했다.
- 서비스 이미지 백업 정리 모델을 추가해 서비스별 보존 개수, 미사용 N일 기준, 현재 서비스에서 사용하지 않는 백업 이미지 정리 대상을 계산하고 삭제할 수 있게 했다.
- 시스템 설정의 자동 백업 정책에 서비스별 보존 개수와 미사용 정리 기준을 추가하고, 정리 대상 확인/정리 실행 버튼을 연결했다.
- 서비스 생성 모달을 단계형 wizard로 재구성했다.
- 기본 생성 화면에서 Compose YAML을 숨기고, 고급 편집을 연 경우에만 원문을 표시하도록 바꿨다.
- 서비스 이름/설명, 이미지 이름과 tag, 내부 port, 환경변수, 데이터 볼륨, 도메인/SSL, 실행 서버 자동/수동 배치, 최종 요약 단계를 추가했다.
- 서비스 생성 시 설명, 환경변수, 볼륨, 배치 정책을 metadata와 Compose 초안에 반영하도록 했다.
- Compose 생성 책임을 `services_compose` struct로 분리해 WIZ 구조 계약의 모델 파일 크기 제한을 맞췄다.
- 남은 TODO 문서에 완료된 P4/P5/P10 항목과 다음 잔여 작업을 갱신했다.

## 변경 파일

- `devlog.md`
- `docs/docker-infra-development-todo.md`
- `docs/docker-infra-remaining-todo.md`
- `src/app/page.dashboard/api.py`
- `src/app/page.services/api.py`
- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `src/app/page.system/api.py`
- `src/app/page.system/view.pug`
- `src/app/page.system/view.ts`
- `src/model/struct.py`
- `src/model/struct/backup_system_policy_defaults.py`
- `src/model/struct/service_image_backup_cleanup.py`
- `src/model/struct/service_image_backup_tick.py`
- `src/model/struct/services.py`
- `src/model/struct/services_compose.py`

## 검증

- `python -m py_compile src/app/page.services/api.py src/model/struct/services.py src/model/struct/services_compose.py src/model/struct/service_image_backup_tick.py src/model/struct/service_image_backup_cleanup.py src/model/struct/backup_system_policy_defaults.py src/app/page.dashboard/api.py src/app/page.system/api.py`
- `wiz_project_build(clean=false, projectName="main")`
- `PYTHONPATH=. python -m unittest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest tests.api.test_wiz_structure_contract`
- `git diff --check`
