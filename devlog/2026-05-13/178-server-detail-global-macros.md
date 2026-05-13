# 서버 상세 카드 제거와 전역 매크로 실행 전용화

- **ID**: 178
- **날짜**: 2026-05-13
- **유형**: UX 수정

## 작업 요약
서버 관리 상세 상단의 중간 정보 카드 5개를 제거했다.
서버 상세 매크로 탭은 서버 전용 매크로 생성/수정/삭제 기능을 제거하고, 전역 매크로만 조회·선택·실행하도록 정리했다.

## 원문 요청사항
```text
작업을 진행해줘.

서버 관리 상세에서 중간에 있는 카드 5개는 삭제해줘.
매크로는 서버 전용 매크로 기능을 삭제하고, 오로지 전역 매크로만 불러와서 실행할 수 있도록 수정해줘. 그리고 실행할 매크로 선택 시 설명을 보여주도록 해줘.
```

## 변경 파일 목록
- `src/app/page.servers/view.pug`: 서버 상세 중간 카드 5개와 서버 전용 매크로 관리 패널/모달 제거, 전역 매크로 선택 시 설명 표시 UI 추가.
- `src/app/page.servers/view.ts`: 서버 전용 매크로 상태와 CRUD 로직 제거, 전역 매크로만 로드하도록 변경, 선택된 매크로 설명 helper 추가.
- `src/app/page.servers/api.py`: 서버 페이지 매크로 목록 API를 전역 매크로만 반환하도록 변경하고, 매크로 실행 API에서 전역 매크로 ID만 허용하도록 검증 추가.
- `devlog.md`, `devlog/2026-05-13/178-server-detail-global-macros.md`: 작업 이력 기록.

## 확인 결과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/app/page.servers/api.py` 통과.
- 서버 페이지 내 서버 전용 매크로 UI/API 잔여 참조 검색 통과.
- `wiz_project_build(projectName=main, clean=false)` 성공.
