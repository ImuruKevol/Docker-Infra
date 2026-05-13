# 작업 로그 페이지네이션과 개수 select 폭 보정

- **ID**: 174
- **날짜**: 2026-05-13
- **유형**: UX 수정

## 작업 요약
작업 로그 화면의 목록 조회 API에 page/offset/total 기반 페이지네이션을 추가하고, 화면 하단에서 페이지 번호를 선택할 수 있도록 Season pagination 컴포넌트를 연결했다.
개수 선택 select는 숫자와 기본 화살표가 겹치지 않도록 고정 폭과 오른쪽 패딩을 키웠다.

## 원문 요청사항
```text
작업 로그 화면에서 페이지네이션이 제대로 적용되고있지 않은 것으로 보여.
페이지를 선택할 수 있는 부분도 없고. 그리고 갯수 선택 select는 width를 조금 더 키워야 해. 화살표 아이콘이 숫자 표시에 겹쳐져서 보이고 있어.
```

## 변경 파일 목록
- `src/model/struct/infra_catalog_registry.py`: 작업 로그 조회 필터 SQL을 재사용 가능하게 분리하고, 총 건수 계산 및 LIMIT/OFFSET 기반 페이지 조회와 pagination 메타데이터를 추가.
- `src/app/page.operations/api.py`: 작업 로그 load API에서 `page` 파라미터를 파싱해 모델 조회에 전달.
- `src/app/page.operations/view.ts`: 현재 페이지/총 건수/페이지 범위 상태와 페이지 이동 로직, 페이지 요약 텍스트를 추가.
- `src/app/page.operations/view.pug`: 작업 로그 하단 페이지네이션 UI를 추가하고, 개수 select 폭/패딩을 보정.
- `devlog.md`, `devlog/2026-05-13/174-operations-pagination-select-width.md`: 작업 이력 기록.

## 확인 결과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/infra_catalog_registry.py src/app/page.operations/api.py` 성공.
- `wiz_project_build(projectName="main", clean=false)` 성공.

## 남은 리스크
- 실제 운영 브라우저에서 `/operations` 화면을 직접 클릭해 페이지 이동과 select 렌더링을 확인하지는 못했다.
