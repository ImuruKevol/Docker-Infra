# 108. 도메인 인증서 서비스 상세 링크와 Search Select 선택 타이밍 보강

## 사용자 요청

인증서 적용 서비스 부분에 각 서비스 상세 화면으로 이동할 수 있는 링크 버튼을 추가하고, Search Select 컴포넌트의 1회 클릭 선택 버그가 아직 해결되지 않은 문제를 다시 수정한다.

## 변경 파일

- `src/app/page.domains/view.pug`
- `src/app/page.domains/view.ts`
- `src/app/component.search.select/view.html`
- `src/app/component.search.select/view.ts`
- `tests/api/test_domain_management_ui.py`

## 변경 내용

- 도메인 관리의 인증서 적용 서비스 목록에 `/services?service_id={id}` 상세 링크 버튼을 추가했다.
- Search Select 항목 선택을 `click`이 아니라 `mousedown` 단계에서 확정하도록 변경해 blur, label 기본 동작, 외부 click 처리보다 먼저 값이 반영되게 했다.
- Search Select 선택 직후 내부 `value`와 `valueChange`를 먼저 갱신하고 `ChangeDetectorRef.detectChanges()`를 호출해 표시 값도 즉시 갱신되게 했다.
- 드롭다운 내부 click/mousedown 전파를 명시적으로 차단하고 Enter/Space 키 선택을 유지했다.
- 정적 UI 계약 테스트에 서비스 상세 링크와 Search Select 선택 타이밍 계약을 추가했다.

## 검증

- `wiz_project_build(projectName="main", clean=false)` 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_domain_management_ui.py tests/api/test_server_macros.py tests/api/test_services_preflight.py` 성공
- `/opt/conda/envs/docker-infra/bin/python -m py_compile tests/api/test_domain_management_ui.py` 성공
