# 서비스 생성 레이아웃 재정리와 DDNS 기본 활성화

- 날짜: 2026-06-08
- ID: 017
- 리뷰 ID: ppzvldnwrhawqxaywmhgomvqmdbqpuzk

## 사용자 원 요청

이 씨발 디자인이라는 개념을 좀 생각을 해서 수정해줘.
지금은 레이아웃은 레이아웃대로 개판이고 예쁘지도 않아.
그리고 등록된 ddns가 있으면 기본적으로 도메인 적용이 활성화되도록 해줘.

## 변경 파일

- `src/app/page.services.create/view.pug`
- `src/app/page.services.create/view.ts`
- `devlog.md`
- `devlog/2026-06-08/017-service-create-layout-domain-default.md`

## 작업 내용

- 서비스 생성 화면을 단일 작업 카드 안에서 상단 기본 정보, 좌측 템플릿 변수, 우측 DDNS/요약 영역으로 재배치했다.
- 이전의 좌측 패널/보조 카드 구조를 제거하고, 내부 구획은 border divider 중심으로 정리해 레이아웃을 더 단순하게 만들었다.
- 도메인 설정은 큰 카드형 선택지 대신 compact segmented control로 변경했다.
- 등록된 DDNS suffix가 있으면 최초 도메인 옵션 로드 시 `domain_mode`를 `registered`로 자동 설정하도록 했다.
- 사용자가 직접 도메인 사용 안 함을 선택한 뒤에는 자동 기본값이 다시 덮어쓰지 않도록 `domainModeTouched` 플래그를 추가했다.

## 확인 결과

- `wiz_project_build(clean=false)`: 통과
- 로컬 `http://127.0.0.1:3001/services/create`에 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 추가해 접근을 시도했으나 인증 세션이 없어 `/access`로 리다이렉트됨.
