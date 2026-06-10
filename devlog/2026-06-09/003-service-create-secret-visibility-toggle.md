# 서비스 생성 비밀 값 표시 토글 추가

- 날짜: 2026-06-09
- ID: 003
- 리뷰 ID: ppzvldnwrhawqxaywmhgomvqmdbqpuzk

## 사용자 요청

비밀 값은 눈 아이콘 토글 버튼을 오른쪽에 추가해서 확인할 수 있도록 한다.

## 변경 파일

- `src/app/page.services.create/view.pug`
  - 비밀 템플릿 변수 input 오른쪽에 눈 아이콘 버튼을 추가했다.
  - 토글 버튼 클릭 시 password/text 표시가 전환되도록 입력 영역을 재구성했다.
- `src/app/page.services.create/view.ts`
  - 비밀 필드별 표시 상태 signal을 추가했다.
  - 템플릿 변경/상세 로드 시 표시 상태를 초기화했다.
  - 비밀 값 보기/숨기기 라벨과 아이콘 helper를 추가했다.

## 확인 결과

- `wiz_project_build(clean=false)` 성공.
- `curl -I`에 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 넣어 `http://127.0.0.1:3001/services/create`가 200 응답하는 것을 확인했다.
- Playwright headless 검증에도 동일 쿠키를 넣어 접근했으나 인증 세션이 없어 `/access`로 이동했다. 콘솔 오류는 없었다.

## 남은 리스크

- 인증된 브라우저 세션에서 실제 비밀 값 입력과 눈 아이콘 토글 동작은 직접 클릭 검증하지 못했다.
