# 서비스 상세 상단 서버 버튼 배치와 요약 카드 제거

- 날짜: 2026-05-19
- ID: 256
- 리뷰 ID: widvtkqcznlhrydxkmjmhvvzehukysny

## 사용자 요청

서비스가 어떤 서버에서 실행 중인지 보여주는 버튼만 헤더 영역으로 옮기고, 서비스 상세의 `실행 기준`, `접속 주소`, `서버 / 인증서`, `구성요소` 정보 카드 4개를 삭제해달라는 요청.

## 변경 파일

- `src/app/page.services/view.pug`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-19/256-service-detail-header-server-button.md`

## 작업 내용

- 실행 서버 상세 이동 버튼을 서비스 상세 헤더 액션 영역으로 이동.
- `실행 기준`, `접속 주소`, `서버 / 인증서`, `구성요소`로 구성된 4분할 요약 카드 영역 삭제.
- 정적 계약 테스트를 새 레이아웃 기준으로 갱신.

## 검증

- `PYTHONDONTWRITEBYTECODE=1 /opt/conda/envs/docker-infra/bin/python -m unittest project/main/tests/api/test_services_preflight.py`
- `wiz_project_build(projectName="main", clean=false)`
- `curl -I` with `season-wiz-project=main` and `season-wiz-devmode=true` cookies against `https://infra-dev.nanoha.kr/services`

결과: 모두 성공.
