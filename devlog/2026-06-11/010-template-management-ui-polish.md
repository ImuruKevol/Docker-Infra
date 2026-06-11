# 010 템플릿 관리 목록과 상세 편집 UI 정리

- 날짜: 2026-06-11
- 리뷰 ID: akzftdlktpeogugonbrxquomuwxujxzo

## 사용자 원 요청

- 템플릿 목록 화면 헤더의 새 템플릿/저장 버튼 제거, 새로고침 버튼 추가.
- 목록 상단 README.md/docker-compose.yaml 뱃지 제거.
- 템플릿 컬럼 설명 문구 제거, 목록 컬럼 폭/태그 영역/텍스트 크기 조정, 상태 컬럼 제거.
- 서비스 상세/템플릿 상세 헤더 뱃지 제거, 템플릿명 아래 Namespace 제거.
- 템플릿 노출 체크박스를 스위치 토글로 변경.
- 템플릿 상세의 서비스 생성/삭제 버튼을 헤더 오른쪽으로 이동하고 미리보기 버튼 제거.
- AI 수정/점검 버튼과 모달 제거.
- README/기본값/Compose/Schema/Preview 탭을 왼쪽 가이드 패널과 오른쪽 편집/미리보기 영역 구조로 정리.

## 변경 파일

- `src/app/page.templates/view.pug`
- `src/app/page.templates/view.ts`
- `src/app/page.services/view.pug`
- `devlog.md`
- `devlog/2026-06-11/010-template-management-ui-polish.md`

## 변경 내용

- 템플릿 화면 상단 공통 헤더를 새로고침 버튼만 보이도록 정리하고, 상세 헤더 오른쪽에 저장/서비스 생성/삭제 액션을 배치했다.
- 템플릿 목록에서 파일 뱃지, 설명 fallback, 상태 컬럼을 제거하고 템플릿/Namespace 고정 폭과 태그 가변 폭을 적용했다.
- Namespace와 태그 텍스트 크기를 키워 목록 가독성을 보강했다.
- 템플릿 상세 헤더의 편집 뱃지와 Namespace 보조 문구를 제거하고, 서비스 상세 헤더의 "서비스 상세" 뱃지도 제거했다.
- 서비스 생성 화면 노출 여부를 checkbox에서 role=switch 토글 버튼으로 변경했다.
- AI 수정/점검 버튼, 모달, 관련 TypeScript 상태/메서드 참조를 제거했다.
- README 가이드를 추가하고 README/Compose/기본값/Schema 탭을 왼쪽 가이드 패널과 오른쪽 Monaco editor 레이아웃으로 통일했다.
- Preview 탭도 왼쪽 입력/검증 패널과 오른쪽 렌더링 결과 패널 구조로 변경했다.

## 검증 결과

- 성공: WIZ project build `main`
- 확인: `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 추가한 Playwright 확인을 시도했으나 로컬 서버가 인증 화면(`/access`)으로 리다이렉트되어 인증 후 화면 검증은 수행하지 못했다.
- 확인: 제거 대상 문구(`AI 수정/점검`, `Compose 표준 파일 세트`, 상세 헤더 뱃지 텍스트)가 화면 템플릿에서 제거됐는지 검색으로 확인했다.
