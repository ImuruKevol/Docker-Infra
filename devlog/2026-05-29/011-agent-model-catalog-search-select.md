# AI Agent 모델 목록 공식 출처 연동과 검색 Select 적용

- 날짜: 2026-05-29
- 리뷰 ID: cxaqmytxjrdnjjdcuazqouethjqeipfv
- 요청: Codex, Claude Code, 헤르메스가 선택한 provider별 공식 홈페이지에서 모델 목록을 가져오고, 기본 select가 아닌 실시간 검색 필터링 커스텀 select로 모델을 선택하게 해 달라는 요청.

## 변경 요약

- `codex_runtime.agent_model_catalog()`를 추가해 agent/provider별 공식 모델 출처를 조회하고 모델 후보를 표준 item 목록으로 반환하도록 했다.
- OpenRouter는 공개 models JSON을 사용하고, OpenAI/Anthropic/Gemini/xAI/DeepSeek/Novita는 공식 문서 페이지에서 모델 ID를 파싱하며 실패 시 provider별 기본 후보를 제공하도록 했다.
- 시스템 설정 API에 `ai_agent_model_catalog()`를 추가했다.
- Codex, Claude Code, 헤르메스 모델 입력을 `wiz-component-search-select` 기반 검색형 select로 바꿨다.
- 헤르메스 provider 변경 시 해당 provider 모델 목록을 다시 불러오도록 연결했다.
- installer WIZ bundle archive와 checksum을 최신 변경 기준으로 재생성했다.

## 변경 파일

- `src/model/struct/codex_runtime.py`
- `src/app/page.system/api.py`
- `src/app/page.system/view.ts`
- `src/app/page.system/view.pug`
- `tests/api/test_system_settings_dynamic_menu.py`
- `installer/payload/checksums.sha256`
- `installer/payload/wiz-bundle.tar.zst`
- `devlog.md`
- `devlog/2026-05-29/011-agent-model-catalog-search-select.md`

## 확인

- 공식 출처 확인: OpenAI Models, Claude Code model config, OpenRouter models API, Gemini model docs, xAI models docs, DeepSeek pricing/models docs, Novita API docs.
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/codex_runtime.py src/model/struct/ai_settings.py src/app/page.system/api.py`: 성공
- `python -m unittest tests/api/test_services_preflight.py tests/api/test_system_settings_dynamic_menu.py tests/api/test_installer_contract.py`: 성공
- `wiz_project_build(projectName="main", clean=false)`: 성공
- `/opt/conda/bin/wiz bundle --project=main`: 성공
- `/root/docker-infra/update-wiz-bundle.sh`: 성공, payload checksum 검증 포함
- `cd installer/payload && sha256sum -c checksums.sha256`: 성공
- `curl https://openrouter.ai/api/v1/models`: 357개 모델 응답 확인
- `curl -I` with `season-wiz-project=main; season-wiz-devmode=true` against `http://127.0.0.1:3001/dashboard`: HTTP 200
- `POST /wiz/api/page.system/load` with the same cookies: route reachable, application response 401 because no authenticated session cookie was present

## 남은 리스크

- 인증된 브라우저 세션에서 실제 dropdown 검색/선택 조작까지는 확인하지 않았다.
- OpenAI 등 일부 문서 페이지는 HTML 구조가 바뀌거나 차단되면 fallback 목록으로 동작한다.
