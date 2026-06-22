# 시스템 백업 UI와 스냅샷 기본 정책 정리

- **ID**: 002
- **날짜**: 2026-06-22
- **유형**: UX 개선 / 기능 수정

## 작업 요약
시스템 설정의 백업 화면에서 의미가 모호한 노드 설정 적용 버튼을 제거하고, 자동 백업 설정을 별도 카드가 아닌 백업 시스템 본문 흐름 안에 배치했다.
자동 백업이 꺼져도 예약/보관 설정이 보이도록 유지하되 비활성 상태로 흐리게 표시했고, 자동 백업 정책은 항상 컨테이너 상태 스냅샷을 포함하도록 고정했다.

## 원문 요청사항
```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

작업 시작

## 리뷰 요약

- 리뷰 ID: vgosoiiihlsnzkukbdizwwevcjgpgjcg
- 제목: 시스템 설정 - 백업 UI/UX 및 기능 수정

## 리뷰어 요청 내용

- "노드 설정 적용"이 무슨 기능을 하는 버튼인지 모르겠음. 가능하면 제거할 것.
- "서비스 이미지 자동 백업" 섹션을 카드로 따로 분리하지 말고 내용물을 밖으로 뺄 것.
- 자동 백업 사용을 비활성화해도 설정들은 보이게 하되, disabled와 회색, 흐리게를 할 것.
- 자동 백업 기능은 기본적으로 컨테이너 이미지만 백업하는게 아니라 현재 상태 자체를 백업하는 스냅샷 기능이어야 함. 현재는 스냅샷 백업이 옵션으로 되어있는데, 이걸 디폴트로 하고 화면에서는 제거할 것. 이미지만 백업은 지원할 필요 없음.
```

## 변경 파일 목록
- `src/app/page.system/view.pug`
  - 노드 설정 적용 버튼을 제거.
  - 자동 백업 영역의 별도 카드 테두리/헤더 구조를 제거하고 본문 섹션으로 재배치.
  - 자동 백업 비활성 상태에서도 설정을 렌더링하며 `fieldset disabled`, 회색/흐림 스타일을 적용.
  - 스냅샷 옵션 체크박스를 제거하고 "컨테이너 상태 스냅샷"으로 고정 표시.
- `src/app/page.system/view.ts`
  - 제거된 노드 설정 버튼의 프론트엔드 핸들러와 상태값을 삭제.
  - 백업 정책 저장/동기화 기본값을 `container_snapshot`, `snapshot_enabled: true`로 고정.
  - 수동 백업 요청 문구와 결과 문구를 서비스 상태 스냅샷 기준으로 정리.
- `src/app/page.system/api.py`
  - 수동 자동 백업 실행 API가 `include_snapshots`와 `snapshot_enabled`를 항상 `True`로 전달하도록 보정.
- `src/model/struct/backup_system_policy_defaults.py`
  - 백업 정책 기본/정규화 값을 컨테이너 상태 스냅샷 방식으로 고정.
- `src/model/struct/service_image_backup_scheduler.py`
  - 스케줄러가 저장 정책이나 요청 payload의 스냅샷 제외 값을 무시하고 항상 스냅샷을 포함하도록 보정.
- `tests/api/test_backup_system_ui.py`
  - 자동 백업 UI의 노드 버튼 제거, 카드 제거, disabled 표시, 스냅샷 옵션 제거 계약을 반영.
- `tests/api/test_backup_system_schedule.py`
  - 정책 정규화와 수동 실행 payload가 스냅샷 제외 값을 받아도 스냅샷을 유지하는 계약을 반영.
- `tests/api/test_backup_registry_nodes.py`
  - 노드 백업 레지스트리 API 계약은 유지하되 시스템 화면 버튼 노출 기대를 제거.

## 검증 결과
- 통과: `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_backup_system_ui tests.api.test_backup_system_schedule tests.api.test_backup_registry_nodes`
- 통과: `wiz_project_build(clean=false)`
- 참고: `/opt/conda/envs/docker-infra/bin/python -m unittest discover tests/api`는 기존 라이브 인증 401, 서비스 생성 정적 계약, WIZ 구조 계약 다수의 기존 실패로 전체 통과하지 못했다. 이번 변경 대상 테스트는 별도로 통과했다.
