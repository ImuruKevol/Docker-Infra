# 서비스 생성 화면 서비스명 입력 위치와 AI 안내 카드 정리

- 날짜: 2026-05-20
- ID: 288
- 리뷰 ID: qcgmkfnyonlsrvidmbteanvezvhkudrj

## 사용자 요청

서비스 생성 시 템플릿 기반, AI 자동 구성, 직접 작성 모두 서비스 이름 입력하는 부분을 생성 타입 고르는 3개 토글 버튼 바로 아래쪽으로 이동해줘.
그리고 AI 자동 구성은 오른쪽의 "서비스 구성", "도메인 연결", "자동 보정" 카드 3개는 삭제해줘.
그리고 템플릿 기반 토글 버튼의 색상 템플릿을 컨텐츠 영역에 있는 색상 템플릿 기준으로 수정해줘.

## 변경 파일

- `src/app/page.services.create/view.pug`
- `src/app/page.services.create/view.ts`
- `devlog.md`
- `devlog/2026-05-20/288-service-create-name-ai-card-layout.md`

## 변경 내용

- 서비스 이름 입력 필드를 생성 방식 토글 3개 바로 아래의 공통 입력 영역으로 이동했다.
- 템플릿/AI/직접 작성 섹션 내부의 중복 서비스 이름 입력 필드를 제거했다.
- AI 자동 구성 우측 안내 카드 3개 렌더링을 제거하고, 초안 적용 완료 안내는 AI 입력 카드 안에 유지했다.
- 템플릿 기반 토글 활성 상태 색상을 템플릿 컨텐츠 영역과 동일한 indigo 계열로 맞췄다.

## 검증

- `wiz_project_build(clean=false, projectName=main)` 성공.
- `curl -k --cookie 'season-wiz-project=main; season-wiz-devmode=true' https://infra-dev.nanoha.kr/services/create` 응답 200 확인.
- Playwright 브라우저 확인 시 동일 쿠키를 넣었지만 운영자 접속 화면(`/access`)으로 리다이렉트되어 인증 이후 실제 DOM 검증은 수행하지 못했다.
