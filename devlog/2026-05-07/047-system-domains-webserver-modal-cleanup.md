# 시스템 설정 웹서버/브랜딩 정리, 도메인 관리 필터/SSL 개선, 공통 모달 취소 라벨 정비

- **ID**: 047
- **날짜**: 2026-05-07
- **유형**: 기능 추가

## 작업 요약
시스템 설정 화면에서 일반 브랜딩, Harbor/GitLab, Nginx/Apache2 및 SSL 인증서 경로 관리를 실제 동작 기준으로 재구성했다. 도메인 관리 화면은 Cloudflare zone/record 중심으로 단순화하고, 실시간 필터와 SSL 상태 요약을 추가했다. 공통 모달의 cancel 라벨 처리도 정리해 `true`가 노출되지 않도록 수정했다.

## 원문 요청사항
```text
시스템 설정
- svg를 업로드했더니 이미지가 보이질 않아
- Harbor, GitLab 설정은 사용/미사용 체크 여부에 따라 해당 설정들을 보이게/안보이게 수정
- Harbor는 기본 Project라는 설정은 필요 없음.
- 상단의 4개 카드가 의미가 없는 것 같음. 삭제 요망.
- Public URL은 의미가 없는 것으로 보임. 설정값 삭제 요망. 이 설정은 도메인 관리, 서버 관리 등 여러 곳에서 사용되고 있는 것으로 보이는데, 전부 삭제 필요.
- Nginx/Apache2(httpd) 설치 여부에 따른 관리 기능이 필요함. nginx/apache2(httpd) 설치 경로와 데몬 실행 상태 등에 따라 사용 중인 웹서버가 무엇인지 확인하고, 설정 파일들의 위치 및 SSL 인증서 파일들의 경로를 설정할 수 있는 기능이 필요함.
  - SSL 인증서의 경우엔 인증서 파일들을 복호화 및 분석해서 상세 정보(유효 기간 등 메타 데이터들)를 확인할 수 있는 기능이 필요함.

도메인 관리
- Content 컬럼의 값이 너무 길어질 경우가 있음. 최대 길이 제한이 필요함.
- DNS Records는 실시간 검색 필터가 필요함. 다시 API를 요청할 필요는 없고, Type은 토글 버튼 형식으로, 그 옆에 Text Input으로는 Name, Content로 실시간 필터링 기능이 필요함. A 타입들에 지정된 IP들을 그루핑해서 IP별로 필터링도 있으면 좋을 것 같음.
- 시스템 설정에서 설정된 SSL 인증서들의 상태를 여기에서도 보여줄 수 있으면 좋을 것 같음.
- 상단 영역에 정보 카드들이 9개나 있는데 전부 제거할 것.
- 인증서 상태는 상세 컨텐츠 영역의 헤더 부분에 축약해서 보여줄 것.
- 연결된 서비스 도메인의 경우엔 일단 제거할 것. 추후 대대적인 개선이 필요해서 일단 제거하고 나중에 추가하는게 나을 것 같음.

공통
- 삭제 확인 모달 등에서 cancel 위치에 "true"라는 값이 표시되고 있음. 기본적으로 "취소"라던가 "Cancel"과 같은 텍스트를 보여주도록 할 것.
```

## 변경 파일 목록
- `src/model/struct/appearance.py`
  - 일반 브랜딩 설정 저장과 업로드 asset 경로 해석, SVG 포함 MIME 처리 유지
- `src/model/struct/integrations.py`
  - Harbor 기본 project 필드 제거
- `src/model/struct/webserver.py`
  - nginx/apache2 감지, daemon 상태, 설정 경로, SSL cert 분석과 요약 추가
- `src/model/struct/domains.py`
  - 도메인 상세 응답을 SSL 인증서 요약 중심으로 정리하고 불필요한 summary 집계를 제거
- `src/model/struct/setup.py`
  - `public_url` 설정 제거
- `src/model/struct.py`
  - `appearance`, `domains`, `integrations`, `webserver` 접근자 정리
- `src/app/page.system/api.py`
  - 일반 설정, 연동 설정, 웹서버/SSL 설정 로드·저장 API 정리
- `src/app/page.system/view.ts`
  - 일반 브랜딩, SVG 업로드, Harbor/GitLab 토글, 웹서버/SSL 상태 편집 로직 재구성
- `src/app/page.system/view.pug`
  - 상단 카드 제거, 브랜딩 입력/업로드, Harbor/GitLab 토글 표시, 웹서버/SSL 섹션 추가
- `src/app/page.domains/view.ts`
  - Zone 상세, DNS record 실시간 필터, SSL summary, 서비스 연계 잔여 상태 정리
- `src/app/page.domains/view.pug`
  - 상단 정보 카드 제거, record type/IP/name/content 필터, Content truncate, SSL header 요약, linked service domain UI 제거
- `src/app/page.dashboard/view.pug`
  - Runtime 카드에서 `public_url` 제거
- `src/portal/season/libs/appearance.ts`
  - favicon SVG MIME/type 적용과 cache bust 처리
- `src/portal/season/libs/src/modal.ts`
  - cancel 기본 라벨과 boolean/string normalize 처리
- `src/portal/season/app/modal/view.ts`
  - cancel 텍스트 helper 추가
- `src/portal/season/app/modal/view.pug`
  - cancel 버튼이 `취소` 라벨을 표시하고 `model.cancel()`을 사용하도록 수정
- `tests/api/test_system_settings_dynamic_menu.py`
  - appearance/webserver/public_url 제거 계약 검증 추가
- `docs/docker-infra-runtime.md`
  - Harbor 필드와 system/domains 동작 설명 갱신
- `docs/api/openapi.json`
  - setup schema/example에서 `public_url` 제거

## 검증 결과
- `wiz_project_build(projectName="main", clean=false)` 통과
- `wiz_project_build(projectName="main", clean=true)` 통과
- `python -m compileall src/model src/app/page.system src/app/page.domains src/route/api-system-assets src/route/api-system-assets-path src/route/api-system-appearance` 통과
- `python -m unittest tests.api.test_system_settings_dynamic_menu tests.api.test_migration_schema tests.api.test_wiz_structure_contract` 통과 (`skipped=2`)
- live API 확인
  - `POST /wiz/api/page.system/load` → `200`
  - `POST /wiz/api/page.domains/load` → `200`
  - `GET /api/system/appearance` → `200`
  - `POST /api/system/assets` SVG 업로드 후 asset fetch → `200`, `content-type: image/svg+xml`
- `systemctl restart wiz.docker-infra` 후 `/system` load 500 해소 확인
