# 모달 레이어와 서버별 자원 차트 탭 UI 수정

- **ID**: 166
- **날짜**: 2026-05-13
- **유형**: 버그 수정

## 작업 요약
1440px 화면에서 페이지 모달이 데스크톱 사이드바 아래에 깔려 왼쪽이 잘리는 문제를 사이드바 z-index 조정으로 수정했다.
대시보드 서버별 자원 추이 모달은 서버 목록을 토글 탭으로 제공하고, 선택한 서버 하나의 CPU/Memory/Storage 차트만 렌더링하도록 변경했다. 서버 관리 자원 기록 API는 오래 로드된 metric history 모델에 `node_chart`가 없어도 query fallback으로 응답하도록 보강했다.

## 원문 요청사항
```text
1440 사이즈에서 모달들이 전체적으로 왼쪽이 잘리는 문제를 수정하고, 대시보드 - 서버별 모니터링 모달에서 각 서버들별로 보는걸 토글 버튼을 이용한 탭 형태로 서버 하나씩만 보도록 UI를 수정해줘.

그리고 서버 관리 화면에서 크게 보기 모달에서 'NodesMetricHistory' object has no attribute 'node_chart' 이런 에러가 뜨고 있어.
```

## 변경 파일 목록
- `src/app/layout.sidebar/view.pug`
  - 데스크톱 사이드바 z-index를 `z-50`에서 `z-30`으로 낮춰 페이지 모달(`z-40`)이 1440px에서도 사이드바 위에 표시되도록 수정.
- `src/app/page.dashboard/view.pug`
  - 서버별 자원 추이 모달을 서버별 카드 그리드에서 토글 탭 + 단일 서버 차트 패널 구조로 변경.
  - 선택 서버의 CPU/Memory/Storage 차트를 한 화면에 표시하도록 차트 컨테이너를 분리.
- `src/app/page.dashboard/view.ts`
  - 활성 서버 차트 ID 상태와 탭 선택/초기 선택 로직 추가.
  - 선택한 서버 차트만 렌더링되도록 기존 node chart 렌더 흐름과 연결.
- `src/app/page.servers/api.py`
  - `resource_history`, `delete_resource_history`에서 metric history 모델을 직접 로드하도록 변경.
  - `node_chart`가 없는 오래 로드된 모델 객체에서는 `query` fallback으로 응답해 크게 보기 모달 오류를 방지.

## 검증 결과
- `wiz_project_build(clean=false)` 성공.
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests/api/test_node_reporter.py` 성공 (`OK`, 1건 skipped).

## 남은 리스크
실제 운영 세션에서 이미 로드된 WIZ 모델 캐시 상태는 서버 재시작 없이 환경마다 다를 수 있으므로, fallback 경로로 에러는 방어했지만 실서비스 화면의 1440px 시각 확인은 배포 환경에서 한 번 더 확인이 필요하다.
