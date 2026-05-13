# 157. bbb Jitsi 서비스 직접 복구와 AI 런타임 compose 계약 보강

- 날짜: 2026-05-13
- 요청: 현재 bbb 이름으로 떠있는 서비스를 직접 정상동작하도록 수정하고, 수정한 부분을 바탕으로 현재 AI 로직을 업데이트

## 변경 파일

- `.runtime/dev/templates/bbb_3d4e4f/docker-compose.yaml`
- `src/model/struct/ai_assistant.py`
- `tests/api/test_services_preflight.py`
- `/etc/nginx/sites-available/docker-infra-bbb.nanoha.kr.conf`

## 작업 내용

- bbb Jitsi stack에서 `_FILE` 기반 Docker secret 환경변수를 제거하고, Jitsi 이미지가 실제로 읽는 직접 환경변수 방식으로 교정했다.
- `prosody`, `jicofo` healthcheck가 이미지에 없거나 검증되지 않은 명령에 의존해 Swarm update rollback을 유발하던 구성을 보수적으로 수정했다.
- bbb 도메인 nginx upstream이 HTTPS 컨테이너 포트를 HTTP로 프록시하던 설정을 공개 HTTP 포트로 바로잡고 nginx를 reload했다.
- AI 서비스 생성/수정 검증 단계에서 `*_FILE`, top-level Docker secrets, 빈 secret-like env, Jitsi 이미지의 취약한 healthcheck를 런타임 계약 위반으로 잡도록 보강했다.
- AI prompt에 stack-local credential, 검증된 healthcheck 명령, rollback 후 healthcheck 확인 지침을 추가했다.

## 확인

- `docker service ls`에서 `bbb_3d4e4f_web`, `prosody`, `jicofo`, `jvb`가 모두 `1/1` 상태임을 확인했다.
- `https://bbb.nanoha.kr/test-room-codex`가 HTTP 200을 반환했고, Playwright로 Jitsi 회의 진입 화면이 렌더링됨을 확인했다.
- Jicofo 로그에서 Prosody 연결, JVB brewery join, videobridge 등록 로그를 확인했다.
- `/opt/conda/envs/docker-infra/bin/python -m py_compile project/main/src/model/struct/ai_assistant.py project/main/tests/api/test_services_preflight.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest project/main/tests/api/test_services_preflight.py`
- WIZ `main` 프로젝트 빌드 성공.

## 남은 리스크

- bbb compose의 내부 인증값은 현재 서비스 복구를 위해 stack-local 값으로 고정되어 있다. 운영 보안 기준에서는 추후 서비스별 secret rotation 기능을 별도 설계하는 것이 좋다.
- Jitsi 회의 화면 로딩과 백엔드 연결은 확인했지만, 실제 카메라/마이크 권한을 통한 양방향 미디어 품질까지 장시간 검증하지는 않았다.
