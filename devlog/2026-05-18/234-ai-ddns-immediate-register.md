# 234. AI DDNS 수정 직후 등록 API 호출 추가

- 날짜: 2026-05-18
- 요청자: 권태욱
- 리뷰 ID: lrmzidmbdswuudpmvcjfayyucjmiofzx

## 원 요청

> 아래 에러가 계속 반복되고 있어. AI로 DDNS 도메인을 적용할 때 등록된 DDNS 서버 정보를 이용해 API 호출까지 해서 해당 DDNS 서브도메인을 등록하는 과정까지 진행이 되어야 해.
> 확실하게 문제점을 분석 후 검증까지 해줘.

## 변경 요약

- 문제 원인을 AI fallback이 도메인 row는 저장하지만 DDNS API 호출은 기존 배포/nginx 적용 단계까지 기다리던 구조로 정리했다.
- 런타임 AI 수정에서 DDNS 도메인 draft가 적용되면 `update_wizard` 직후 `ddns_model.register_service_domains()`를 즉시 호출하도록 했다.
- 즉시 등록 결과를 `ddns_register_result`로 반환하고, 성공/실패 여부를 AI repair summary와 warnings에 반영하도록 했다.
- 기존 배포/nginx 적용 단계의 DDNS 등록 호출은 유지해 배포 시점에도 한 번 더 idempotent하게 확인된다.
- 관련 정적 계약 테스트를 보강했다.

## 변경 파일

- `src/model/struct/ai_assistant.py`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-18/234-ai-ddns-immediate-register.md`

## 확인한 내용

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py src/model/struct/codex_runtime.py src/model/struct/services_update.py tools/docker_infra_mcp.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight`: 12개 테스트 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_domain_management_ui tests.api.test_installer_contract tests.api.test_local_executor tests.api.test_migration_schema`: 22개 테스트 통과, 2개 skip
- `git diff --check`: 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과

## 남은 리스크

- 실제 API 호출 성공 여부는 외부 DDNS 관리 서버 응답과 공인 IP 조회 결과에 의존한다.
- 즉시 등록은 DDNS 도메인 draft가 확인되는 AI runtime repair 경로에서만 수행된다.
