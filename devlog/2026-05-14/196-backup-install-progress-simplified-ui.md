# 196. 백업 시스템 설치 진행 로그와 설정 화면 단순화

- **ID**: 196
- **날짜**: 2026-05-14
- **유형**: 개선

## 작업 요약
백업 시스템이 설치되지 않은 상태에서는 설치 버튼과 설치 진행 로그만 보이도록 시스템 설정 Backup 탭을 단순화했다.
설치 요청은 백그라운드 operation으로 시작하고, 화면은 operation output을 polling해서 installer 로그처럼 진행 단계를 표시한다.
설치 후 화면에서는 내부 Harbor URL, 관리자 계정, 저장 경로를 숨기고 상태 확인 결과만 보여주며, 자동 백업 설정은 사용 체크 전에는 추가 설정을 숨기도록 정리했다.

## 원문 요청사항
```text
설치 후 시작을 누르면 그냥 무작정 기다리고만 있어야 해서 실제로 설치가 되고 있는건지 모르겠어.
설치가 되어있지 않은 상태면 그냥 아예 다른 설정들은 감춰버리고, 설치 버튼만 놔두도록 수정해줘. 그리고 버튼을 누르면 설치 과정이 출력되면서 installer처럼 설치가 어디까지 진행이 되었는지 알 수 있도록 해줘.
그리고 Harbor URL, 관리자 계정같은 정보는 필요 없어. 사용자가 harbor에는 직접 접속할 일이 없도록 하는게 목표야. 그냥 백업 시스템 상태 확인같은 버튼을 누르면 health check만 표시되도록 해줘.
그리고 저장 경로가 표시되어 있는데, 이것도 사실 필요 없어.
아래에 있는 자동 백업 설정들은 너무 복잡하게 되어있고, 설정이 너무 어려워. 조금 더 쉽게 단순화해줘. 사용에 체크를 안하면 다른 설정들은 보여줄 필요도 없고.
```

## 변경 파일 목록
- `src/app/page.system/view.pug`: 미설치/설치 상태별 Backup 탭 구성을 분리하고 내부 Harbor 정보, 저장 경로, 복잡한 자동 백업/정리 설정 노출 제거.
- `src/app/page.system/view.ts`: 백그라운드 설치 시작, operation polling, 설치 로그 출력, 상태 확인 결과 표시, 단순 자동 백업 저장 payload 적용.
- `src/app/page.system/api.py`: 백그라운드 설치 시작 옵션과 백업 operation 상태 조회 API 추가.
- `src/model/struct/local_executor.py`: local command stdout/stderr를 실시간으로 전달하는 `run_stream` 추가.
- `src/model/struct/backup_system_runtime.py`: 백업 시스템 설치를 백그라운드 operation으로 실행하고 준비/설정/installer 진행 로그를 누적하도록 보강.
- `src/model/struct/backup_system_policy_defaults.py`: 숨겨진 허용 시간 설정이 자동 백업을 제한하지 않도록 기본 시간대를 하루 종일로 변경.
- `tests/api/test_backup_system_ui.py`: Backup 탭 UI 단순화와 설치 진행 로그 계약 테스트 추가.
- `devlog.md`, `devlog/2026-05-14/196-backup-install-progress-simplified-ui.md`: 작업 이력 기록.

## 확인 결과
- 성공: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_backup_system_runtime tests.api.test_backup_system_ui tests.api.test_local_executor`
- 성공: `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/local_executor.py src/model/struct/backup_system_runtime.py src/model/struct/backup_system_policy_defaults.py src/app/page.system/api.py tests/api/test_backup_system_runtime.py tests/api/test_backup_system_ui.py`
- 성공: `wiz_project_build(clean=false)`

## 남은 리스크
- 실제 Harbor 설치 전체를 다시 실행하지는 않았다.
- 설치 중 브라우저를 새로고침하면 현재 화면의 polling 상태는 초기화되며, 작업 로그 화면에는 operation 기록이 남는다.
