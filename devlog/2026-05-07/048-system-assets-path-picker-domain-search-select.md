# 시스템 설정 SVG/지연 업로드, 로컬 경로 선택 모달, 도메인 A 레코드 공통 검색 선택 적용

- **ID**: 048
- **날짜**: 2026-05-07
- **유형**: 기능 추가

## 작업 요약
시스템 설정의 favicon/logo 업로드를 저장 시점 일괄 업로드로 바꾸고, SVG asset 응답을 실제 바이너리로 내려 브라우저 렌더가 깨지지 않도록 수정했다.  
웹서버/SSL 경로 입력은 로컬 파일 트리 모달에서 파일/디렉토리를 선택하도록 바꿨고, 도메인 관리의 A 레코드 IP 필터는 공용 검색형 select 컴포넌트로 교체했다.

## 원문 요청사항
```text
시스템 설정
- 여전히 svg를 업로드하면 이미지가 깨지고 있음. data/di_logo.svg를 업로드해놨으니 이걸로 확실하게 검증할 것.
- favicon과 logo는 이미지 선택 시 바로 업로드를 해버리지 말고, 일반 설정 저장을 눌러야 변경된 이미지만 업로드되도록 할 것.
- 웹 서버 및 SSL 부분에서는 Nginx가 실행 중이면 Nginx만 표시하고, Apache2가 실행 중이면 Apache2만 표시를 해야해.
- 메인 설정 파일 경로와 사이트 설정 디렉토리, 인증서 추가 모달의 인증서 파일 경로 및 키 파일 경로는 서버 관리 화면에서 파일 및 디렉토리 모달을 참고해서 사용자가 직접 파일 트리에서 선택할 수 있어야 해.

도메인 관리
- A 레코드 IP select는 만들어놓은 공용 search select 컴포넌트로 바꿔줘.
```

## 변경 파일 목록
- `src/route/api-system-assets-path/controller.py`
  - asset 응답을 `wiz.response.send()` 문자열화 경로에서 Flask `Response` 기반 바이너리 응답으로 변경했다.
- `src/app/page.system/api.py`
  - 로컬 파일/디렉토리 목록 조회용 `browse_local_files()` API를 추가하고 홈 경로, 숨김 파일 필터, 절대 경로 해석을 직접 처리하도록 구성했다.
- `src/app/page.system/view.ts`
  - favicon/logo를 선택 후 저장 시 업로드하는 staged flow로 변경했다.
  - 실행 중 웹서버만 노출하도록 필터링하고, 웹서버/SSL 경로 선택용 로컬 파일 브라우저 상태와 동작을 추가했다.
- `src/app/page.system/view.pug`
  - General 카드의 업로드 UX를 저장 전 대기 방식으로 재구성했다.
  - 웹서버 경로 입력과 인증서 경로 입력에 파일/디렉토리 선택 버튼 및 로컬 파일 브라우저 모달을 추가했다.
- `src/app/page.domains/view.ts`
  - A 레코드 IP 필터용 공용 search select item 변환 함수를 추가했다.
- `src/app/page.domains/view.pug`
  - 기존 native select를 `wiz-component-search-select`로 교체했다.
- `tests/api/test_system_settings_dynamic_menu.py`
  - `/system` API 정적 계약에 로컬 파일 브라우저 엔드포인트 존재 여부를 반영했다.

## 검증 결과
- `wiz_project_build(projectName="main", clean=true)` 1회, 이후 일반 빌드 다수 통과
- `python -m unittest tests.api.test_system_settings_dynamic_menu tests.api.test_wiz_structure_contract` 통과 (`skipped=2`)
- `git diff --check` 통과
- live 확인
  - `POST /wiz/api/page.system/browse_local_files` → `200`, 기본 경로 `/root`
  - `data/di_logo.svg` 업로드 후 `/api/system/assets/...svg` 응답이 `image/svg+xml`로 내려오고 본문이 실제 `<svg ...>`로 시작함
  - Playwright 검증에서 `#system-logo-upload` 파일 선택 직후 `/api/system/assets` 호출 `0회`, `일반 설정 저장` 후 `1회`
  - 저장 후 logo 이미지 `naturalWidth=150`, `naturalHeight=150`, page error 없음
  - `/domains` 진입 시 page error 없음

## 비고
- 새 `api.py` 함수는 현재 WIZ 런타임에서 hot-reload만으로 교체되지 않아, live 검증을 위해 `wiz.docker-infra` 데몬 재시작 1회를 수행했다.
