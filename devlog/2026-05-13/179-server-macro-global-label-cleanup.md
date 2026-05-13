# 서버 상세 매크로 전역 표시 제거

- **ID**: 179
- **날짜**: 2026-05-13
- **유형**: UX 수정

## 작업 요약
서버 상세 매크로 탭에서 "전역" 표시 텍스트를 제거했다.
매크로 선택 목록에서 활성 매크로의 전역 뱃지가 표시되지 않도록 정리했다.

## 원문 요청사항
```text
"전역"이라는 표시 텍스트 및 뱃지들은 삭제해줘.이제 전부 전역 매크로라서 의미가 없어
```

## 변경 파일 목록
- `src/app/page.servers/view.pug`: 매크로 탭 제목, 선택 placeholder, 빈 상태 문구에서 "전역" 표시 제거.
- `src/app/page.servers/view.ts`: 매크로 선택 항목의 전역 뱃지 제거, 요약 문구에서 "전역" 표시 제거.
- `src/app/page.servers/api.py`: 서버 페이지 매크로 실행 제한 오류 문구에서 "전역" 표시 제거.
- `devlog.md`, `devlog/2026-05-13/179-server-macro-global-label-cleanup.md`: 작업 이력 기록.

## 확인 결과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/app/page.servers/api.py` 통과.
- `src/app/page.servers` 내 "전역" 표시 잔여 검색 결과 없음.
- `wiz_project_build(projectName=main, clean=false)` 성공.
