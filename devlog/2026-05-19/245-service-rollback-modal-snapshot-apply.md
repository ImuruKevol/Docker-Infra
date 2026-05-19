# 서비스 버전 되돌리기 모달과 스냅샷 우선 적용 개선

## 원 요청

- 리뷰 ID: `xbsdahebrlxafrnganhugpifavkwmcto`
- 요청: 서비스 상세 버전 되돌리기 모달에서 footer 버튼 텍스트 줄바꿈을 수정하고, 버튼 왼쪽 안내 문구와 단순 되돌리기 버튼을 제거한다. 되돌리기는 기본적으로 적용까지 진행해야 한다. 스냅샷이 있는 버전은 현재 Compose와 동일하더라도 스냅샷 이미지 기준으로 되돌려야 한다.

## 변경 내용

- `src/app/page.services/view.pug`
  - 롤백 모달 footer 안내 문구를 제거했다.
  - 단순 `되돌리기` 버튼을 제거하고 `되돌리고 적용` 단일 primary 버튼으로 정리했다.
  - primary 버튼에 최소 폭과 `whitespace-nowrap`를 적용해 텍스트가 줄바꿈되지 않도록 했다.
- `src/app/page.services/view.ts`
  - `runRollback()` 기본 동작을 적용까지 진행하도록 변경했다.
  - 이미지 롤백 요약에서 스냅샷 백업 개수를 우선 표시하도록 했다.
- `src/model/struct/services_rollback.py`
  - 롤백 대상 버전에 연결된 이미지 백업을 고를 때 성공한 `container_snapshot`을 최우선으로 선택하도록 정렬했다.
  - 롤백 계획의 `same_content`와 이미지 변경 목록을 스냅샷/이미지 백업 참조가 반영된 최종 Compose 기준으로 계산하도록 변경했다.
  - 백업 시스템 실행 상태와 별개로 이미 저장된 백업 참조가 있으면 롤백 적용 대상에 포함하도록 했다.
- `tests/api/test_services_preflight.py`
  - 롤백 모달 footer 계약을 새 UX에 맞게 갱신했다.
  - 스냅샷 우선 롤백 계획 코드 경로를 정적 계약으로 확인하도록 보강했다.

## 검증

- 성공: `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/services_rollback.py src/app/page.services/api.py`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight`
- 성공: `wiz_project_build(projectName="main", clean=false)`
- 성공: devmode 쿠키(`season-wiz-project=main`, `season-wiz-devmode=true`)를 붙여 `https://infra-dev.nanoha.kr/services` 응답 확인, `200 text/html`

## 남은 리스크

- 실제 `wiki_service` 버전 18 롤백 적용은 운영 데이터와 백업 저장소를 변경할 수 있어 실행하지 않았다.
- 현재 작업 전부터 같은 프로젝트에 다른 미커밋 변경과 devlog가 남아 있었으며, 이번 변경은 해당 파일들을 되돌리지 않고 필요한 부분만 반영했다.
