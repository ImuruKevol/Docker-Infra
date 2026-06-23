# 서비스 생성 자동 배치 CPU/Memory 구간 통계 반영

- **ID**: 014
- **날짜**: 2026-06-22
- **유형**: 기능 추가

## 작업 요약

서비스 생성/배포의 자동 배치 추천이 최신 1개 tick만 보지 않고 최근 구간의 CPU/Memory 최소/평균/최대 사용률을 함께 반영하도록 보강했다.
preflight 상세에도 계산된 구간 통계와 압력 점수를 포함해 추천 근거를 추적할 수 있게 했다.

## 원문 요청사항

```text
# ReviewOps Codex 작업 요청

아래 요청을 현재 프로젝트 루트에서 처리하세요. 필요한 파일을 직접 수정하고, 마지막 응답은 한국어로 간결하게 작성하세요.
스트리밍 응답은 사용하지 않습니다. 작업이 끝난 뒤 변경 요약, 확인한 내용, 남은 리스크만 정리하세요.
이 작업의 세션 단위는 아래 리뷰 ID입니다. 리뷰 ID가 같으면 같은 Codex 히스토리 맥락으로 이어서 처리하세요.

## 사용자 요청

작업 시작

## 리뷰 요약

- 리뷰 ID: orksevuaugerokpjbcmmkwhukmjwvxwn
- 제목: 서비스 생성 시 자동 배치 로직 보강
- 요청 링크: https://infra-dev.nanoha.kr/access
- Codex 요청자: 권태욱
- 프로젝트 루트: /root/docker-infra
- Codex 세션 ID: 신규
- 스크린샷 컨텍스트: 없음
- 에이전트 작업 지시서 컨텍스트: 포함됨
- HTML 문서 생성 규칙 컨텍스트: 없음
- HTML 문서 설정 컨텍스트: 없음
- HTML 프로젝트 인스트럭션 파일: 없음
- 첨부파일 컨텍스트: 0개

## 에이전트 작업 지시서

# 에이전트 작업 지시서

## 리뷰 정보

- 리뷰 ID: orksevuaugerokpjbcmmkwhukmjwvxwn
- 제목: 서비스 생성 시 자동 배치 로직 보강
- 상태: in_progress
- 우선순위: normal
- 분류: ux
- 프로젝트: Docker Infra DEV
- 프로젝트 종류: web_service
- 요청 링크: https://infra-dev.nanoha.kr/access
- 화면: 1440x900
- 캡처 방식: reviewops-sdk-dom-snapshot
- 스크린샷 첨부: no
- 리뷰 첨부 파일: 0개

## 리뷰어 요청 내용

서비스 생성 시 많은 부분을 고려해야 하는데, 충분이 고려되어있는지 확인하고 보강해줘.

- CPU, Memory 사용률을 고려할 때 현재 1tick에 대한 사용률만 보지 말고, 일정 구간동안의 평균 / 최소 / 최대 사용률을 모두 고려해야 함.
```

## 변경 파일 목록

- `src/model/struct/services_placement.py`
  - 최근 60분 기본 구간의 `node_metrics`를 함께 조회하고, `resource_window` metadata 또는 최근 metric rows를 기반으로 CPU/Memory min/avg/max/last 통계를 계산하도록 보강했다.
  - 자동 배치 점수에서 CPU/Memory latest 값 대신 avg/max/min 가중 압력 점수를 사용하도록 변경했다.
  - 추천 응답에 `cpu_stats`, `memory_stats`, `resource_window`, `stat_weights`, `metric_window_minutes`를 추가했다.
- `src/model/struct/services_preflight.py`
  - 실행 서버 preflight detail에 CPU/Memory 구간 통계와 압력 점수를 포함했다.
- `tests/api/test_services_preflight.py`
  - 자동 배치 점수가 latest tick만이 아니라 CPU/Memory 구간 통계를 반영하는지 검증하는 단위 테스트를 추가했다.
- `devlog.md`
- `devlog/2026-06-22/014-service-placement-resource-window-stats.md`

## 확인 결과

- `/opt/conda/envs/docker-infra/bin/python -m py_compile src/model/struct/services_placement.py src/model/struct/services_preflight.py tests/api/test_services_preflight.py`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight.ServicesPreflightStaticContractTest.test_service_placement_uses_cpu_memory_window_stats_for_pressure`: 통과
- `wiz_project_build(projectName="main", clean=false)`: 통과
- `/opt/conda/envs/docker-infra/bin/python -m unittest tests.api.test_services_preflight`: 실패 2건. 현재 `page.services.create/view.pug`의 기존 템플릿 UI 계약 문자열 `변수 {{editableTemplateFields().length}}개`, `selectedTemplateReadme()` 누락으로 실패했으며 이번 자동 배치 변경 범위와는 별개다.
