# 069. 서비스 생성 wizard 도메인 선택·Compose 충돌 표시·stack deploy 실행 경로 추가

## 사용자 요청

이어서 진행해줘

## 변경 사항

- 서비스 생성 wizard의 도메인 단계에서 등록된 도메인 zone을 선택하고 앞 주소를 조합할 수 있게 했다.
- 등록 도메인이 없거나 별도 주소를 쓰는 경우 직접 도메인 연결 경로를 제공했다.
- 서비스 생성 wizard의 마지막 단계에서 `초안 저장`과 `저장 후 배포`를 분리했다.
- 서비스 상세 헤더에 현재 Compose 기준 배포 버튼을 추가했다.
- 배포 방식은 `docker stack deploy --with-registry-auth` 기준으로 확정하고, Job 없이 `operation_logs`에 실행 결과와 output을 저장하도록 했다.
- 배포 전 `docker_infra_overlay` network를 확인하고 없으면 생성하도록 했다.
- 고급 Compose 편집 시 wizard form 값과 원문 Compose의 service/image/port/environment/volume 불일치를 검사하고 화면에 표시하도록 했다.
- 서비스 배포 실행 책임을 `services_deploy` struct로 분리해 WIZ 모델 파일 크기 제한을 유지했다.
- P5 완료 항목과 P6 배포 방식/operation API 완료 항목을 TODO 문서에 반영했다.

## 변경 파일

- `config/docker_infra.py`
- `devlog.md`
- `docs/docker-infra-development-todo.md`
- `docs/docker-infra-remaining-todo.md`
- `src/app/page.services/api.py`
- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `src/model/struct/local_command_catalog.py`
- `src/model/struct/services.py`
- `src/model/struct/services_compose.py`
- `src/model/struct/services_deploy.py`

## 검증

- `python -m py_compile src/app/page.services/api.py src/model/struct/services.py src/model/struct/services_compose.py src/model/struct/services_deploy.py src/model/struct/local_command_catalog.py`
- `wiz_project_build(clean=false, projectName="main")`
- `PYTHONPATH=. python -m unittest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest tests.api.test_wiz_structure_contract`
- `git diff --check`
