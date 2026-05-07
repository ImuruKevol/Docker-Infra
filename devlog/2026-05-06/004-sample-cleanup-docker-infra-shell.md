# 샘플 소스 및 devlog 정리 후 Docker Infra 앱 골격 구성

- **ID**: 004
- **날짜**: 2026-05-06
- **유형**: 소스 정리

## 사용자 원 요청

사용자가 `config.env`와 `domain.txt`에 연동 설정을 준비해두었으며, 값이 유출되지 않도록 조심하면서 TODO 순서대로 작업을 진행해 달라고 요청했다.

## 작업 요약

TODO의 P0 순서에 따라 샘플 게시판, 멤버, 마이페이지, 사용자 모델, post portal 패키지와 샘플 devlog를 제거했다. Docker Infra용 앱 골격으로 대시보드, 서버 관리, 서비스 관리, 도메인 관리, 이미지 관리, 템플릿 관리, 시스템 설정, 도구 다운로드 페이지를 추가했다.

연동 파일은 값 없이 키 존재만 확인했으며, secret 값은 출력하거나 저장하지 않았다.

## 변경 파일 목록

### 프로젝트 문서

- `README.md`: Docker Infra 프로젝트 설명으로 교체
- `devlog.md`: Docker Infra 작업 이력만 남기도록 정리
- `docs/angular-21-upgrade.md`: 샘플 업그레이드 문서 제거

### Source 앱

- `src/app/component.nav.sidebar/*`: Docker Infra 메뉴로 교체
- `src/app/page.access/*`: password-only 접속 화면 골격으로 교체
- `src/app/page.dashboard/*`: Docker Infra 대시보드 골격으로 교체
- `src/app/page.servers/*`: 서버 관리 페이지 골격 추가
- `src/app/page.services/*`: 서비스 관리 페이지 골격 추가
- `src/app/page.domains/*`: 도메인 관리 페이지 골격 추가
- `src/app/page.images/*`: 이미지 관리 페이지 골격 추가
- `src/app/page.templates/*`: 템플릿 관리 페이지 골격 추가
- `src/app/page.system/*`: 시스템 설정 페이지 골격 추가
- `src/app/page.tools/*`: 도구 다운로드 페이지 골격 추가

### Source route

- `src/route/openapi-json/*`: `/openapi.json` route 추가
- `src/route/swagger/*`: `/swagger` route 추가

### API 계약

- `docs/api/openapi.json`: 초기 OpenAPI 계약 추가

### 테스트

- `tests/api/test_openapi_contract.py`: OpenAPI 정적 계약 및 선택적 live API 계약 테스트 추가
- `tests/api/test_sample_cleanup.py`: 샘플 제거와 Docker Infra 페이지 골격 확인 테스트 추가
- `tests/fixtures/test_ids.py`: 테스트 run id와 namespace helper 추가
- `tests/cleanup/cleanup_registry.py`: 테스트 cleanup registry 추가
- `tests/e2e/README.md`: Playwright 테스트 원칙 기록

### 샘플 제거

- `src/app/page.posts*`: 샘플 게시판 페이지 제거
- `src/app/page.members`: 샘플 멤버 페이지 제거
- `src/app/page.mypage`: 샘플 마이페이지 제거
- `src/portal/post`: 샘플 post portal 패키지 제거
- `src/model/db/user.py`: 샘플 사용자 DB 모델 제거
- `src/model/struct/user.py`: 샘플 사용자 Struct 제거
- `src/controller/user.py`: 샘플 사용자 인증 controller 제거
- `src/controller/admin.py`: 샘플 admin controller 제거
- `devlog/2026-02-21`, `devlog/2026-04-27`, `devlog/2026-04-28`: 샘플 devlog 제거

### 리소스

- `src/assets/lang/ko.json`: Docker Infra 메뉴 번역으로 교체
- `src/assets/lang/en.json`: Docker Infra 메뉴 번역으로 교체

## 검증

- 민감 설정 파일 값이 출력되지 않도록 redacted key만 확인
- 샘플 source app, post portal, user model 제거 확인
- Docker Infra source app 골격 파일 존재 확인
- 샘플 README/devlog 문구 제거 확인
- JSON 파일 파싱 확인
- Python syntax compile 확인
- Pug compile 확인
- `python -m unittest discover tests/api` 실행: 5개 중 3개 통과, live API 2개는 서버 URL 미설정으로 skip
- `git diff --check` 통과 확인
- 테스트 중 생성된 `__pycache__`와 `/tmp/di-*.html` 산출물 삭제
- WIZ MCP build는 현재 환경에 `wiz` CLI가 없어 실행 불가
