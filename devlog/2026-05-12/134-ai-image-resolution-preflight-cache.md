# 134. AI 이미지 태그 자동 보정과 서비스 생성 preflight 중복 호출 방지

## 요청

- 원 요청: "ollama로 생성 요청 시에 자꾸 이미지 버전 관련 에러가 뜨고 있어. 그를 위해서 간단한 mcp를 붙여야 할 것 같아. 타겟이 되는 이미지를 선택한 후에는 터미널에서 docker search 명령어를 실행해서 이미지 버전을 선택하도록 해야해. 그리고 4단계로 넘어갈 때 점검을 쭉 한번 돌리는데, 저장 후 배포 버튼을 누르면 다시 점검을 돌려서 같은 로직이 중복으로 돌아가는 버그가 있어."
- 리뷰 ID: `lvzxjnujqysqobymwcncwklhsvxssxoq`

## 변경 파일

- `src/model/struct/services_wizard.py`
- `src/model/struct/ai_assistant.py`
- `src/app/page.services.create/view.ts`
- `devlog.md`
- `devlog/2026-05-12/134-ai-image-resolution-preflight-cache.md`

## 원인

- AI가 생성한 이미지 태그가 Docker Hub에 없으면 이전 이미지 검증 보강 로직이 곧바로 실패시켜 Ollama 생성 결과가 반복적으로 이미지 버전 오류에 걸릴 수 있었다.
- 서비스 생성 화면은 4단계 진입 시 preflight를 실행하고, 저장/배포 버튼에서도 같은 payload로 `preflight` API를 다시 호출했다.

## 작업 내용

- `services_wizard`에 `docker search --format '{{json .}}'` 기반 이미지 후보 탐색 헬퍼를 추가했다.
- 이미지 후보가 정해진 뒤 Docker Hub tag 목록과 manifest 확인으로 사용 가능한 태그를 선택해 invalid tag를 자동 보정하도록 했다.
- AI output 검증 전에 컴포넌트 이미지 태그를 보정하고, 보정 실패 시 repair context에 docker search 후보를 전달해 다음 AI 재요청이 후보 중 하나를 선택하게 했다.
- 서비스 생성 화면에 preflight payload signature 캐시를 추가해 4단계에서 이미 점검한 동일 payload는 저장/배포 클릭 시 `preflight` API를 재호출하지 않게 했다.

## 확인

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/services_wizard.py src/model/struct/ai_assistant.py` 성공
- `docker search --limit 1 --format '{{json .}}' nginx` 성공
- `git diff --check` 성공
- WIZ `wiz_project_build(projectName="main", clean=false)` 성공

## 남은 리스크

- Docker search는 repository 검색만 제공하므로 실제 태그 선택은 Docker Hub tag/manifest 확인을 함께 사용한다.
- private registry 또는 Docker Hub 외부 registry 이미지는 기존 정책대로 배포 시 pull 결과 확인 대상으로 남는다.
- 저장 API 내부의 최종 server-side preflight는 안전장치로 유지되므로, 화면의 중복 API 호출은 줄였지만 저장 시 서버 검증 자체는 계속 수행된다.
