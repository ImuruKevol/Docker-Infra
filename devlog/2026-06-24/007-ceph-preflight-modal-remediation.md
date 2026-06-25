# Ceph preflight 결과 모달과 보정 안내 추가

- **ID**: 007
- **날짜**: 2026-06-24
- **유형**: Storage/Ceph UX 보강

## 작업 요약
Ceph 사전 점검 버튼을 누르면 즉시 모달이 열리도록 바꾸고, 모달 안에서 결과 요약과 operation output 기반 중간 과정을 확인할 수 있게 했다.
warning/error 항목은 공통 조건, node별 조건, 독립 서버 제외 항목을 합쳐 보여주며 각 항목마다 발생 이유와 보정 방법을 표시한다.
안전하게 자동 연결할 수 있는 항목은 서버 관리/Swarm 등록 화면으로 이동하는 보정 버튼을 제공하고, host package 설치나 disk 정리처럼 위험한 변경은 자동 적용하지 않도록 명시했다.

## 원문 요청사항
```text
- 사전 점검 버튼은 누르면 모달 형태로 결과 및 중간 과정이 떠야해.
- warning, error이 떴으면 각 요소별로 왜 떴는지, 어떻게 보정이 가능한지 안내할 수 있어야 해. 가능하면 자동으로 적용할 수 있으면 좋고.

리뷰 ID: ybptdjndmjlcgkhwmdxfulwtxfuviqrz
제목: Ceph preflight와 cluster bootstrap PoC 구현
```

## 변경 파일 목록

### Source App
- `src/app/page.storage/view.ts`: preflight 모달 상태, warning/error issue 집계, 자동 보정 액션 처리 helper 추가.
- `src/app/page.storage/view.pug`: preflight 결과/중간 과정/보정 안내 모달 추가.

### Model
- `src/model/struct/storage_ceph_preflight.py`: check별 `reason`, `remediation`, `auto_fix` metadata 추가.

### Tests / Devlog
- `tests/api/test_storage_models.py`: preflight 모달과 보정 안내 계약 static test 추가.
- `devlog.md`: 작업 요약 행 추가.
- `devlog/2026-06-24/005-ceph-preflight-modal-remediation.md`: 상세 devlog 추가.

## 확인 결과
- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/storage_ceph_preflight.py src/model/struct/storage_ceph_cluster.py src/model/struct/storage_ceph_bootstrap.py src/app/page.storage/api.py src/model/struct/storage.py` 통과.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_storage_models` 통과.
- `wiz_project_build(clean=False)` 성공.
- dev 서버를 `127.0.0.1:3017`에서 띄우고 Playwright로 `season-wiz-project=main`, `season-wiz-devmode=true` 쿠키를 설정한 뒤 `/storage` 진입을 시도했다. 인증 세션이 없어 `/access`로 리다이렉트되는 것을 확인했다.

## 남은 리스크
- 인증 세션이 없어 로그인 후 실제 모달 렌더링과 버튼 상호작용은 브라우저에서 검증하지 못했다.
- 자동 보정은 안전한 route 이동 수준으로 제한했다. Docker 설치, kernel module 설치, disk 정리, GPT/LVM package 설치 같은 host 변경은 별도 plan/run 흐름이 필요하다.
- preflight API는 현재 동기 실행이므로 모달은 즉시 열리지만 operation output은 API 응답 후 채워진다. 장시간 SSH 점검 중 실시간 단계 표시가 필요하면 background operation/polling 구조로 분리해야 한다.
