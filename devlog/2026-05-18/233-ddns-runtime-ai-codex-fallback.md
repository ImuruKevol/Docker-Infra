# 233. DDNS 런타임 AI Codex 실패 fallback 추가

- 날짜: 2026-05-18
- 요청자: 권태욱
- 리뷰 ID: lrmzidmbdswuudpmvcjfayyucjmiofzx

## 원 요청

> 아래 에러가 뜨면서 AI 수정이 되지 않아.
> 런타임 검증 단계에서 `AI 검증 시도 실패: Codex 실행이 실패했습니다.`가 반복되고, DDNS 도메인 수정으로 넘어가지 못한다.

## 변경 요약

- DDNS repair suggestion이 있는 런타임 검증에서 Codex 호출이 실패하면 deterministic verification fallback을 반환하도록 했다.
- DDNS repair suggestion이 있는 런타임 수정에서 Codex 호출이 실패하면 추천 DDNS domain row로 서비스 수정 draft를 생성하도록 했다.
- stream 기반 런타임 수정에서도 Codex 수정 호출 실패 시 DDNS fallback으로 진행하도록 했다.
- fallback 결과에는 추천 DDNS 도메인, endpoint id, wildcard suffix, target port가 포함되며 기존 update/deploy 경로를 그대로 사용한다.
- 관련 정적 계약 테스트를 보강했다.

## 변경 파일

- `src/model/struct/ai_assistant.py`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-18/233-ddns-runtime-ai-codex-fallback.md`

## 확인한 내용

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py src/model/struct/codex_runtime.py src/model/struct/services_update.py tools/docker_infra_mcp.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight`: 12개 테스트 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_domain_management_ui tests.api.test_installer_contract tests.api.test_local_executor tests.api.test_migration_schema`: 22개 테스트 통과, 2개 skip
- `git diff --check`: 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과

## 남은 리스크

- fallback은 DDNS 전환 의도와 추천 endpoint가 확인되는 경우에만 동작한다.
- Codex 자체 실패 원인은 별도 런타임 환경, 로그인 상태, CLI stderr 확인이 필요할 수 있다.
