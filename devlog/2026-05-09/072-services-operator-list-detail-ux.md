# 072. 서비스 목록과 상세 화면을 운영자용 UX로 재구성

## 사용자 요청

서비스 목록 및 상세 UI/UX 재설계를 이어서 진행한다. IP 정도만 아는 일반 관리자도 사용할 수 있을 정도로 난이도를 낮추고, 개발자틱한 정보는 기본 화면에서 제거한다.

## 변경 사항

- 서비스 목록을 서비스 이름, 설명, 운영 상태, 접속 주소, 마지막 변경 시각 중심으로 재구성했다.
- 목록 기본 화면에서 namespace, compose version count, stack name, compose path 같은 내부 정보를 제거했다.
- 서비스 상세 헤더를 접속 주소, 운영 상태, 서비스 적용/새로고침 중심으로 정리했다.
- 상세 상단에 현재 상태, 접속 주소, 백업 상태, 최근 처리 결과 요약을 추가했다.
- 연결된 도메인 영역을 사용자 접속 주소와 내부 연결 port 중심으로 단순화했다.
- 이미지와 백업 영역에서 digest와 raw ref 노출을 줄이고, 이미지 백업/현재 상태 백업/되돌리기 같은 운영자용 액션명으로 바꿨다.
- 최근 작업은 raw operation type 대신 `서비스 적용`, `이미지 백업` 같은 설명형 라벨로 표시하도록 했다.
- Compose 원문, compose version, 서비스 파일 브라우저는 `고급 정보` 접힘 영역으로 이동했다.
- 서비스 목록 API 응답에 대표 도메인과 대표 port를 포함하도록 catalog query를 보강했다.
- TODO 문서에 이번 완료 범위와 남은 서비스 상세 UX 작업을 반영했다.

## 변경 파일

- `devlog.md`
- `devlog/2026-05-09/072-services-operator-list-detail-ux.md`
- `docs/docker-infra-development-todo.md`
- `docs/docker-infra-remaining-todo.md`
- `src/app/page.services/view.pug`
- `src/app/page.services/view.ts`
- `src/model/struct/infra_catalog_registry.py`

## 검증

- `wiz_project_build(clean=false, projectName="main")`
- `python -m py_compile src/model/struct/infra_catalog_registry.py`
- `PYTHONPATH=. python -m unittest tests.api.test_images_templates_catalog.ImagesTemplatesStaticContractTest tests.api.test_migration_schema.MigrationSchemaStaticContractTest tests.api.test_wiz_structure_contract`
- `git diff --check`
