# 297. 기본 템플릿 삭제 후 재생성 방지

- 날짜: 2026-05-21
- 요청: 버그 수정해줘. 리뷰 ID `mjtgfrdytfwpnbvmyfeojkmxwvmszqry`, 템플릿 삭제 후 성공 메시지가 뜨지만 새로고침하면 다시 표시되는 문제.

## 변경 요약

- 기본 seed 템플릿을 삭제할 때 템플릿 루트에 `.deleted-seed-templates.json` tombstone을 기록하도록 했다.
- `ensure_defaults`가 tombstone에 기록된 seed namespace는 다시 생성하지 않도록 변경했다.
- 같은 namespace로 템플릿을 다시 저장하면 tombstone을 제거해 수동 복구/재생성이 가능하도록 했다.
- seed 삭제 지속성에 대한 동적 단위 테스트와 정적 계약 검사를 추가했다.

## 변경 파일

- `src/model/struct/templates.py`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-21/297-template-delete-seed-persistence.md`

## 검증 결과

- `python -m py_compile src/model/struct/templates.py tests/api/test_services_preflight.py` 통과.
- `python tests/api/test_services_preflight.py` 통과. 16개 테스트 성공.
- `git diff --check` 통과.
- `wiz_project_build(projectName="main", clean=false)` 통과.
- `python -m pytest tests/api/test_services_preflight.py -q`는 현재 환경에 `pytest`가 없어 실행하지 못했고, 동일 테스트 파일을 `unittest` 방식으로 검증했다.

## 남은 리스크

- 실제 운영/개발 데이터의 템플릿 삭제 API 호출은 파괴적 동작이라 수행하지 않았다.
- 이미 이전 삭제 시도 후 다시 생성된 기본 템플릿은 한 번 더 삭제해야 tombstone이 기록된다.
