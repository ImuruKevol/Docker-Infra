# 작업 로그 전체 건수 fallback과 페이지 버튼 보강

- **ID**: 175
- **날짜**: 2026-05-13
- **유형**: 버그 수정

## 작업 요약
작업 로그 화면에서 API pagination 메타데이터가 없거나 top-level 필드로 내려오는 경우에도 전체 건수와 페이지 수를 계산하도록 보강했다.
하단 페이지 선택은 외부 pagination 컴포넌트 의존 대신 화면 자체의 이전/다음 및 페이지 번호 버튼으로 렌더링하도록 변경했다.

## 원문 요청사항
```text
전체는 183개라고 나오고, 갯수는 80개씩 불러오는데 맨 하단에는 총 80개라고 표시되고 있는 버그가 있어. 페이지 선택도 안뜨고.
```

## 변경 파일 목록
- `src/model/struct/infra_catalog_registry.py`: 작업 로그 응답에 `total`, `page`, `pages`, `page_size` top-level 필드를 추가해 pagination 메타데이터 접근을 보강.
- `src/app/page.operations/view.ts`: pagination 응답 누락 시 status count 기반 전체 건수 fallback, page count 계산, 자체 페이지 버튼 helper를 추가.
- `src/app/page.operations/view.pug`: 하단 페이지 선택 UI를 자체 버튼 그룹으로 교체.
- `devlog.md`, `devlog/2026-05-13/175-operations-pagination-total-fallback.md`: 작업 이력 기록.

## 확인 결과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/infra_catalog_registry.py src/app/page.operations/api.py` 성공.
- `wiz_project_build(projectName="main", clean=false)` 성공.

## 남은 리스크
- 실제 운영 브라우저에서 `/operations` 화면의 183건 기준 페이지 버튼 표시와 페이지 이동은 직접 클릭 검증하지 못했다.
