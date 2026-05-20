# 287. 템플릿 삭제 후 프론트 목록 갱신 적용

## 사용자 요청

- 리뷰 ID: wsclocypqyjuyeqefgxyxrdullusdhke
- 제목: 템플릿 삭제 로직 최적화
- 원문: 현재 템플릿을 삭제하면 삭제 후 목록부터 다시 불러오고 있는데, 삭제 API 성공 시 다시 불러오지 말고 그냥 프론트 단에서 목록에서만 삭제시키면 속도가 더 빨라지는 듯한 느낌이 들 수 있을 것 같아.

## 변경 파일

- `src/app/page.templates/view.ts`
  - 템플릿 삭제 API 성공 후 `load()`를 다시 호출하지 않도록 변경했다.
  - 삭제된 템플릿을 `templates` signal에서 즉시 제거하고, 삭제된 상세 캐시와 선택 상세 상태를 초기화하도록 `removeDeletedTemplateFromList`를 추가했다.
  - 목록 선택 비교가 `id`와 `namespace` fallback을 같은 방식으로 쓰도록 `templateItemId`를 추가했다.
- `tests/api/test_services_preflight.py`
  - 템플릿 삭제 성공 분기에서 로컬 목록 갱신 helper를 호출하고 `load()`를 호출하지 않는 정적 계약을 추가했다.
- `devlog.md`
- `devlog/2026-05-20/287-template-delete-local-list-update.md`

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_create_supports_templates_and_draft_sources` 성공.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest` 성공.
- `wiz_project_build(projectName="main", clean=false)` 성공.
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 넣고 `https://infra-dev.nanoha.kr/templates` HTTP 200 확인.
- 같은 쿠키로 `https://infra-dev.nanoha.kr/wiz/api/page.templates/load` HTTP 200과 응답 본문 `code=401` 확인. 로그인 세션이 없어 실제 목록 데이터 조회는 확인하지 못했다.

## 남은 리스크

- 삭제 API는 실제 템플릿을 삭제하는 파괴적 동작이고 로그인 세션도 없어 실데이터 삭제 후 화면 체감은 브라우저에서 직접 검증하지 못했다.
