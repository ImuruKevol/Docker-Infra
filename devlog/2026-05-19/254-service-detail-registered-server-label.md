# 서비스 상세 서버 표시를 Docker Infra 등록 정보 기준으로 보정

- 날짜: 2026-05-19
- ID: 254
- 리뷰 ID: widvtkqcznlhrydxkmjmhvvzehukysny

## 사용자 요청

서비스 상세의 "서버 / 인증서" 영역에 wiki_service 기준으로 실제 서버 hostname인 `ktw-test`가 표시되는데, Docker Infra에 등록된 서버 정보를 표시하도록 수정 요청.

## 변경 파일

- `src/app/page.services/view.ts`
- `src/model/struct/services_status.py`
- `src/model/struct/services_runtime.py`
- `src/model/struct/services_deploy_targets.py`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-19/254-service-detail-registered-server-label.md`

## 작업 내용

- 서비스 상세 서버 요약이 컨테이너/도메인/스택 작업의 Docker Infra 등록 서버 라벨을 우선 사용하도록 수정.
- 배포 후 도메인 proxy metadata에 실제 Swarm hostname과 등록 서버 표시명을 분리 저장하도록 보강.
- 저장된 runtime status를 상세 조회 시 등록 서버 ID/name/host 기준으로 보정하도록 추가.
- 정적 계약 테스트에 등록 서버 라벨 경로를 추가.

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m py_compile project/main/src/model/struct/services_status.py project/main/src/model/struct/services_runtime.py project/main/src/model/struct/services_deploy_targets.py`
- `/opt/conda/envs/docker-infra/bin/python -m unittest project/main/tests/api/test_services_preflight.py`
- `wiz_project_build(projectName="main", clean=false)`
- `curl -I` with `season-wiz-project=main` and `season-wiz-devmode=true` cookies against `https://infra-dev.nanoha.kr/services`

결과: 모두 성공.
