# 서비스 생성 화면 폭과 템플릿 변수 UX 보정

- 날짜: 2026-06-09
- ID: 001
- 리뷰 ID: ppzvldnwrhawqxaywmhgomvqmdbqpuzk

## 사용자 요청

- README `?` 팝오버 버튼이 템플릿 선택 이후 흐름에서 보이도록 위치를 조정한다.
- 템플릿 선택 select 아래에 중복 출력되는 텍스트를 제거한다.
- 비밀 값 필드도 화면에 보여주고 사용자가 직접 지정할 수 있게 한다.
- DDNS를 사용 안 함에서 사용함으로 바꿀 때 서비스 이름 밸리데이션이 돌지 않도록 하고, 밸리데이션은 생성 버튼에서만 수행한다.
- 서비스 생성 화면 컨텐츠 폭이 다른 화면처럼 전체 폭을 쓰도록 수정한다.

## 변경 파일

- `src/app/page.services.create/view.pug`
  - 화면 컨테이너와 하단 액션 바의 `max-w-4xl` 제한을 제거했다.
  - README `?` 버튼을 템플릿 select 아래로 이동했다.
  - select 아래 선택 템플릿명/태그 중복 출력 블록을 제거했다.
  - 템플릿 변수 목록에 비밀 값 필드를 포함하고 password input으로 표시했다.
- `src/app/page.services.create/view.ts`
  - 비밀 값 placeholder helper를 추가했다.
  - DDNS 모드 전환에서 템플릿 적용/서비스 이름/포트 검증을 실행하지 않도록 정리했다.
  - 도메인 대상 포트가 없어도 도메인 모드를 즉시 꺼버리지 않도록 조정해 생성 시점 검증으로 넘겼다.

## 확인 결과

- `wiz_project_build(clean=false)` 성공.
- `curl -I`에 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 넣어 `http://127.0.0.1:3001/services/create`가 200 응답하는 것을 확인했다.
- Playwright headless 검증에도 동일 쿠키를 넣어 접근했으나 인증 세션이 없어 `/access`로 이동했다. 콘솔 오류는 없었다.

## 남은 리스크

- 인증된 브라우저 세션에서 README 팝오버, 비밀 값 입력, DDNS 토글, 생성 버튼 검증 흐름을 직접 클릭 검증하지 못했다.
