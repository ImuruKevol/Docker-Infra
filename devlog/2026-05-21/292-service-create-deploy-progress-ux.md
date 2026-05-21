# 292. 서비스 생성 배포 진행 상태 UX 개선

## 사용자 원 요청

- 리뷰 ID: zrkllbdxnhofczososixprqzoubagepj
- 제목: 서비스 생성 중 UX 개선
- 요청: 서비스 생성 시 이미지 크기가 커서 pull에 시간이 걸려 컨테이너 목록이 늦게 뜨는 경우, docker ps로도 확인되지 않는 백그라운드 진행 상태를 서비스 상세에 표시해야 함.

## 변경 내용

- 서비스 상세 overview API가 최근 operation 요약을 항상 포함하도록 변경해 생성 직후 백그라운드 배포 작업 배너가 표시되도록 했다.
- 배포 대기 루프에서 Docker stack task 상태를 주기적으로 수집하고 operation message/output metadata에 기록하도록 보강했다.
- 기본 runtime ready 대기 시간을 600초로 늘려 큰 이미지 pull 중에 조기 실패하지 않도록 했다.
- 서비스 상세 화면에 active background operation 자동 overview polling을 추가하고 Docker 작업/컨테이너 수, task 상태, 오류 메시지를 표시했다.
- 컨테이너 목록이 비어 있을 때 active deploy 중이면 이미지 pull 또는 Docker task 처리 중임을 안내하도록 문구를 분기했다.
- 서비스 생성 완료 안내 문구에 Docker 작업과 이미지 pull 대기 상태 확인 가능성을 명시했다.
- 관련 정적 계약 테스트를 보강했다.

## 변경 파일

- `src/model/struct/services_deploy.py`
- `src/app/page.services/api.py`
- `src/app/page.services/view.ts`
- `src/app/page.services/view.pug`
- `src/app/page.services.create/view.ts`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-21/292-service-create-deploy-progress-ux.md`

## 검증 결과

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_services_preflight.py` 통과
- `wiz_project_build(projectName="main", clean=false)` 통과
- `curl -I`에 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 넣어 `https://infra-dev.nanoha.kr/services` 200 응답 확인
