# AI 설정 카드별 저장과 등록 노드 Ollama 스캔 UI 추가

## 사용자 요청

시스템 설정의 AI 탭에서 각 카드별로 따로 저장할 수 있도록 하고, Docker Infra에 등록된 서버 자원을 활용하는 설정은 실행 모드 대신 각 노드의 Ollama 설치 여부와 실행 상태를 스캔해서 선택할 수 있게 개선한다. 해당 설정에도 다른 AI 설정처럼 사용 체크박스를 제공한다.

## 변경 파일

- `src/app/page.system/api.py`
- `src/app/page.system/view.pug`
- `src/app/page.system/view.ts`
- `src/model/struct/ai_assistant.py`
- `src/model/struct/ai_settings.py`
- `src/model/struct/local_command_catalog.py`
- `src/model/struct/local_command_scripts.py`

## 변경 내용

- AI 설정 저장 API에 `save_ai_section`을 추가해 OpenAI, Gemini, Ollama, 등록 노드 실행 설정을 독립 저장할 수 있게 했다.
- AI 탭의 OpenAI, Gemini, Ollama 카드에 각각 저장 버튼을 추가하고, 기존 전체 저장 중심 UX를 제거했다.
- 등록 노드 실행 설정에 `enabled` 값을 추가하고, UI에서는 실행 모드 선택 대신 사용 체크박스, 대상 노드 선택, Ollama port, 노드 모델 Search Select만 노출했다.
- 등록 노드 스캔에서 CPU/GPU/드라이버 정보와 함께 Ollama 설치 여부, 프로세스/서비스 상태, `/api/tags` 응답, 설치 모델 목록을 수집하도록 했다.
- AI 사용 모델 선택 및 기본 모델 결정 로직에서 등록 노드 Ollama는 `runtime.enabled`가 켜진 경우에만 후보와 실행 대상으로 사용하도록 정리했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_settings.py src/model/struct/ai_assistant.py src/model/struct/local_command_scripts.py src/model/struct/local_command_catalog.py src/app/page.system/api.py`
- Ollama 스캔 스크립트를 로컬에서 직접 실행해 JSON 출력과 미설치/미응답 상태 처리를 확인했다.
- `wiz_project_build`로 WIZ/Angular 빌드를 통과했다.
- `systemctl restart wiz.docker-infra.service` 후 `curl -I http://127.0.0.1:3001/` 응답이 `200 OK`임을 확인했다.
