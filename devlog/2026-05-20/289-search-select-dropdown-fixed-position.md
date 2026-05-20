# 검색 select 드롭다운 overflow clipping 방지

- 날짜: 2026-05-20
- ID: 289
- 리뷰 ID: qcgmkfnyonlsrvidmbteanvezvhkudrj

## 사용자 요청

서비스 상세의 AI 검사/수정 모달과 템플릿 상세의 AI 수정/점검 모달에서 사용할 모델 선택 select 클릭 시 뜨는 목록이 부모의 overflow 설정때문인지 아랫부분이 footer에 잘려서 보이질 않아.

## 변경 파일

- `src/app/component.search.select/view.ts`
- `src/app/component.search.select/view.html`
- `devlog.md`
- `devlog/2026-05-20/289-search-select-dropdown-fixed-position.md`

## 변경 내용

- 공통 검색 select 드롭다운을 부모 박스 기준 `absolute` 배치에서 viewport 기준 `fixed` 배치로 변경했다.
- 드롭다운이 열릴 때 버튼 위치, viewport 여유 공간, 위/아래 방향을 계산해 모달 footer나 overflow 영역에 잘리지 않도록 했다.
- 스크롤/리사이즈 시 열린 드롭다운 위치를 다시 계산하고, 컴포넌트 파괴 시 scroll listener를 정리하도록 했다.
- 목록 영역 최대 높이를 계산값으로 적용해 작은 viewport에서도 검색 입력과 목록이 함께 표시되도록 했다.

## 검증

- `wiz_project_build(clean=false, projectName=main)` 성공.
- devmode 쿠키(`season-wiz-project=main`, `season-wiz-devmode=true`) 포함 `/services/create`, `/services`, `/templates` HTTP 200 응답 확인.
- Playwright 브라우저 확인 시 동일 쿠키를 넣었지만 운영자 접속 화면(`/access`)으로 리다이렉트되어 인증 이후 실제 모달 DOM 검증은 수행하지 못했다.
