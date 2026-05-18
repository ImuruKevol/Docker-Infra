# 226. DDNS 서버 등록 모달 입력 항목 단순화

- 날짜: 2026-05-18
- 요청자: 권태욱
- 리뷰 ID: lrmzidmbdswuudpmvcjfayyucjmiofzx

## 원 요청

> DDNS 서버 추가 모달의 설명이 너무 알아보기가 힘들어. Wildcard suffix는 예를 들어 부여받은 ddns 권한이 *.sub.season.co.kr이라면 sub.season.co.kr만 입력하세요 라는 안내 문구가 필요해. API Base URL과 등록/갱신 경로 설정은 굳이 따로 둘 필요 없이 DDNS 서버 API 라고만 통채로 입력받으면 돼.
> health 경로는 삭제해줘. "서비스 도메인 선택에 사용" 이라는 옵션도 필요 없어. 어차피 여기에 등록을 한다는건 사용을 할거라는거야.
> 그리고 TLS 인증서 검증이라는건 무슨 옵션인지 모르겠어. 설명이 부족해.

## 변경 요약

- DDNS 서버 추가/수정 모달 설명을 DDNS 관리 시스템의 wildcard 권한과 API Key 등록 흐름에 맞춰 다시 작성했다.
- `Wildcard suffix` 입력 도움말에 `*.sub.season.co.kr` 권한이면 `sub.season.co.kr`만 입력하라는 예시를 추가했다.
- `API Base URL`과 `등록/갱신 경로` 입력을 `DDNS 서버 API` 전체 URL 하나로 합쳤다.
- health 경로 입력, 연결 확인 버튼, `서비스 도메인 선택에 사용` 체크박스를 제거했다.
- HTTPS 인증서 검증 옵션에 자체 서명/사설 인증서 상황에서만 끄라는 설명을 추가했다.
- 저장 API는 새 `api_url` 입력을 기존 DB 컬럼인 `api_base_url`과 `registration_path`로 분해해 저장하도록 호환 처리했다.

## 변경 파일

- `src/app/page.domains/view.pug`
- `src/app/page.domains/view.ts`
- `src/model/struct/domains_ddns.py`
- `tests/api/test_domain_management_ui.py`
- `devlog.md`
- `devlog/2026-05-18/226-ddns-modal-api-url-simplification.md`

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/domains_ddns.py src/app/page.domains/api.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_domain_management_ui tests.api.test_services_preflight tests.api.test_migration_schema.MigrationSchemaStaticContractTest`: 19개 테스트 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과

## 남은 리스크

- 실제 DDNS 관리 시스템의 API path가 `/api/ddns/records`가 아니면 모달의 `DDNS 서버 API`에 해당 전체 URL을 정확히 입력해야 한다.
- 기존에 `enabled=false`로 저장된 DDNS endpoint는 수정 저장 전까지 DB 값이 남아 있을 수 있다.
