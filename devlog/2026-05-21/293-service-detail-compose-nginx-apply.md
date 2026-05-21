# 서비스 상세 Compose 원문 재적용과 nginx 설정 미리보기 보강

- **ID**: 293
- **날짜**: 2026-05-21
- **유형**: 기능 추가

## 작업 요약

서비스 상세 화면의 Compose/Nginx 탭에서 Compose 원문이 선택된 경우 바로 다시 적용할 수 있는 버튼을 추가했다.
템플릿 기반 서비스처럼 nginx 파일이 아직 생성되지 않은 서비스도 도메인과 공개 포트 설정을 기준으로 nginx 원문 미리보기를 표시하도록 보강했다.

## 원문 요청사항

```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

작업 진행해줘.

## 리뷰 요약

- 리뷰 ID: mlmvfhzjkgkstxxnmwfewflidojpggod
- 제목: 서비스 상세 기능 개선
- 요청 링크: https://infra-dev.nanoha.kr/services
- Codex 요청자: 권태욱
- 프로젝트 루트: /root/docker-infra
- Codex 세션 ID: 신규
- 스크린샷 컨텍스트: 없음
- 에이전트 작업 지시서 컨텍스트: 포함됨
- HTML 문서 생성 규칙 컨텍스트: 없음
- HTML 문서 설정 컨텍스트: 없음
- HTML 프로젝트 인스트럭션 파일: 없음
- 첨부파일 컨텍스트: 0개

## 에이전트 작업 지시서

# 에이전트 작업 지시서

## 리뷰 정보

- 리뷰 ID: mlmvfhzjkgkstxxnmwfewflidojpggod
- 제목: 서비스 상세 기능 개선
- 상태: open
- 우선순위: high
- 분류: ux
- 프로젝트: Docker Infra DEV
- 프로젝트 종류: web_service
- 요청 링크: https://infra-dev.nanoha.kr/services
- 화면: 1440x900
- 캡처 방식: reviewops-sdk-dom-snapshot
- 스크린샷 첨부: yes
- 리뷰 첨부 파일: 0개

## 리뷰어 요청 내용

서비스 상세 화면에서 Compose/Nginx 탭에 개선이 필요함.
일단 헤더 부분에 있던 서비스 다시 적용 버튼이 삭제됨에 따라 이 Compose/Nginx 탭에서 Compose 원문이 활성화가 되어있을 때 적용 버튼을 눌러서 docker compose up을 다시 할 수 있어야 함.
그리고 템플릿으로 서비스 생성 시 Nginx 설정이 없음. 서비스 생성 시 설정하는 공개 포트 등 설정에 따라 설정을 자동으로 적용 해야 함.
```

## 변경 파일 목록

- `src/app/page.services/view.pug`
  - Compose/Nginx 탭 헤더에 Compose 원문 선택 시 표시되는 `다시 적용` 버튼을 추가했다.
- `src/app/page.services/view.ts`
  - Compose 원문 저장 로직을 재사용 가능한 helper로 분리했다.
  - 원문이 수정된 상태에서 다시 적용하면 저장 검사를 먼저 수행한 뒤 배포를 시작하도록 했다.
  - nginx 설정이 실제 파일이 아닌 미리보기일 때의 설명 문구를 추가했다.
- `src/model/struct/service_nginx.py`
  - 서비스 도메인 row로 nginx server block 원문을 렌더링하는 `render_preview`를 추가했다.
- `src/model/struct/services_runtime.py`
  - Compose 파일의 published port를 읽어 nginx 미리보기 metadata에 반영했다.
  - nginx 설정 파일이 아직 없어도 도메인 row가 있으면 설정 원문 미리보기를 반환하도록 했다.
- `tests/api/test_services_preflight.py`
  - Compose/Nginx 탭 재적용 버튼과 nginx 미리보기 계약을 정적 테스트에 추가했다.
- `devlog.md`
- `devlog/2026-05-21/293-service-detail-compose-nginx-apply.md`

## 검증 결과

- `python -m py_compile src/model/struct/service_nginx.py src/model/struct/services_runtime.py` 성공
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest` 성공
- `wiz_project_build(projectName="main", clean=false)` 성공
- `git diff --check` 성공
- `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키로 `https://infra-dev.nanoha.kr/services` HEAD 요청 200 확인
- 같은 쿠키로 `https://infra-dev.nanoha.kr/wiz/api/page.services/detail_service_advanced` POST 요청 시 로그인 세션 부재로 WIZ 응답 `401 AUTHENTICATION_REQUIRED` 확인

## 남은 리스크

- 로그인 세션이 없어 실제 인증 후 브라우저에서 템플릿 생성 서비스의 nginx 미리보기와 재적용 버튼 동작은 직접 클릭 검증하지 못했다.
- 재적용은 기존 서비스 배포 백그라운드 경로를 사용하므로 운영 Docker/nginx 상태 변경은 테스트 환경에서 직접 실행하지 않았다.
