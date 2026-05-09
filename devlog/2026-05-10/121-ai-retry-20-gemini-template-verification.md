# 121. AI 재시도 20회 확대와 Gemini 템플릿 수정 실검증

- 날짜: 2026-05-10
- 요청: AI output 검증 실패가 계속 발생하므로 오류 시 리트라이를 최대 20회까지 늘리고, 등록된 Gemini 3.1 Flash Lite 모델로 `gitlab-runner-stack` 템플릿에 지정 프롬프트를 테스트해 실제 적용 여부를 Playwright로 검증.

## 변경 파일

- `src/model/struct/ai_assistant.py`
- `devlog.md`
- `devlog/2026-05-10/121-ai-retry-20-gemini-template-verification.md`

## 변경 내용

- AI output 검증 실패 재시도 횟수를 20회로 확대했다.
- 템플릿 output 계약에서 `files.docker-compose.yaml`도 바깥 JSON의 object로 반환할 수 있도록 정의했다. 앱은 object를 Docker Compose YAML 텍스트로 직렬화한 뒤 기존 Docker Infra 검증 경로를 통과시킨다.
- YAML 파싱 실패 보정 요청에서 `docker-compose.yaml`과 `values.default.yaml` 모두 object field로 재작성하도록 지시를 강화했다.
- 보정 진단 정보에서 object 형태 파일도 YAML로 직렬화한 줄번호 스니펫으로 전달하도록 정리했다.
- 사용자가 최신 버전을 요청했지만 현재 정확한 버전 정보가 context에 없을 때, stale한 고정 버전을 지어내지 말고 명시적으로 요청된 이미지에 한해 `latest` 태그와 한국어 경고를 사용하도록 지시를 추가했다.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/ai_assistant.py src/app/page.templates/api.py src/app/page.services/api.py src/app/page.services.create/api.py`
- WIZ `wiz_project_build(projectName="main", clean=false)` 성공
- `wiz.docker-infra.service` 재시작 후 `ai_contract`에서 `docker-compose.yaml`, `values.default.yaml`의 preferred type이 `object`로 노출되는지 확인
- Playwright로 로그인 후 등록된 `gemini::gemini-3.1-flash-lite` 모델을 사용해 `gitlab-runner-stack` 템플릿에 다음 요청을 실행했다.
  - 버전을 최신버전으로 바꾸고 도메인은 git.imurukevol.com을 쓸거야.
  - 그리고 설명과 readme는 한글로 수정해줘
- Playwright 검증 결과:
  - AI 스트림 완료 및 Docker Infra preview validation 통과
  - 렌더링된 Compose와 values에 `git.imurukevol.com` 반영
  - 설명과 README 한글 포함
  - `container_name`, `hostname` 미사용
  - `docker_infra_overlay` 네트워크 유지
  - 기존 `16.11.0` 및 중간 검증에서 생성된 stale `17.11.1` 이미지 버전 제거
  - 최신 요청은 `gitlab/gitlab-ce:latest`, `gitlab/gitlab-runner:latest`와 floating tag 고정 권장 경고로 처리
  - `save_template` 성공 및 저장 후 detail preview에서 도메인/README 반영 확인
