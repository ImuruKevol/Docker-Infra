# 252 서비스 상세 헤더 버튼 정리와 스냅샷 백업 위치 이동

## 요청

현재 서비스 상세 헤더 부분에 버튼이 많음. 그 중에 다시 적용 버튼은 그냥 제거할 것. 그리고 스냅샷 백업 버튼은 버전 이력 탭으로 이동.

## 변경 내용

- 서비스 상세 헤더에서 `다시 적용` 버튼을 제거했다.
- 서비스 상세 헤더에서 `스냅샷 백업` 버튼을 제거하고, 버전 이력 탭 헤더로 이동했다.
- 버전 이력 탭의 백업 상태 배지 옆에 스냅샷 백업 버튼을 배치해 백업/롤백 작업 흐름과 위치를 맞췄다.
- 정적 UI 계약 테스트에 헤더 액션 정리와 스냅샷 백업 버튼 위치를 검증하는 조건을 추가했다.

## 변경 파일

- `src/app/page.services/view.pug`
- `tests/api/test_services_preflight.py`
- `devlog.md`
- `devlog/2026-05-19/252-service-header-actions-cleanup.md`

## 검증

- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight` 통과
- WIZ `main` 프로젝트 빌드 통과

## 남은 리스크

- 브라우저 실화면 검증은 별도로 수행하지 않았다.
- 작업 전부터 같은 프로젝트에 다른 미커밋 변경과 미추적 devlog가 있었으며, 이번 작업은 필요한 파일만 수정하고 기존 변경은 되돌리지 않았다.
