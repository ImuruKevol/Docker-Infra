# 시스템 설정 탭 구조와 AI 설정/모델 조회/자원 확인 추가

## 사용자 요청

이 서비스에 AI 생성 기능을 추가해야해. 일단 시스템 설정을 탭 형식으로 수정하고, AI 설정 탭을 추가해줘.
GPT, Gemini를 API 형식으로 사용할 수 있도록 사용할 수 있는 모델 목록을 공식 홈페이지같은곳들에서 불러와서 리스팅하고, API Token을 저장할 수 있어야 해. 물론 더이상 지원하지 않는 모델 API는 경고나 에러 메세지를 표시할 수 있으면 좋은데, 가능할지는 모르겠어.
그리고 ollama IP, Port를 입력해서 외부 GPU, 모델을 불러와서 사용할 수도 있어야 해.
그리고 현재 이 Docker Infra가 설치된 서버의 자원(CPU/GPU)으로 AI 모델을 로드해서 사용할 수도 있어야 해. 이 Docker Infra에 등록된 다른 일반 노드의 자원으로도 로드해서 돌릴 수 있는 기능이 있으면 좋을 것 같은데, 이건 가능할지 모르겠어. GPU의 경우엔 드라이버(radeon, nvidia)가 설치되었는지도 보여줘야 해.

## 변경 사항

- 시스템 설정 화면을 General, Backup, AI 탭 구조로 변경했다.
- AI 설정 탭에 OpenAI GPT, Google Gemini, Ollama endpoint, AI 실행 대상 설정 섹션을 추가했다.
- OpenAI/Gemini API Token은 기존 `system_settings` 암호화 저장 구조를 재사용해 저장하도록 했다.
- OpenAI `/v1/models`, Gemini `models` API, Ollama `/api/tags`를 통해 모델 목록을 갱신하고 캐시하도록 했다.
- 선택 모델이 현재 모델 목록에 없거나 `generateContent` 미지원, preview/experimental/deprecated 상태인 경우 경고/오류 메시지를 표시하도록 했다.
- 로컬 서버와 등록 노드의 AI 실행 자원 조회를 추가하고 CPU core, 메모리, GPU, NVIDIA/Radeon 드라이버 상태를 표시하도록 했다.

## 변경 파일

- `src/app/page.system/api.py`
- `src/app/page.system/view.pug`
- `src/app/page.system/view.ts`
- `src/model/struct.py`
- `src/model/struct/ai_settings.py`
- `src/model/struct/local_command_catalog.py`
- `src/model/struct/local_command_scripts.py`
- `devlog.md`
- `devlog/2026-05-10/109-system-ai-settings.md`

## 공식 API 확인

- OpenAI model list: `https://developers.openai.com/api/reference/resources/models/methods/list`
- OpenAI deprecations: `https://developers.openai.com/api/docs/deprecations`
- Gemini model list: `https://ai.google.dev/api/models`
- Ollama tag list: `https://docs.ollama.com/api/tags`

## 검증

- `python -m py_compile project/main/src/model/struct/ai_settings.py project/main/src/model/struct/local_command_scripts.py project/main/src/model/struct/local_command_catalog.py project/main/src/app/page.system/api.py`
- `AI_RESOURCE_SCRIPT` 로컬 실행 확인: CPU/memory/runtime payload와 Intel GPU vendor 분류 확인
- `wiz_project_build(projectName="main", clean=false)` 성공
