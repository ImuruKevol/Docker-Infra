# 230. 서비스 AI 생성/검사/수정 DDNS 컨텍스트 보강

- 날짜: 2026-05-18
- 요청자: 권태욱
- 리뷰 ID: lrmzidmbdswuudpmvcjfayyucjmiofzx

## 원 요청

> 서비스 AI 생성 및 검사/수정 로직에서 DDNS에 대한 부분이 들어가있는지 확인해줘. AI의 접근 권한에 DDNS에 대한 부분도 추가를 해야하고, 도메인 자동 생성 및 매핑 시 DDNS에 대한 부분이 제대로 동작해야해.

## 변경 요약

- 서비스 AI contract, system prompt, Docker Infra context에 DDNS 관리 서버와 wildcard suffix 선택 정책을 명시했다.
- AI 권한 범위에 DDNS 도메인 선택, 조회, 배포 시 등록 가능 여부를 추가했다.
- AI 도메인 정규화에서 DDNS endpoint id, provider, wildcard suffix, DDNS mode를 보존하도록 했다.
- 런타임 AI 검사/수정 컨텍스트와 수정 payload가 기존 DDNS 메타데이터를 잃지 않도록 보강했다.
- Codex MCP `infra_context`에 도메인 zone 목록과 DDNS endpoint 목록을 노출했다.
- 서비스 수정 경로에서 DDNS endpoint id가 Cloudflare zone id로 다시 저장되지 않도록 분기했다.

## 변경 파일

- `src/model/struct/ai_assistant.py`
- `src/model/struct/codex_runtime.py`
- `src/model/struct/services_update.py`
- `tools/docker_infra_mcp.py`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-18/230-service-ai-ddns-context.md`

## 확인한 내용

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py src/model/struct/codex_runtime.py src/model/struct/services_update.py tools/docker_infra_mcp.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight`: 12개 테스트 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_domain_management_ui`: 5개 테스트 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_installer_contract tests.api.test_local_executor tests.api.test_migration_schema`: 17개 테스트 통과, 2개 skip
- `git diff --check`: 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과

## 남은 리스크

- 실제 AI가 DDNS zone을 선택하는 end-to-end 호출은 모델 응답과 등록된 endpoint 데이터가 필요해 정적/빌드 검증으로 확인했다.
- DDNS 등록 자체는 기존 배포 단계의 `register_service_domains`와 외부 DDNS 관리 서버 응답에 의존한다.
