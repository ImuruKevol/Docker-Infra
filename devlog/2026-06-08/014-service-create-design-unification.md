# 서비스 생성 화면 디자인 통일성 보강

- 날짜: 2026-06-08
- ID: 014
- 리뷰 ID: ppzvldnwrhawqxaywmhgomvqmdbqpuzk

## 사용자 원 요청

바뀐 화면이 너무 거지같아. 제대로 안할래? 다른 화면들과 통일성도 없고 디자인도 개판이고.

## 변경 파일

- `src/app/page.services.create/view.pug`
- `src/app/page.services.create/view.ts`
- `devlog.md`
- `devlog/2026-06-08/014-service-create-design-unification.md`

## 작업 내용

- 서비스 생성 화면을 서비스/템플릿/도메인 관리 화면과 같은 좌측 요약 패널 + 우측 작업 섹션 구조로 재배치했다.
- 이전 화면의 과한 색상 블록과 별도 생성 방식 안내 카드를 제거하고, 기존 화면들에서 쓰는 neutral card, border header, compact summary 패턴으로 정리했다.
- 생성 버튼을 sticky header 액션으로 올리고, 하단 중복 footer 액션을 제거해 다른 관리 화면의 액션 배치와 맞췄다.
- 템플릿 변수와 도메인 설정을 각각 독립된 작업 섹션으로 나누고, README/비밀값 안내/도메인 미리보기를 보조 패널로 정리했다.
- 생성 전 확인 모달도 도메인 관리 모달과 유사한 border header + body + footer 구조로 정리했다.

## 확인 결과

- `wiz_project_build(clean=false)`: 통과
- 로컬 `http://127.0.0.1:3001/services/create`에 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 추가해 접근을 시도했으나 인증 세션이 없어 `/access`로 리다이렉트됨. 실제 생성 화면 브라우저 검증은 수행하지 못했다.
