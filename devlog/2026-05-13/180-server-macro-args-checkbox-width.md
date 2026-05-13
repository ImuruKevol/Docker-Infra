# 서버 상세 매크로 실행 인자 체크박스 폭 축소

- **ID**: 180
- **날짜**: 2026-05-13
- **유형**: UX 수정

## 작업 요약
서버 상세 매크로 탭의 "실행 인자 사용" 체크박스 라벨이 텍스트 길이만큼만 차지하도록 조정했다.
실행 버튼 폭과 위치는 기존 레이아웃을 유지했다.

## 원문 요청사항
```text
실행 인자 사용 체크박스 및 그 공간이 너무 길어. 텍스트 길이만큼만 차지하도록 수정해줘. 그렇다고 실행 버튼의 길이를 늘릴 필요는 없고 지금 width가 딱 맞아. 오른쪽에 빈 공간이 있어도 돼.
```

## 변경 파일 목록
- `src/app/page.servers/view.pug`: 실행 인자 체크박스 라벨을 `inline-flex w-fit max-w-full`로 변경.
- `devlog.md`, `devlog/2026-05-13/180-server-macro-args-checkbox-width.md`: 작업 이력 기록.

## 확인 결과
- `src/app/page.servers/view.pug`에서 체크박스 라벨 클래스 적용 확인.
- `wiz_project_build(projectName=main, clean=false)` 성공.
