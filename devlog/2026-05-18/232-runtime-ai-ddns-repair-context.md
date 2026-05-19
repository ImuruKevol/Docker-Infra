# 232. 런타임 AI DDNS 전환 repair 컨텍스트 보강

- 날짜: 2026-05-18
- 요청자: 권태욱
- 리뷰 ID: lrmzidmbdswuudpmvcjfayyucjmiofzx

## 원 요청

> 아래와 같이 DDNS 도메인 관련 AI 동작이 실패하고 있어.
> 런타임 검증/수정에서 DDNS 필수 값이 없다고 판단하며 도메인을 제거하고, DDNS 서브도메인 전환이 완료되지 않는 문제가 발생한다.

## 변경 요약

- 런타임 AI 검증/수정 컨텍스트에도 등록된 도메인 zone과 DDNS endpoint 목록을 자동 조회해 포함했다.
- DDNS 전환 의도가 있을 때 기존 도메인의 첫 label 또는 서비스 이름을 이용해 추천 DDNS 서브도메인을 계산하도록 했다.
- `ddns_repair_suggestion`에 endpoint, wildcard suffix, suggested_domain, domain_row, target port 정보를 넣어 AI repair가 바로 사용할 수 있게 했다.
- AI가 DDNS 전환 중 `form.domains`를 비워 반환하면 추천 DDNS domain row로 보정해 공개 도메인을 모두 제거하지 않도록 했다.
- 런타임 검증/수정 system prompt에 DDNS 값이 없다고 판단하지 말고 suggestion을 사용하라는 지침을 추가했다.

## 변경 파일

- `src/model/struct/ai_assistant.py`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-18/232-runtime-ai-ddns-repair-context.md`

## 확인한 내용

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py src/model/struct/codex_runtime.py src/model/struct/services_update.py tools/docker_infra_mcp.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight`: 12개 테스트 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_domain_management_ui tests.api.test_installer_contract tests.api.test_local_executor tests.api.test_migration_schema`: 22개 테스트 통과, 2개 skip
- `git diff --check`: 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과

## 남은 리스크

- 추천 DDNS 서브도메인은 명시된 DDNS 도메인이 없을 때 기존 도메인의 첫 label을 사용하므로, 사용자가 원하는 정확한 subdomain과 다를 수 있다.
- 실제 DDNS API 등록 성공 여부는 배포 시 외부 DDNS 관리 서버 응답과 공인 IP 조회 결과에 의존한다.
