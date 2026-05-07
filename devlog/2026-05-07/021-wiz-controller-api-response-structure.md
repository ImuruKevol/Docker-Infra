# 021. WIZ controller/API 응답 패턴과 Struct 경계 리팩토링

- 날짜: 2026-05-07
- 요청: "각 페이지, 컴포넌트들에 api.py를 보면 wiz.response가 try ~ except 안에 들어가있는 문제도 너무 많고, 아직 wiz 프로젝트 구조를 따르지 않는 부분이 많아. base controller에서도 session cookie name, secure 등 설정은 base controller가 아니라 config/boot.py에 있는 before_request, after_request, bootstrap에다가 정의해야해. 이 부분의 상세한 사용법은 season 패키지의 lib/binding/http.py와 lib/server.py를 참고해줘. base controller의 enforce_access도 거기에 있을게 아니라 access 페이지에서 처리하면 돼. 어차피 다른 페이지들은 로그인이 되어있어야 사용가능하고, 로그인이 되어있지 않으면 access 페이지로 이동되기 때문에 access 페이지에서 처리하는게 훨씬 효율적이야. 이 이외에도 wiz project 구조에 맞지 않는 부분들을 싹다 전수조사해서 수정해줘."

## 변경 파일

- `/root/docker-infra/config/boot.py`: session cookie 정책을 `bootstrap`, `before_request`, `after_request` lifecycle로 이동.
- `src/controller/base.py`, `src/controller/user.py`: base controller의 access guard 제거, 인증 guard를 user controller 경계로 정리.
- `src/app/page.access/api.py`, `src/app/page.access/view.ts`, `src/app/page.servers/api.py`, `src/app/page.system/api.py`: app API의 `wiz.response` 호출을 `try/except` 바깥으로 이동하고 access 페이지에서 인증 사용자를 dashboard로 보냄.
- `src/route/api-*/controller.py`: REST route controller 응답 패턴 정리, 보호 API controller를 `user`로 변경.
- `src/model/struct/*.py`: 300줄 초과 Struct를 `jobs_*`, `nodes_*`, `compose_rules`, `local_command_catalog`, `setup_environment` 하위 Struct로 분리.
- `docs/api/openapi.json`, `docs/docker-infra-runtime.md`, `README.md`: 쿠키 정책 위치와 인증/응답 구조 문서 및 OpenAPI 계약 갱신.
- `tests/api/*.py`: WIZ 구조 계약, controller 경계, OpenAPI/schema 기대값 갱신.

## 검증

- Python compile check: 통과.
- WIZ model loader simulation: 통과.
- `wiz.response` try/except 정적 검사: 통과.
- 정적 unittest 17개: 통과.
- WIZ build (`wiz_project_build`, clean=false): 통과.
- `git -C project/main diff --check`: 통과.

## 비고

- Live API/E2E 테스트는 요청대로 별도 리팩터링 이후 단계로 남김.
