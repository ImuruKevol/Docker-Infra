# 163. Codex 로그인 상태 판정과 커스텀 CLI 표시 제거

## 원 요청

- 리뷰 ID: `jhicunojymorogdtegqmkfqpkqrzampu`
- 제목: codex 로그인 상태 버그
- 요청: "확실하게 내용을 분석하고 확인 후 작업해줘."
- 세부 내용: 터미널에서는 Codex 로그인이 확인되지만 시스템 설정 화면에서는 조회되지 않으며, Codex는 일반 Codex를 뜻하므로 커스텀 CLI 표시는 노출하지 않아야 한다. OpenAI GPT, Gemini, Ollama 접근은 내부적으로 커스텀 Codex CLI를 자동 사용해야 한다.

## 변경 파일

- `src/model/struct/codex_runtime.py`
- `src/model/struct/ai_assistant.py`
- `src/app/page.system/view.ts`
- `src/app/page.system/view.pug`
- `devlog.md`
- `devlog/2026-05-13/163-codex-login-status-custom-cli-hide.md`

## 변경 내용

- Codex 로그인 상태 확인은 일반/system Codex CLI만 대상으로 삼도록 정리했다.
- 서비스 프로세스의 `PATH`가 터미널과 달라도 `/usr/local/bin/codex`와 표준 실행 경로를 찾도록 보강했다.
- `CODEX_HOME`이 비어 있고 로그인 파일이 있는 경우 `/root/.codex`를 기본 후보로 사용해 터미널 로그인 세션을 인식하도록 했다.
- 시스템 설정 AI 탭과 AI 실행 이벤트에서 `커스텀 CLI` 문구를 노출하지 않도록 정리했다.

## 확인

- `codex login status` 결과가 `Logged in using ChatGPT`임을 확인했다.
- PATH가 비어 있는 재현 환경에서도 번들 모델의 Codex 상태 계산이 `available=True`, `logged_in=True`로 나오는 것을 확인했다.
- `python -m py_compile src/model/struct/codex_runtime.py src/model/struct/ai_assistant.py bundle/src/model/struct/codex_runtime.py bundle/src/model/struct/ai_assistant.py` 통과.
- `wiz_project_build(projectName="main", clean=false)` 통과.
- `systemctl restart wiz.docker-infra.service` 후 서비스가 `active/running` 상태임을 확인했다.
- `GET /api/system/health` 200 확인.
- `python -m unittest tests.api.test_services_preflight` 통과: 11 tests OK.
- 인증이 필요한 `/wiz/api/page.system/ai_codex_status` 직접 호출은 세션 없이 401임을 확인했다.

## 남은 리스크

- 실제 브라우저 세션이 필요한 시스템 설정 화면의 인증 후 API 호출은 로컬 세션이 없어 직접 확인하지 못했다.
