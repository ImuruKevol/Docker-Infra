# 286. 템플릿 상세 표준 안내 카드 좌측 배치

## 사용자 요청

- 리뷰 ID: hngkjahfaaxzdjrbmrijanonqdlbxfxw
- 제목: 템플릿 상세 UI 수정
- 원문: 템플릿 상세 화면에서 Compose, 기본값, Schema 탭에서 설명 카드가 들어가있는데, 이 설명 카드는 Monaco editor의 왼쪽에 다단으로 들어가야해.

## 변경 파일

- `src/app/page.templates/view.pug`
  - Compose, 기본값, Schema 탭의 표준 안내 카드를 Monaco editor 위쪽 단독 영역에서 제거하고 editor와 같은 grid 안의 좌측 패널로 이동했다.
  - 안내 항목은 작은 카드 단위로 유지하되, 좁은 화면에서는 editor 위쪽 다단 배치, 넓은 화면에서는 Monaco 왼쪽 세로 패널로 보이도록 반응형 grid를 적용했다.
  - README와 Preview 탭의 기존 표시 흐름은 유지했다.
- `devlog.md`
- `devlog/2026-05-20/286-template-detail-guide-left-panel.md`

## 확인 결과

- `wiz_project_build(clean=false)` 성공.
- `https://infra-dev.nanoha.kr/templates`에 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 설정해 Playwright 접근을 시도했으나 `/access`로 리다이렉트되어 인증 없는 실화면 시각 검증은 진행하지 못했다.
