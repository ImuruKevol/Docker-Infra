# 107. 도메인 관리 레코드 UI와 DNS 기본값 정리

## 사용자 요청

도메인 관리 화면에서 긴 DNS Content 때문에 화면 폭이 헤더보다 커지는 문제를 줄이고, CNAME/TXT 등 긴 값은 상세 모달에서 확인하도록 개선한다. Exposure(Proxied)는 기본 false로 고정하고 화면에서 제거하며, TTL/Priority도 숨긴다. 인증서 업로드 버튼 줄바꿈, 레코드 타입 안내 카드, 레코드 타입 입력 방식, A 레코드 특수 Name 설명, 좌측 도메인 목록 표시, Name/Content 통합 필터, Search Select 1회 클릭 선택 버그, 우측 Domain 설정 카드 제거를 함께 처리한다.

## 변경 파일

- `src/app/page.domains/view.pug`
- `src/app/page.domains/view.ts`
- `src/app/component.search.select/view.html`
- `src/app/component.search.select/view.ts`
- `src/model/struct/domains_cloudflare.py`
- `tests/api/test_domain_management_ui.py`

## 변경 내용

- DNS 레코드 표에서 Exposure/TTL 컬럼을 제거하고 Content 컬럼을 IP 또는 상세 버튼만 표시하도록 축소했다.
- CNAME/TXT 등 긴 Content는 DNS 레코드 상세 모달에서 확인하도록 추가했다.
- 레코드 타입 안내 카드를 제거하고 목록 상단 타입 토글 hover 툴팁으로 설명을 이동했다.
- 레코드 추가/수정 모달의 타입 선택을 토글 버튼으로 바꾸고 TTL/Priority/Proxy 입력을 제거했다.
- A 레코드 Name 입력에서 빈 값, `@`, `*`, `_` 접두어 동작 설명을 표시했다.
- 저장 시 DNS record name 빈 값은 `@`로 정규화하고, proxied는 false, TTL은 타입별 기본값, MX/SRV priority는 내부 기본값으로 고정했다.
- 좌측 도메인 목록에서 Zone ID 노출을 제거하고 record 수와 last sync를 배지로 표시했다.
- Name/Content 필터를 하나의 검색 입력으로 통합했다.
- 인증서 업로드 버튼에 `whitespace-nowrap`와 최소 폭을 적용했다.
- Search Select에서 항목 클릭 시 내부 value를 즉시 갱신하고 이벤트 전파를 막아 1회 클릭으로 선택되게 했다.
- 도메인 관리 UI 변경을 고정하는 정적 테스트를 추가했다.

## 검증

- `wiz_project_build(projectName="main", clean=false)` 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_domain_management_ui.py tests/api/test_server_macros.py tests/api/test_services_preflight.py` 성공
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/domains_cloudflare.py tests/api/test_domain_management_ui.py` 성공
