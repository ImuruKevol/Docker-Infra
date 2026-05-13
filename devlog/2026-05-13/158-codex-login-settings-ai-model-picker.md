# 158. Codex 로그인 실행 설정과 AI 점검 모델 선택 추가

## 사용자 요청

작업을 진행해줘. 진행할 때 내가 이미 codex cli에 로그인은 해놨는데 codex 커스텀에다가는 아직 로그인은 안해놨어. 둘이 세션을 공유를 하는지는 모르겠네. 일단 커스텀하지 않은 codex를 이용해서 붙이면 돼. 로그인도 해놨으니 그냥 바로 명령을 테스트해보는 등 실제로 codex를 이용해서 AI에 명령을 던지고 결과를 확인해도 돼.

## 변경 내용

- 시스템 설정의 AI 탭에 Codex 로그인 실행 섹션을 추가했다.
- Codex 로그인 상태, 일반/커스텀 CLI 경로, 버전, 실제 실행 테스트 결과를 확인할 수 있게 했다.
- Codex 로그인 모드에서 일반 `codex` CLI의 로그인 세션을 사용해 `gpt-5.5`와 `xhigh` reasoning 설정으로 실행할 수 있게 했다.
- 서비스 AI 수정/백그라운드 검사 모달에서 사용할 모델을 선택할 수 있게 했다.
- AI 모델 후보와 기본 선택에 Codex 로그인 모델을 포함했다.

## 변경 파일

- `src/model/struct/codex_runtime.py`
- `src/model/struct/ai_settings.py`
- `src/model/struct/ai_assistant.py`
- `src/app/page.system/api.py`
- `src/app/page.system/view.ts`
- `src/app/page.system/view.pug`
- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `devlog.md`
- `devlog/2026-05-13/158-codex-login-settings-ai-model-picker.md`

## 확인 결과

- `codex exec --json --ephemeral --skip-git-repo-check --sandbox read-only -m gpt-5.5 -c model_reasoning_effort="xhigh"`로 로그인 세션 응답을 확인했다.
- `codex exec --json --ephemeral --skip-git-repo-check --ignore-user-config --sandbox read-only -m gpt-5.5 -c model_reasoning_effort="xhigh"`로 앱 래퍼와 같은 로그인 auth 경로를 확인했다.
- `/opt/conda/envs/docker-infra/bin/python -m py_compile`로 변경 Python 파일 문법 검사를 통과했다.
- `wiz_project_build(projectName=main, clean=false)` 빌드에 성공했다.
