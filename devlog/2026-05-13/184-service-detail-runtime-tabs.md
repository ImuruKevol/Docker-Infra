# 서비스 상세 구성 탭 실행 상태와 원문/파일/버전 탭 재구성

- **ID**: 184
- **날짜**: 2026-05-13
- **유형**: UX 개선

## 작업 요약
서비스 상세의 구성 탭에서 접속 흐름 캔버스를 제거하고 실행 상태 중심으로 재구성했다.
컨테이너를 외부 오픈 구성과 내부 전용 구성으로 나누어 표시하고, 컨테이너별 실행/중지/재시작/삭제 액션과 일괄 시작/중지/재시작 액션을 구성 탭에 배치했다.
백업 탭은 제거했고, 기존 고급 탭 내용은 Compose/Nginx, 서비스 파일, 버전 이력 탭으로 분리했다.
내장 Harbor가 활성화되어 있고 해당 Compose 버전에 백업된 이미지가 있으면 버전 되돌리기 시 Harbor 이미지 참조를 함께 반영하도록 보강했다.

## 원문 요청사항
```text
작업을 진행해줘. 이 서비스의 사용자층이 개발 지식이 거의 없는 일반 관리자라는 것을 명심하고 진행해줘.

서비스 상세에서 구성 탭에 접속 흐름을 현재 캔버스로 그리고 있는데, 이건 아무리 해도 잘 그릴 수가 없어서 그냥 접속 흐름은 제거하고 아래의 실행 상태 부분을 개선하는게 나을 것 같아. 실행 상태 부분을 외부에 오픈되는 컨테이너와 내부에서만 도는 컨테이너를 구분해서 표시하면 될 것 같아. 그리고 여기에 일괄 시작, 일괄 중지, 일괄 재시작 버튼을 추가해줘.
백업 탭은 그냥 삭제해줘.
고급 탭의 내용들은 각각 별도의 탭들로 분리해야해. Compose 원문 및 Nginx 설정, 서비스 파일, 버전 이력으로. 실행 구성 요소의 컨테이너별 액션들은 구성 탭으로 이동하고, 컨테이너 목록 자체는 구성 탭만 있으면 되기에 따로 탭으로 분리할 필요는 없어.
버전 이력의 경우엔 내장 harbor가 시스템 설정에서 활성화가 되어있을 경우엔 Compose 버전에 이미지 버전까지 롤백할 수 있도록 해야해.
```

## 변경 파일 목록
- `src/app/page.services/view.pug`
  - 구성 탭 접속 흐름 캔버스 제거
  - 외부 오픈/내부 전용 컨테이너 그룹과 일괄 액션 버튼 추가
  - 백업 탭 제거, Compose/Nginx·서비스 파일·버전 이력 탭 분리
  - 버전 되돌리기 모달에 Harbor 이미지 롤백 상태 표시 추가
- `src/app/page.services/view.ts`
  - 상세 탭 타입과 지연 로딩 섹션을 새 탭 구조에 맞게 수정
  - 컨테이너 외부/내부 분류, 노출 상태 라벨, 일괄 컨테이너 액션 추가
  - Harbor 이미지 롤백 안내와 되돌리기 요청 옵션 추가
- `src/app/page.services/api.py`
  - 상세 응답 섹션 플래그를 새 탭 구조로 조정
  - `service_container_bulk_action` API 추가
- `src/model/struct/services_runtime.py`
  - 버전/원문 상세 응답에 백업 시스템 상태 추가
- `src/model/struct/services_rollback.py`
  - Compose 버전의 Harbor 이미지 백업 조회와 되돌리기 시 이미지 참조 반영 추가

## 확인한 내용
- `/opt/conda/envs/docker-infra/bin/python -m py_compile project/main/src/app/page.services/api.py project/main/src/model/struct/services_runtime.py project/main/src/model/struct/services_rollback.py` 통과
- `wiz_project_build(clean=false, projectName=main)` 성공

## 남은 리스크
- 실제 운영 서비스에서 외부 오픈/내부 전용 분류가 모든 Compose 패턴을 완벽히 반영하는지는 다양한 서비스 데이터로 추가 확인이 필요하다.
- Harbor 이미지 롤백은 해당 Compose 버전에 성공한 이미지 백업 기록이 있을 때만 이미지 참조까지 함께 반영된다.
