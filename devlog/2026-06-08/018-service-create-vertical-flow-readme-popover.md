# 서비스 생성 세로 흐름과 README 팝오버 적용

- 날짜: 2026-06-08
- ID: 018
- 리뷰 ID: ppzvldnwrhawqxaywmhgomvqmdbqpuzk

## 사용자 요청

서비스 생성 화면에서 시선이 좌우로 오가지 않도록 위에서 아래로 설정하는 흐름으로 수정한다. 템플릿을 가장 먼저 선택하게 하고, 선택 템플릿 README는 기본 노출하지 않고 작은 `?` 버튼으로 말풍선 팝오버에서 확인하게 한다. 목록으로 돌아가기와 생성 버튼은 UI/UX 흐름에 맞게 잘 보이도록 재구성한다.

## 변경 파일

- `src/app/page.services.create/view.pug`
  - 서비스 생성 화면을 단일 세로 컬럼 흐름으로 재배치했다.
  - 템플릿 선택을 첫 섹션으로 올리고 README를 `?` 버튼 팝오버로 숨겼다.
  - 기본 정보, 템플릿 변수, 도메인 설정, 생성 요약을 위에서 아래로 이어지는 구획으로 정리했다.
  - 목록으로 돌아가기와 생성 버튼을 하단 sticky 액션 바로 이동했다.
- `src/app/page.services.create/view.ts`
  - README 팝오버 상태와 토글/닫기 메서드를 추가했다.
  - 템플릿 변경 시 README 팝오버가 자동으로 닫히도록 했다.

## 확인 결과

- `wiz_project_build(clean=false)` 성공.
- `curl -I`에 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 넣어 `http://127.0.0.1:3001/services/create`가 200 응답하는 것을 확인했다.
- Playwright headless 검증에도 동일 쿠키를 넣어 접근했으나 인증 세션이 없어 `/access`로 이동했다. 콘솔 오류는 없었다.

## 남은 리스크

- 인증된 브라우저 세션에서 실제 서비스 생성 입력/README 팝오버/하단 액션 위치를 직접 클릭 검증하지 못했다.
