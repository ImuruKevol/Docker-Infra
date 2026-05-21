# 298. 템플릿 저장 후 목록 재조회 제거

- 날짜: 2026-05-21
- 요청: 리뷰 ID `mjtgfrdytfwpnbvmyfeojkmxwvmszqry`, 템플릿 수정 저장 시 목록 전체를 다시 불러와 느리고 비효율적이니 개선해달라는 요청.

## 변경 요약

- 템플릿 저장 성공 후 `load(false)`와 `selectTemplate(...)`로 목록/상세를 다시 호출하던 흐름을 제거했다.
- 저장 API가 반환한 템플릿 상세를 이용해 현재 목록 항목과 상세 캐시를 즉시 갱신하도록 `upsertSavedTemplate`를 추가했다.
- 새 템플릿 저장, 기존 템플릿 수정, namespace 변경 케이스에서 로컬 목록이 중복되지 않도록 이전 key와 새 key를 함께 정리한다.
- 정적 계약 테스트에 저장 성공 분기에서 목록 재조회가 없는지 검사하는 항목을 추가했다.

## 변경 파일

- `src/app/page.templates/view.ts`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-21/298-template-save-local-list-update.md`

## 검증 결과

- `python -m py_compile src/model/struct/templates.py tests/api/test_services_preflight.py` 통과.
- `python tests/api/test_services_preflight.py` 통과. 16개 테스트 성공.
- `git diff --check` 통과.
- `wiz_project_build(projectName="main", clean=false)` 통과.
- devmode 쿠키(`season-wiz-project=main`, `season-wiz-devmode=true`)로 `https://infra-dev.nanoha.kr/templates` HTTP 200 확인.
- 같은 쿠키로 `https://infra-dev.nanoha.kr/wiz/api/page.templates/load` HTTP 200과 응답 본문 `code=401` 확인. 로그인 세션이 없어 실제 데이터 조회는 확인하지 못했다.
- `python -m pytest tests/api/test_services_preflight.py -q`는 현재 환경에 `pytest`가 없어 실행하지 못했고, 동일 테스트 파일을 `unittest` 방식으로 검증했다.

## 남은 리스크

- 실제 로그인 세션에서 템플릿 저장 후 체감 속도와 목록 갱신은 브라우저로 직접 확인하지 못했다.
- 저장 API가 반환하는 `data.template` 계약에 의존한다. 현재 백엔드는 저장 후 상세 템플릿을 반환한다.
