# 058. nginx 고정 운영 기준 적용, 도메인 인증서 업로드와 서비스 흐름 단순화

## 사용자 요청

웹서버는 Nginx/Apache2 선택이 아니라 nginx로 고정하고, nginx 설정 파일 경로·데몬 이름·사이트 설정 디렉토리는 Ubuntu 24.04 기본값으로 고정한다. SSL 인증서는 시스템 설정이 아니라 도메인 관리에서 업로드하고 유효 기간을 확인하게 하며, 인증서가 없는 도메인은 서비스 관리에서 certbot 무료 인증서 발급 흐름으로 이어지게 한다. Harbor는 일반 이미지 빌드/푸시가 아니라 Docker Infra로 운영 중인 Docker Compose 서비스의 이미지 백업 및 버전 관리용으로만 사용하도록 분석·반영한다.

## 변경 파일

- `src/model/struct/webserver.py`: Apache2 감지와 편집 설정을 제거하고 Ubuntu 24.04 기본 nginx 경로를 고정했다. 도메인별 SSL 인증서 업로드 파일을 `data/domain-certificates/` 아래에 저장하고 OpenSSL로 만료일, SAN, key 존재 여부를 분석하도록 정리했다.
- `src/model/struct/setup.py`, `src/model/struct/setup_environment.py`, `src/model/struct/local_command_catalog.py`: 설치/점검의 proxy 기준을 nginx로 고정하고 Apache2 command 노출을 제거했다.
- `src/model/struct/domains.py`, `src/app/page.domains/api.py`, `src/app/page.domains/view.ts`, `src/app/page.domains/view.pug`, `src/route/api-domain-certificates/`: 도메인 상세에서 SSL 인증서 업로드, 삭제, 상태 확인을 제공하는 route/API/UI를 추가했다.
- `src/app/page.system/api.py`, `src/app/page.system/view.ts`, `src/app/page.system/view.pug`: 시스템 설정에서 웹서버/SSL 경로 편집 화면과 API를 제거하고 일반 설정과 Harbor 백업 저장소 설정만 남겼다.
- `src/app/page.services/view.ts`, `src/app/page.services/view.pug`, `src/model/struct/services.py`: 서비스 생성 화면에서 proxy 선택을 제거하고 Nginx 자동 연결로 고정했다. SSL 선택지는 도메인 업로드 인증서 사용, certbot 발급 예정, 나중에 설정으로 정리했다.
- `src/app/page.access/view.ts`, `src/app/page.access/view.pug`, `src/app/page.tools/api.py`, `src/app/page.tools/view.ts`: 설치 마법사와 운영 도구의 Apache2 노출을 제거하고 nginx 기준 안내와 점검만 남겼다.
- `src/model/struct/integrations.py`, `src/model/struct/integrations_registry.py`: Harbor 설정 명칭을 백업 저장소 역할에 맞게 조정했다.
- `docs/docker-infra-design.md`, `docs/docker-infra-runtime.md`, `docs/docker-infra-development-todo.md`: nginx 고정, 도메인 SSL 업로드, Harbor 백업 저장소 역할을 문서와 TODO에 반영했다.

## 검증

- `python -m py_compile`로 변경된 Python API/model/route 파일의 문법을 확인했다.
- `wiz_project_build(clean=true)`는 신규 route 반영을 위해 시도했으나 120초 tool timeout으로 결과 수신에 실패했다.
- 이어서 `wiz_project_build(clean=false)`를 실행해 Angular/WIZ 빌드 성공을 확인했다.
- `git diff --check`로 whitespace 오류가 없음을 확인했다.
